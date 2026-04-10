#!/bin/bash
set -e

echo "========================================="
echo "  MULTI-AGENT OPS ASSISTANT — Full Deployment"
echo "========================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RESOURCE_GROUP="rg-multi-agent-ops-assistant"
LOCATION="northcentralus"

# -------------------------------------------
# PHASE 1: Pre-flight checks
# -------------------------------------------
echo ""
echo "🔍 Phase 1: Pre-flight checks..."

for cmd in az sqlcmd jq docker; do
  if ! command -v $cmd &> /dev/null; then
    echo "❌ $cmd is not installed. Please install it and try again."
    exit 1
  fi
done

if ! az account show &> /dev/null 2>&1; then
  echo "🔐 Not logged in to Azure. Logging in..."
  az login
fi

echo "✅ All tools available and logged in"
echo "   Subscription: $(az account show --query name -o tsv)"
echo "   User: $(az account show --query user.name -o tsv)"

# -------------------------------------------
# PHASE 2: Deploy infrastructure (Bicep)
# -------------------------------------------
echo ""
echo "🏗️  Phase 2: Deploying infrastructure..."

DEPLOYER_ID=$(az ad signed-in-user show --query id -o tsv)

if [ -z "$SQL_ADMIN_PASSWORD" ]; then
  read -sp "Enter SQL admin password (min 8 chars, mixed case + number + special): " SQL_ADMIN_PASSWORD
  echo ""
  read -sp "Confirm SQL admin password: " SQL_ADMIN_PASSWORD_CONFIRM
  echo ""
  if [ "$SQL_ADMIN_PASSWORD" != "$SQL_ADMIN_PASSWORD_CONFIRM" ]; then
    echo "❌ Passwords do not match. Exiting."
    exit 1
  fi
fi

az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

echo "   Deploying Bicep templates (this takes 3-5 minutes)..."
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$PROJECT_ROOT/infra/main.bicep" \
  --parameters "$PROJECT_ROOT/infra/main.bicepparam" \
  --parameters deployerPrincipalId="$DEPLOYER_ID" sqlAdminPassword="$SQL_ADMIN_PASSWORD" \
  --name main \
  --output none

echo "✅ Infrastructure deployed"

# -------------------------------------------
# PHASE 3: Extract outputs and generate .env
# -------------------------------------------
echo ""
echo "📝 Phase 3: Generating .env file..."

bash "$SCRIPT_DIR/../infra/scripts/output-env.sh"

echo "✅ .env file created"
set -a
source "$PROJECT_ROOT/.env"
set +a

# -------------------------------------------
# PHASE 4: Seed database
# -------------------------------------------
echo ""
echo "🗄️  Phase 4: Seeding database..."

echo "   Waiting 30 seconds for SQL firewall rules to propagate..."
sleep 30

bash "$SCRIPT_DIR/../infra/scripts/seed-database.sh"

echo "✅ Database seeded with demo data"

# -------------------------------------------
# PHASE 5: Upload docs to blob storage
# -------------------------------------------
echo ""
echo "📚 Phase 5: Uploading operational docs to blob storage..."

bash "$SCRIPT_DIR/../infra/scripts/setup-foundry-iq.sh"

echo "✅ Documents uploaded"

# -------------------------------------------
# PHASE 6: Build and push container
# -------------------------------------------
echo ""
echo "🐳 Phase 6: Building and pushing container..."

ACR_NAME=$(az deployment group show \
  --resource-group "$RESOURCE_GROUP" \
  --name main \
  --query properties.outputs.acrRegistryName.value \
  -o tsv)

ACR_SERVER=$(az deployment group show \
  --resource-group "$RESOURCE_GROUP" \
  --name main \
  --query properties.outputs.acrLoginServer.value \
  -o tsv)

az acr login --name "$ACR_NAME"

cd "$PROJECT_ROOT"
docker build -t ops-assistant:latest .
docker tag ops-assistant:latest "$ACR_SERVER/ops-assistant:latest"
docker push "$ACR_SERVER/ops-assistant:latest"

echo "✅ Container pushed to $ACR_SERVER"

# -------------------------------------------
# PHASE 7: Summary
# -------------------------------------------
echo ""
echo "========================================="
echo "  ✅ DEPLOYMENT COMPLETE"
echo "========================================="
echo ""
echo "Resources deployed in: $RESOURCE_GROUP"
echo ""
echo "Endpoints:"
echo "  Foundry:  $AZURE_AI_PROJECT_ENDPOINT"
echo "  Search:   $AZURE_AI_SEARCH_ENDPOINT"
echo "  ACR:      $ACR_SERVER"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  NEXT STEPS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. CREATE FOUNDRY IQ KNOWLEDGE BASE (manual, ~2 minutes):"
echo "   → Open https://ai.azure.com"
echo "   → Open your project"
echo "   → Knowledge Bases → Create → Name: 'ops-assistant-kb'"
echo "   → Add source → Azure Blob Storage → select storage account → 'operational-docs' container"
echo "   → Start indexing"
echo ""
echo "2. TEST LOCALLY:"
echo "   source .env"
echo "   pip install -r requirements.txt"
echo "   uvicorn src.api:app --reload --port 8000"
echo "   → Open http://localhost:8000"
echo ""
echo "3. DEPLOY AS HOSTED AGENT (after local testing):"
echo "   azd init -t https://github.com/Azure-Samples/azd-ai-starter-basic"
echo "   azd ai agent init -m ./agent.yaml"
echo "   azd up"
echo ""
