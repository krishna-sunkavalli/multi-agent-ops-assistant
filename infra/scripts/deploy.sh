#!/bin/bash
# deploy.sh — One-command end-to-end infrastructure deployment for MULTI-AGENT OPS ASSISTANT
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESOURCE_GROUP="rg-multi-agent-ops-assistant"
LOCATION="northcentralus"

echo "═══════════════════════════════════════════════════"
echo "  Multi-Agent Ops Assistant — Infrastructure Deployment"
echo "═══════════════════════════════════════════════════"
echo ""

# Step 1: Get deployer's principal ID
echo "▶ Step 1/6: Retrieving deployer identity..."
DEPLOYER_ID=$(az ad signed-in-user show --query id -o tsv)
echo "  Deployer principal ID: $DEPLOYER_ID"

# Step 2: Prompt for SQL admin password if not set
if [ -z "$SQL_ADMIN_PASSWORD" ]; then
  echo ""
  read -s -p "  Enter SQL admin password: " SQL_ADMIN_PASSWORD
  echo ""
  read -s -p "  Confirm SQL admin password: " SQL_ADMIN_PASSWORD_CONFIRM
  echo ""
  if [ "$SQL_ADMIN_PASSWORD" != "$SQL_ADMIN_PASSWORD_CONFIRM" ]; then
    echo "❌ Passwords do not match. Exiting."
    exit 1
  fi
fi

# Step 3: Create resource group
echo ""
echo "▶ Step 2/6: Creating resource group '$RESOURCE_GROUP'..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

# Step 4: Run Bicep deployment
echo ""
echo "▶ Step 3/6: Deploying infrastructure (this may take 5-10 minutes)..."
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$PROJECT_ROOT/infra/main.bicep" \
  --parameters "$PROJECT_ROOT/infra/main.bicepparam" \
  --parameters deployerPrincipalId="$DEPLOYER_ID" sqlAdminPassword="$SQL_ADMIN_PASSWORD" \
  --name main \
  --output none

echo "  ✅ Infrastructure deployed"

# Step 5: Extract outputs and generate .env file
echo ""
echo "▶ Step 4/6: Generating .env file..."
bash "$SCRIPT_DIR/output-env.sh"

# Step 6: Seed the database
echo ""
echo "▶ Step 5/6: Seeding database..."
bash "$SCRIPT_DIR/seed-database.sh"

# Step 7: Upload docs and set up Foundry IQ
echo ""
echo "▶ Step 6/6: Setting up Foundry IQ knowledge base..."
bash "$SCRIPT_DIR/setup-foundry-iq.sh"

echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ Deployment complete!"
echo ""
echo "  Run 'source .env' to load environment variables."
echo "  Then 'python -m src.main' to start the chatbot."
echo "═══════════════════════════════════════════════════"
