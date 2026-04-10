using 'main.bicep'

param projectName = 'opsassistant'

param location = readEnvironmentVariable('AZURE_LOCATION', 'swedencentral')

param customHostname = readEnvironmentVariable('CUSTOM_HOSTNAME', '')

// GPT-4o model capacity (TPM in thousands) — lower for test environments with limited quota
param modelCapacity = int(readEnvironmentVariable('MODEL_CAPACITY', '70'))

// Injected by preprovision hook via azd env set
param deployerPrincipalId = readEnvironmentVariable('DEPLOYER_PRINCIPAL_ID', '')
param deployerDisplayName = readEnvironmentVariable('DEPLOYER_DISPLAY_NAME', 'Deployment Admin')

// Private networking (default: false = public access; set USE_PRIVATE_ENDPOINTS=true for VNet + PEs)
param usePrivateEndpoints = readEnvironmentVariable('USE_PRIVATE_ENDPOINTS', 'false') == 'true'
