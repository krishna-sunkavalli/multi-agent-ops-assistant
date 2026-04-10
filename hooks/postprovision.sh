#!/bin/bash
# postprovision.sh — azd hook: runs after infrastructure provisioning
# Seeds the SQL database, grants SQL access to the app's managed identity,
# uploads operational docs to blob storage, and creates/populates the Search index.
# NOTE: Container image build + deploy is handled by `azd deploy` via remoteBuild.
#       Resources deploy with public access by default (private is opt-in).
set -e

echo ""
echo "════════════════════════════════════════════════════"
echo "  Post-Provision: Configuring Ops Assistant"
echo "════════════════════════════════════════════════════"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# azd sets these from Bicep outputs automatically
SQL_SERVER="${SQL_SERVER_FQDN}"
SQL_DB="${SQL_DATABASE_NAME}"
SQL_SERVER_NAME="${SQL_SERVER_NAME}"
STORAGE_ACCOUNT="${AZURE_STORAGE_ACCOUNT_NAME}"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP_NAME}"
CA_NAME="${SERVICE_OPSASSISTANT_NAME}"
PRINCIPAL_ID="${SERVICE_OPSASSISTANT_PRINCIPAL_ID}"
APP_URL="${SERVICE_OPSASSISTANT_URL}"
SEARCH_ENDPOINT="${AZURE_SEARCH_ENDPOINT}"
SEARCH_SERVICE_NAME="${AZURE_SEARCH_SERVICE_NAME}"

if [ -z "$SQL_SERVER_NAME" ]; then
  SQL_SERVER_NAME=$(echo "$SQL_SERVER" | cut -d'.' -f1)
fi

if [ -z "$SEARCH_SERVICE_NAME" ] && [ -n "$SEARCH_ENDPOINT" ]; then
  SEARCH_SERVICE_NAME=$(echo "$SEARCH_ENDPOINT" | sed 's|https://||;s|\.search\.windows\.net.*||')
fi

# ── Pre-flight: Ensure sqlcmd is installed ──
if ! command -v sqlcmd &> /dev/null; then
  echo ""
  echo "  ERROR: sqlcmd is required but not found."
  echo "  Install the modern Go-based sqlcmd:"
  echo "    curl -fsSL https://aka.ms/install-sqlcmd | bash"
  echo "  Or see: https://learn.microsoft.com/sql/tools/sqlcmd/go-sqlcmd"
  echo ""
  exit 1
fi

# ── Step 1/4: Add SQL firewall rules for seeding ──
echo ""
echo "Step 1/4: Adding SQL firewall rules for seeding..."

