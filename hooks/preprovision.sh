#!/usr/bin/env bash
# preprovision.sh — azd hook: runs before infrastructure provisioning
# Captures the deployer's Entra identity and configures remote ACR builds.

set -euo pipefail

echo ""
echo "════════════════════════════════════════════════════"
echo "  Pre-Provision: Configuring environment"
echo "════════════════════════════════════════════════════"

# ── Enable remote ACR builds (no Docker needed on the local machine) ──
azd env set AZURE_CONTAINER_REGISTRY_BUILD true 2>/dev/null
echo "  Remote ACR builds enabled (no local Docker required)"

DEPLOYER_ID=$(az ad signed-in-user show --query id -o tsv 2>/dev/null || true)
DEPLOYER_NAME=$(az ad signed-in-user show --query displayName -o tsv 2>/dev/null || true)

if [ -z "$DEPLOYER_ID" ]; then
    echo "  WARNING: Could not detect signed-in user."
    echo "  Make sure you are logged in: az login && azd auth login"
    echo "  Continuing — SQL admin will default to 'Deployment Admin'."
else
    echo "  Deployer: $DEPLOYER_NAME ($DEPLOYER_ID)"
    azd env set DEPLOYER_PRINCIPAL_ID "$DEPLOYER_ID"
    azd env set DEPLOYER_DISPLAY_NAME "$DEPLOYER_NAME"
    echo "  Saved to azd env"
fi
