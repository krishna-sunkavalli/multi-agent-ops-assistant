# postprovision.ps1 — azd hook: runs after infrastructure provisioning
# Seeds the SQL database, grants SQL access to the app's managed identity,
# uploads operational docs to blob storage, and creates/populates the Search index.
# NOTE: Container image build + deploy is handled by `azd deploy` via remoteBuild.
#       Resources deploy with public access by default (private is opt-in).

$ErrorActionPreference = "Stop"

function Assert-LastExitCode {
    param([string]$Message = "Command failed")
    if ($LASTEXITCODE -ne 0) {
        throw "$Message (exit code: $LASTEXITCODE)"
    }
}

Write-Host ""
Write-Host "════════════════════════════════════════════════════"
Write-Host "  Post-Provision: Configuring Ops Assistant"
Write-Host "════════════════════════════════════════════════════"

$ProjectRoot = Split-Path -Parent $PSScriptRoot

# azd sets these from Bicep outputs automatically
$SqlServer      = $env:SQL_SERVER_FQDN
$SqlDb          = $env:SQL_DATABASE_NAME
$SqlServerName  = $env:SQL_SERVER_NAME
$StorageAccount = $env:AZURE_STORAGE_ACCOUNT_NAME
$ResourceGroup  = $env:AZURE_RESOURCE_GROUP_NAME
$CaName         = $env:SERVICE_OPSASSISTANT_NAME
$PrincipalId    = $env:SERVICE_OPSASSISTANT_PRINCIPAL_ID
$ClientId       = $env:SERVICE_OPSASSISTANT_CLIENT_ID
$AppUrl         = $env:SERVICE_OPSASSISTANT_URL
$SearchEndpoint = $env:AZURE_SEARCH_ENDPOINT
$SearchServiceName = $env:AZURE_SEARCH_SERVICE_NAME
$AiAccountName = $env:AZURE_AI_ACCOUNT_NAME
$UsePrivateEndpoints = $env:USE_PRIVATE_ENDPOINTS -eq 'true'

if (-not $SqlServerName) {
    $SqlServerName = $SqlServer.Split('.')[0]
}

if (-not $SearchServiceName -and $SearchEndpoint) {
    $SearchServiceName = ($SearchEndpoint -replace 'https://', '' -replace '\.search\.windows\.net/?', '')
}

# ── Pre-flight: Ensure sqlcmd is installed ──
$SqlcmdPath = Get-Command sqlcmd -ErrorAction SilentlyContinue
if (-not $SqlcmdPath) {
    Write-Host ""
    Write-Host "  ERROR: sqlcmd is required but not found." -ForegroundColor Red
    Write-Host "  Install the modern Go-based sqlcmd:"
    Write-Host "    winget install sqlcmd"
    Write-Host "  Or download from: https://learn.microsoft.com/sql/tools/sqlcmd/go-sqlcmd"
    Write-Host ""
    exit 1
}

