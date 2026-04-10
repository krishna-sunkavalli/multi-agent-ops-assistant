# preprovision.ps1 — azd hook: runs before infrastructure provisioning
# Captures the deployer's Entra identity and configures remote ACR builds.

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "════════════════════════════════════════════════════"
Write-Host "  Pre-Provision: Configuring environment"
Write-Host "════════════════════════════════════════════════════"

# ── Enable remote ACR builds (no Docker needed on the local machine) ──
azd env set AZURE_CONTAINER_REGISTRY_BUILD true 2>$null
Write-Host "  Remote ACR builds enabled (no local Docker required)"

try {
    $UserJson = az ad signed-in-user show -o json 2>$null | ConvertFrom-Json
    if ($UserJson) {
        Write-Host "  Deployer: $($UserJson.displayName) ($($UserJson.id))"
        azd env set DEPLOYER_PRINCIPAL_ID $UserJson.id
        azd env set DEPLOYER_DISPLAY_NAME $UserJson.displayName
        Write-Host "  Saved to azd env"
    } else {
        throw "No signed-in user"
    }
} catch {
    Write-Host "  WARNING: Could not detect signed-in user."
    Write-Host "  Make sure you are logged in: az login && azd auth login"
    Write-Host "  Continuing — SQL admin will default to 'Deployment Admin'."
}