MY_IP=$(curl -s https://api.ipify.org)
az sql server firewall-rule create \
  --resource-group "$RESOURCE_GROUP" \
  --server "$SQL_SERVER_NAME" \
  --name "azd-deployer-temp" \
  --start-ip-address "$MY_IP" \
  --end-ip-address "$MY_IP" \
  --output none 2>/dev/null || true

az sql server firewall-rule create \
  --resource-group "$RESOURCE_GROUP" \
  --server "$SQL_SERVER_NAME" \
  --name "AllowAllWindowsAzureIps" \
  --start-ip-address "0.0.0.0" \
  --end-ip-address "0.0.0.0" \
  --output none 2>/dev/null || true

echo "  Firewall rules created (deployer IP: $MY_IP + Azure services)"
echo "  Waiting 30 seconds for propagation..."
sleep 30

# ── Step 2/4: Seed the database ──
echo ""
echo "Step 2/4: Seeding database..."

echo "  Applying schema to $SQL_SERVER / $SQL_DB..."
sqlcmd -S "$SQL_SERVER" -d "$SQL_DB" \
  --authentication-method=ActiveDirectoryDefault \
  -i "$PROJECT_ROOT/database/schema.sql"

echo "  Inserting seed data..."
sqlcmd -S "$SQL_SERVER" -d "$SQL_DB" \
  --authentication-method=ActiveDirectoryDefault \
  -i "$PROJECT_ROOT/database/seed-data.sql"

echo "  Database seeded"

# ── Step 3/4: Grant SQL access to the app's user-assigned managed identity ──
echo ""
echo "Step 3/4: Granting SQL access to Container App '$CA_NAME'..."

# SQL SID for TYPE=E must use the CLIENT_ID (application ID), not the principal/object ID.
# azd outputs CLIENT_ID as SERVICE_OPSASSISTANT_CLIENT_ID.
CLIENT_ID="${SERVICE_OPSASSISTANT_CLIENT_ID}"
if [ -z "$CLIENT_ID" ]; then
  # Fallback: look up client ID from the principal ID
  CLIENT_ID=$(az identity list --resource-group "$RESOURCE_GROUP" \
    --query "[?principalId=='$PRINCIPAL_ID'].clientId | [0]" -o tsv 2>/dev/null || true)
fi

if [ -z "$CLIENT_ID" ]; then
  echo "  WARNING: Could not determine CLIENT_ID — skipping SQL user grant"
else
  # Convert GUID to binary SID for SQL CREATE USER ... WITH SID
  # (avoids "duplicate display name" error when multiple environments coexist)
  SID_HEX=$(python3 -c "
import uuid, sys
g = uuid.UUID(sys.argv[1])
print('0x' + g.bytes_le.hex().upper())
" "$CLIENT_ID")

  TEMP_SQL=$(mktemp /tmp/ca-sql-user-XXXXXX.sql)
  cat > "$TEMP_SQL" <<EOSQL
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '$CA_NAME')
BEGIN
    CREATE USER [$CA_NAME] WITH SID = $SID_HEX, TYPE = E;
    ALTER ROLE db_datareader ADD MEMBER [$CA_NAME];
    ALTER ROLE db_datawriter ADD MEMBER [$CA_NAME];
    PRINT 'Created SQL user for $CA_NAME';
END
ELSE
BEGIN
    PRINT 'SQL user $CA_NAME already exists';
END
EOSQL

  sqlcmd -S "$SQL_SERVER" -d "$SQL_DB" \
    --authentication-method=ActiveDirectoryDefault \
    -i "$TEMP_SQL" || {
      echo "  WARNING: Could not grant SQL access automatically."
      echo "  Run manually after deployment:"
      echo "    CREATE USER [$CA_NAME] WITH SID = $SID_HEX, TYPE = E;"
      echo "    ALTER ROLE db_datareader ADD MEMBER [$CA_NAME];"
      echo "    ALTER ROLE db_datawriter ADD MEMBER [$CA_NAME];"
    }

  rm -f "$TEMP_SQL"
  echo "  SQL access granted to '$CA_NAME' (ClientId: $CLIENT_ID)"
fi

# Clean up temporary deployer firewall rule (keep AllowAllWindowsAzureIps for app)
az sql server firewall-rule delete \
  --resource-group "$RESOURCE_GROUP" \
  --server "$SQL_SERVER_NAME" \
  --name "azd-deployer-temp" \
  --output none 2>/dev/null || true

# ── Step 4/4: Upload operational docs + create Search index ──
echo ""
echo "Step 4/4: Uploading docs and creating Search index..."

az storage blob upload-batch \
  --account-name "$STORAGE_ACCOUNT" \
  --destination operational-docs \
  --source "$PROJECT_ROOT/operational-docs" \
  --auth-mode login \
  --overwrite true \
  --output none

echo "  Documents uploaded to blob storage"

if [ -n "$SEARCH_SERVICE_NAME" ]; then
  ADMIN_KEY=$(az search admin-key show \
    --service-name "$SEARCH_SERVICE_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query primaryKey -o tsv)

  INDEX_NAME="ops-assistant-kb"
  API_VERSION="2024-07-01"

  # Delete existing index if present (idempotent re-run)
  curl -s -X DELETE \
    "${SEARCH_ENDPOINT}/indexes/${INDEX_NAME}?api-version=${API_VERSION}" \
    -H "api-key: ${ADMIN_KEY}" \
    -H "Content-Type: application/json" \
    -o /dev/null 2>/dev/null || true

  # Create the index
  INDEX_DEF='{
    "name": "'"${INDEX_NAME}"'",
    "fields": [
      { "name": "id", "type": "Edm.String", "key": true, "searchable": false, "filterable": true, "retrievable": true },
      { "name": "content", "type": "Edm.String", "searchable": true, "retrievable": true, "analyzer": "en.lucene" },
      { "name": "title", "type": "Edm.String", "searchable": true, "retrievable": true, "filterable": true },
      { "name": "source", "type": "Edm.String", "searchable": false, "retrievable": true, "filterable": true }
    ]
  }'

  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "${SEARCH_ENDPOINT}/indexes?api-version=${API_VERSION}" \
    -H "api-key: ${ADMIN_KEY}" \
    -H "Content-Type: application/json" \
    -d "${INDEX_DEF}")

  if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    echo "  Search index '${INDEX_NAME}' created"
  else
    echo "  WARNING: Failed to create search index (HTTP $HTTP_CODE)"
  fi

  # Index each operational doc
  DOCS_PATH="$PROJECT_ROOT/operational-docs"
  DOC_COUNT=0

  BATCH='{"value":['
  FIRST=true

  for FILE in "$DOCS_PATH"/*.md; do
    [ -f "$FILE" ] || continue
    BASENAME=$(basename "$FILE" .md)
    DOC_ID=$(echo "$BASENAME" | sed 's/[^a-zA-Z0-9_-]/_/g')
    TITLE=$(echo "$BASENAME" | sed 's/-/ /g')
    SOURCE=$(basename "$FILE")
    CONTENT=$(python3 -c "
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    print(json.dumps(f.read()))
" "$FILE")

    if [ "$FIRST" = true ]; then
      FIRST=false
    else
      BATCH="${BATCH},"
    fi
    BATCH="${BATCH}{\"@search.action\":\"upload\",\"id\":\"${DOC_ID}\",\"content\":${CONTENT},\"title\":\"${TITLE}\",\"source\":\"${SOURCE}\"}"
    DOC_COUNT=$((DOC_COUNT + 1))
  done

  BATCH="${BATCH}]}"

  if [ "$DOC_COUNT" -gt 0 ]; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
      "${SEARCH_ENDPOINT}/indexes/${INDEX_NAME}/docs/index?api-version=${API_VERSION}" \
      -H "api-key: ${ADMIN_KEY}" \
      -H "Content-Type: application/json" \
      -d "${BATCH}")

    if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
      echo "  Indexed ${DOC_COUNT} documents into '${INDEX_NAME}'"
    else
      echo "  WARNING: Failed to index documents (HTTP $HTTP_CODE)"
    fi
  else
    echo "  WARNING: No .md files found in $DOCS_PATH"
  fi
else
  echo "  WARNING: Search service name not found — skipping KB creation"
fi

# ── Summary ──
echo ""
echo "════════════════════════════════════════════════════"
echo "  Post-provision complete!"
echo ""
echo "  Database: seeded with schema + data"
echo "  SQL access: granted to Container App MI"
echo "  Blob storage: operational docs uploaded"
echo "  Search index: 'ops-assistant-kb' created and indexed"
echo ""
if [ -n "$APP_URL" ]; then
  echo "  App URL: $APP_URL"
fi
echo "════════════════════════════════════════════════════"