# ── Step 0: Enable public access temporarily for PE-mode seeding ──
if ($UsePrivateEndpoints) {
    Write-Host ""
    Write-Host "Step 0: Private endpoints detected — temporarily enabling public access for seeding..."

    Write-Host "  Enabling public access on SQL Server '$SqlServerName'..."
    az sql server update `
        --resource-group $ResourceGroup `
        --name $SqlServerName `
        --set publicNetworkAccess=Enabled `
        --output none 2>&1
    Assert-LastExitCode "Failed to enable public access on SQL Server"

    Write-Host "  Enabling public access on Search service '$SearchServiceName'..."
    az search service update `
        --resource-group $ResourceGroup `
        --name $SearchServiceName `
        --public-access enabled `
        --output none 2>&1
    Assert-LastExitCode "Failed to enable public access on Search service"

    Write-Host "  Enabling public access on Storage account '$StorageAccount'..."
    az storage account update `
        --resource-group $ResourceGroup `
        --name $StorageAccount `
        --public-network-access Enabled `
        --default-action Allow `
        --output none 2>&1
    Assert-LastExitCode "Failed to enable public access on Storage account"

    Write-Host "  Public access enabled — waiting 30 seconds for propagation..."
    Start-Sleep -Seconds 30
}

# ── Step 1/4: Add SQL firewall rules for seeding ──
Write-Host ""
Write-Host "Step 1/4: Adding SQL firewall rules for seeding..."

$MyIp = (Invoke-RestMethod -Uri "https://api.ipify.org" -TimeoutSec 10)
az sql server firewall-rule create `
    --resource-group $ResourceGroup `
    --server $SqlServerName `
    --name "azd-deployer-temp" `
    --start-ip-address $MyIp `
    --end-ip-address $MyIp `
    --output none 2>&1
Assert-LastExitCode "Failed to create deployer firewall rule"

az sql server firewall-rule create `
    --resource-group $ResourceGroup `
    --server $SqlServerName `
    --name "AllowAllWindowsAzureIps" `
    --start-ip-address 0.0.0.0 `
    --end-ip-address 0.0.0.0 `
    --output none 2>&1
Assert-LastExitCode "Failed to create Azure IPs firewall rule"

Write-Host "  Firewall rules created (deployer IP: $MyIp + Azure services)"
Write-Host "  Waiting 30 seconds for propagation..."
Start-Sleep -Seconds 30

# ── Step 2/4: Seed the database ──
Write-Host ""
Write-Host "Step 2/4: Seeding database..."

Write-Host "  Applying schema to $SqlServer / $SqlDb..."
sqlcmd -S $SqlServer -d $SqlDb `
    --authentication-method=ActiveDirectoryDefault `
    -i "$ProjectRoot\database\schema.sql"
Assert-LastExitCode "Failed to apply database schema"

Write-Host "  Inserting seed data..."
sqlcmd -S $SqlServer -d $SqlDb `
    --authentication-method=ActiveDirectoryDefault `
    -i "$ProjectRoot\database\seed-data.sql"
Assert-LastExitCode "Failed to insert seed data"

Write-Host "  Database seeded"

# ── Step 3/4: Grant SQL access to the app's user-assigned managed identity ──
Write-Host ""
Write-Host "Step 3/4: Granting SQL access to Container App '$CaName'..."

# SQL External User SID must use the MI **client ID** (application ID), not the principal ID (object ID).
# Using principalId causes 'Login failed for user <token-identified principal>' at runtime.
$SqlSidSource = if ($ClientId) { $ClientId } else { $PrincipalId }

if (-not $SqlSidSource) {
    Write-Host "  WARNING: Neither SERVICE_OPSASSISTANT_CLIENT_ID nor SERVICE_OPSASSISTANT_PRINCIPAL_ID set — skipping SQL user grant" -ForegroundColor Yellow
} else {
    if (-not $ClientId) {
        Write-Host "  WARNING: SERVICE_OPSASSISTANT_CLIENT_ID not set, falling back to PRINCIPAL_ID — SQL auth may fail" -ForegroundColor Yellow
    }
    # Convert GUID to binary SID for SQL CREATE USER ... WITH SID
    # Must use Client ID (app ID), not Principal ID (object ID)
    $GuidBytes = [System.Guid]::Parse($SqlSidSource).ToByteArray()
    $SidHex = "0x" + [System.BitConverter]::ToString($GuidBytes).Replace("-", "")

    $SqlUserScript = @"
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '$CaName')
BEGIN
    CREATE USER [$CaName] WITH SID = $SidHex, TYPE = E;
    ALTER ROLE db_datareader ADD MEMBER [$CaName];
    ALTER ROLE db_datawriter ADD MEMBER [$CaName];
    PRINT 'Created SQL user for $CaName';
END
ELSE
BEGIN
    PRINT 'SQL user $CaName already exists';
END
"@
    $TempSql = [System.IO.Path]::GetTempFileName() + ".sql"
    $SqlUserScript | Out-File -FilePath $TempSql -Encoding utf8

    try {
        sqlcmd -S $SqlServer -d $SqlDb `
            --authentication-method=ActiveDirectoryDefault `
            -i $TempSql
        Assert-LastExitCode "sqlcmd failed to grant SQL access"

        Write-Host "  SQL access granted to '$CaName' (PrincipalId: $PrincipalId)"
    } catch {
        Write-Host "  WARNING: Could not grant SQL access - $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "  Run manually after deployment:"
        Write-Host "    CREATE USER [$CaName] WITH SID = $SidHex, TYPE = E;"
        Write-Host "    ALTER ROLE db_datareader ADD MEMBER [$CaName];"
        Write-Host "    ALTER ROLE db_datawriter ADD MEMBER [$CaName];"
    } finally {
        Remove-Item -Path $TempSql -ErrorAction SilentlyContinue
    }
}

# Clean up temporary deployer firewall rule (keep AllowAllWindowsAzureIps for app)
az sql server firewall-rule delete `
    --resource-group $ResourceGroup `
    --server $SqlServerName `
    --name "azd-deployer-temp" `
    --output none 2>&1 | Out-Null

# ── Step 4/4: Upload operational docs + create Search index ──
Write-Host ""
Write-Host "Step 4/4: Uploading docs and creating Search index..."

az storage blob upload-batch `
    --account-name $StorageAccount `
    --destination operational-docs `
    --source "$ProjectRoot\operational-docs" `
    --auth-mode login `
    --overwrite true `
    --output none 2>&1
Assert-LastExitCode "Failed to upload documents to blob storage"

Write-Host "  Documents uploaded to blob storage"

if ($SearchServiceName) {
    $AdminKey = (az search admin-key show `
        --service-name $SearchServiceName `
        --resource-group $ResourceGroup `
        --query primaryKey -o tsv)
    Assert-LastExitCode "Failed to retrieve Search admin key"

    $IndexName = "ops-assistant-kb"
    $ApiVersion = "2024-07-01"

    $IndexDef = @{
        name = $IndexName
        fields = @(
            @{ name = "id"; type = "Edm.String"; key = $true; searchable = $false; filterable = $true; retrievable = $true }
            @{ name = "content"; type = "Edm.String"; searchable = $true; retrievable = $true; analyzer = "en.lucene" }
            @{ name = "title"; type = "Edm.String"; searchable = $true; retrievable = $true; filterable = $true }
            @{ name = "source"; type = "Edm.String"; searchable = $false; retrievable = $true; filterable = $true }
        )
        semantic = @{
            defaultConfiguration = "default"
            configurations = @(
                @{
                    name = "default"
                    prioritizedFields = @{
                        titleField = @{ fieldName = "title" }
                        prioritizedContentFields = @(
                            @{ fieldName = "content" }
                        )
                    }
                }
            )
        }
    } | ConvertTo-Json -Depth 7

    $Headers = @{
        "Content-Type" = "application/json"
        "api-key"      = $AdminKey
    }

    # Delete existing index if present (idempotent re-run)
    try {
        Invoke-RestMethod `
            -Uri "$SearchEndpoint/indexes/${IndexName}?api-version=$ApiVersion" `
            -Method Delete `
            -Headers $Headers `
            -ErrorAction SilentlyContinue
    } catch { }

    Invoke-RestMethod `
            -Uri "$SearchEndpoint/indexes/${IndexName}?api-version=$ApiVersion" `
            -Method Put `
            -Headers $Headers `
            -Body $IndexDef | Out-Null

    Write-Host "  Search index '$IndexName' created/updated"
    # Index each operational doc
    $DocsPath = "$ProjectRoot\operational-docs"
    $Documents = @()

    foreach ($File in Get-ChildItem -Path $DocsPath -Filter "*.md") {
        $Content = Get-Content -Path $File.FullName -Raw -Encoding UTF8
        $DocId = $File.BaseName -replace '[^a-zA-Z0-9_-]', '_'

        $Documents += @{
            "@search.action" = "upload"
            id       = $DocId
            content  = $Content
            title    = ($File.BaseName -replace '-', ' ')
            source   = $File.Name
        }
    }

    if ($Documents.Count -gt 0) {
        $Batch = @{ value = $Documents } | ConvertTo-Json -Depth 5

        # Retry indexing with wait — search service may not be ready immediately after index creation
        $MaxRetries = 3
        $RetryDelay = 15
        for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
            try {
                Invoke-RestMethod `
                    -Uri "$SearchEndpoint/indexes/$IndexName/docs/index?api-version=$ApiVersion" `
                    -Method Post `
                    -Headers $Headers `
                    -Body ([System.Text.Encoding]::UTF8.GetBytes($Batch)) | Out-Null
                Write-Host "  Indexed $($Documents.Count) documents into '$IndexName'"
                break
            } catch {
                if ($attempt -lt $MaxRetries) {
                    Write-Host "  Search indexing attempt $attempt failed ($($_.Exception.Message)), retrying in ${RetryDelay}s..."
                    Start-Sleep -Seconds $RetryDelay
                } else {
                    throw $_
                }
            }
        }
    } else {
        Write-Host "  WARNING: No .md files found in $DocsPath"
    }

    # ── Step 4b: Create Knowledge Source + Knowledge Base for agentic retrieval ──
    Write-Host ""
    Write-Host "  Creating Knowledge Source + Knowledge Base for agentic retrieval..."

    $KBApiVersion = "2025-11-01-preview"
    $KBHeaders = @{
        "Content-Type"  = "application/json"
        "api-key"       = $AdminKey
        "Prefer"        = "return=representation"
    }
    $KSName = "operational-docs"

    # Get Azure OpenAI API key from the Foundry (Cognitive Services) account
    $AiKey = ""
    if ($AiAccountName) {
        $AiKey = (az cognitiveservices account keys list `
            --name $AiAccountName `
            --resource-group $ResourceGroup `
            --query key1 -o tsv 2>$null)
        if (-not $AiKey) {
            Write-Host "  WARNING: Could not retrieve AI Services key — KB model config will be incomplete" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  WARNING: AZURE_AI_ACCOUNT_NAME not set — KB model config will be incomplete" -ForegroundColor Yellow
    }

    $AiResourceUri = "https://${AiAccountName}.openai.azure.com/"

    # Create Knowledge Source (points to existing search index)
    $KSDef = @{
        name = $KSName
        kind = "searchIndex"
        description = "Ops Assistant operational documentation"
        searchIndexParameters = @{
            searchIndexName = $IndexName
            sourceDataFields = @(
                @{ name = "content" }
                @{ name = "title" }
            )
            searchFields = @(
                @{ name = "*" }
            )
        }
    } | ConvertTo-Json -Depth 5

    $MaxRetries = 3
    $RetryDelay = 10

    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        try {
            Invoke-RestMethod `
                -Uri "${SearchEndpoint}/knowledgesources('${KSName}')?api-version=${KBApiVersion}" `
                -Method Put `
                -Headers $KBHeaders `
                -Body ([System.Text.Encoding]::UTF8.GetBytes($KSDef)) | Out-Null
            Write-Host "  Knowledge Source '${KSName}' created"
            break
        } catch {
            if ($attempt -lt $MaxRetries) {
                Write-Host "  Knowledge Source creation attempt $attempt failed ($($_.Exception.Message)), retrying in ${RetryDelay}s..."
                Start-Sleep -Seconds $RetryDelay
            } else {
                Write-Host "  ERROR: Failed to create Knowledge Source after $MaxRetries attempts" -ForegroundColor Red
                throw $_
            }
        }
    }

    # Create Knowledge Base (references the knowledge source + model for query planning)
    $KBModelConfig = @()
    if ($AiKey -and $AiAccountName) {
        $KBModelConfig = @(
            @{
                kind = "azureOpenAI"
                azureOpenAIParameters = @{
                    resourceUri = $AiResourceUri
                    deploymentId = "gpt-4o"
                    apiKey = $AiKey
                    modelName = "gpt-4o"
                }
            }
        )
    }

    $KBDef = @{
        name = $IndexName
        description = "Ops Assistant knowledge base for operational documentation"
        knowledgeSources = @(
            @{ name = $KSName }
        )
    }
    if ($KBModelConfig.Count -gt 0) {
        $KBDef["models"] = $KBModelConfig
    }
    $KBDefJson = $KBDef | ConvertTo-Json -Depth 5

    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        try {
            Invoke-RestMethod `
                -Uri "${SearchEndpoint}/knowledgebases('${IndexName}')?api-version=${KBApiVersion}" `
                -Method Put `
                -Headers $KBHeaders `
                -Body ([System.Text.Encoding]::UTF8.GetBytes($KBDefJson)) | Out-Null
            Write-Host "  Knowledge Base '${IndexName}' created with model config"
            break
        } catch {
            if ($attempt -lt $MaxRetries) {
                Write-Host "  Knowledge Base creation attempt $attempt failed ($($_.Exception.Message)), retrying in ${RetryDelay}s..."
                Start-Sleep -Seconds $RetryDelay
            } else {
                Write-Host "  ERROR: Failed to create Knowledge Base after $MaxRetries attempts" -ForegroundColor Red
                throw $_
            }
        }
    }
} else {
    Write-Host "  WARNING: Search service name not found — skipping KB creation"
}

# ── Re-lock public access when running in PE mode ──
if ($UsePrivateEndpoints) {
    Write-Host ""
    Write-Host "Re-locking public access (private endpoint mode)..."

    az sql server update `
        --resource-group $ResourceGroup `
        --name $SqlServerName `
        --set publicNetworkAccess=Disabled `
        --output none 2>&1 | Out-Null
    Write-Host "  SQL Server public access disabled"

    az search service update `
        --resource-group $ResourceGroup `
        --name $SearchServiceName `
        --public-access disabled `
        --output none 2>&1 | Out-Null
    Write-Host "  Search service public access disabled"

    az storage account update `
        --resource-group $ResourceGroup `
        --name $StorageAccount `
        --public-network-access Disabled `
        --default-action Deny `
        --output none 2>&1 | Out-Null
    Write-Host "  Storage account public access disabled"
}

# ── Summary ──
Write-Host ""
Write-Host "════════════════════════════════════════════════════"
Write-Host "  Post-provision complete!"
Write-Host ""
Write-Host "  Database: seeded with schema + data"
Write-Host "  SQL access: granted to Container App MI"
Write-Host "  Blob storage: operational docs uploaded"
Write-Host "  Search index: 'ops-assistant-kb' created and indexed"
Write-Host "  Knowledge Base: agentic retrieval configured"
Write-Host ""
if ($AppUrl) {
    Write-Host "  App URL: $AppUrl"
}
Write-Host "════════════════════════════════════════════════════"