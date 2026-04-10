#!/bin/bash
# setup-foundry-iq.sh — Upload operational docs and guide Foundry IQ KB creation
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESOURCE_GROUP="rg-multi-agent-ops-assistant"

# Get storage account name from deployment outputs
STORAGE_ACCOUNT=$(az deployment group show \
  --resource-group "$RESOURCE_GROUP" \
  --name main \
  --query properties.outputs.storageAccountName.value \
  -o tsv)

echo "  Storage account: $STORAGE_ACCOUNT"

# Upload operational docs to blob storage
echo "  Uploading operational docs to blob storage..."
az storage blob upload-batch \
  --account-name "$STORAGE_ACCOUNT" \
  --destination operational-docs \
  --source "$PROJECT_ROOT/operational-docs" \
  --auth-mode login \
  --overwrite true \
  --output none

echo "  ✅ Documents uploaded to blob storage"
echo ""
echo "  NOTE: Knowledge Base (Search index) creation is now automated"
echo "  by the azd postprovision hook. This script only handles blob upload."
echo "  If using azd, run 'azd up' which handles everything end-to-end."
