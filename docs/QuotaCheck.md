# Azure OpenAI Quota Check

Before deploying Ops Assistant, verify that your Azure subscription has sufficient Azure OpenAI quota in your target region.

## Required Quota

| Model | Minimum TPM (Tokens Per Minute) | Deployment Type | Used By |
|---|---|---|---|
| **GPT-4o** | 80K | Standard | Specialist agents (Operations, Diagnostics, Forecasting, Safety, Quality) |
| **GPT-4o-mini** | 30K | Standard | Triage agent |

## How to Check Your Quota

### Option 1: Azure Portal

1. Go to the [Azure Portal](https://portal.azure.com)
2. Search for **Azure OpenAI** and select your resource (or the region you plan to deploy to)
3. Navigate to **Management** → **Quotas**
4. Check the available TPM for **GPT-4o** and **GPT-4o-mini** in your target region

### Option 2: Azure CLI

```bash
# Check quota for a specific region
az cognitiveservices usage list \
  --location northcentralus \
  --query "[?name.value=='OpenAI.Standard.gpt-4o'].{Model:name.value, Current:currentValue, Limit:limit}" \
  -o table
```

### Option 3: Azure AI Foundry Portal

1. Go to [ai.azure.com](https://ai.azure.com)
2. Navigate to **Management** → **Quota**
3. Filter by your target region
4. Verify available capacity for GPT-4o and GPT-4o-mini

## Recommended Region

**North Central US** — This region provides full feature availability for Microsoft Foundry and Azure AI services used by this solution.

## If You Don't Have Enough Quota

1. **Request a quota increase** via the Azure Portal:
   - Go to **Azure OpenAI** → **Quotas** → select the model → **Request Quota Increase**
   - Or submit a request at [https://aka.ms/oai/quotaincrease](https://aka.ms/oai/quotaincrease)

2. **Try a different region** — Quota availability varies by region. Check [Azure Products by Region](https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/?products=all&regions=all) for alternatives.

3. **Reduce the deployment capacity** — You can modify the GPT-4o capacity in `infra/modules/foundry.bicep` (default: 80 TPM). Lower values reduce throughput but may fit within your available quota.

## Next Steps

Once you've confirmed sufficient quota, proceed with deployment:

- [Deployment Guide](./DEPLOYMENT.md)
- [Back to README](../README.md)
