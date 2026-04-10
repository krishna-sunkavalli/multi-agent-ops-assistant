#!/bin/bash
# teardown.sh — Remove all Ops Assistant Azure resources
RESOURCE_GROUP="rg-multi-agent-ops-assistant"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "⚠️  This will DELETE all Ops Assistant resources in '$RESOURCE_GROUP'."
read -p "Are you sure? (yes/no): " CONFIRM

if [ "$CONFIRM" = "yes" ]; then
  echo "Deleting resource group $RESOURCE_GROUP..."
  az group delete --name "$RESOURCE_GROUP" --yes --no-wait

  # Clean up local files
  rm -f "$PROJECT_ROOT/.env"

  echo "✅ Teardown initiated. Resource deletion is running in the background."
  echo "   Check Azure portal to confirm all resources are removed."
else
  echo "Cancelled."
fi
