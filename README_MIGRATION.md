# Azure Function App v1 → v2 Migration Tool

This tool provides a complete workflow to export Azure Function App v1 metadata and deploy it as v2 in Azure Container Apps.

## Components

### 1. `export_and_transform_metadata.py`
Exports v1 Function App metadata from Azure and transforms it to v2-compatible format.

**Usage:**
```bash
python export_and_transform_metadata.py \
  --subscription-id <SUBSCRIPTION_ID> \
  --resource-group <RESOURCE_GROUP> \
  --app-name <V1_APP_NAME> \
  --output-file v2_metadata.json
```

**Output:** JSON file with both v1 and v2 metadata

### 2. `deploy_v2_function_app.py`
Deploys a v2 Function App using transformed metadata.

**Usage:**
```bash
python deploy_v2_function_app.py \
  --subscription-id <SUBSCRIPTION_ID> \
  --resource-group <TARGET_RESOURCE_GROUP> \
  --metadata-file v2_metadata.json \
  --environment-id /subscriptions/.../managedEnvironments/myenv
```

### 3. `migrate_function_app.py` (Master Script)
Orchestrates the complete workflow in one command:
- Exports v1 metadata
- Transforms to v2 format
- Deploys the v2 Function App
- Applies app settings

**Usage (Complete Migration):**
```bash
python migrate_function_app.py \
  --subscription-id <SUBSCRIPTION_ID> \
  --source-rg <SOURCE_RG> \
  --source-app <V1_APP_NAME> \
  --target-rg <TARGET_RG> \
  --target-app <V2_APP_NAME> \
  --environment-id /subscriptions/.../managedEnvironments/myenv
```

**Usage (Export Only):**
```bash
python migrate_function_app.py \
  --subscription-id <SUBSCRIPTION_ID> \
  --source-rg <SOURCE_RG> \
  --source-app <V1_APP_NAME> \
  --export-only \
  --output-file v2_metadata.json
```

## Prerequisites

1. **Python 3.8+**

2. **Install Azure SDK:**
   ```bash
   pip install azure-identity azure-mgmt-web azure-mgmt-resource
   ```

3. **Azure CLI Authentication:**
   ```bash
   az login
   ```
   Or use service principal/managed identity for authentication.

4. **Required Permissions:**
   - Read access to the source Function App
   - Write access to create new Function App in target resource group

## Data Transformations

### v1 → v2 Metadata Changes

| Field | v1 | v2 |
|-------|-----|-----|
| `kind` | null or "functionapp" | "functioncontainerapp" |
| `managed_by` | null or "Microsoft.Web" | "Microsoft.App" |
| `FUNCTIONS_EXTENSION_VERSION` | ~1, ~2, or ~3 | ~4 |
| `managedEnvironmentId` | N/A | Required for Container Apps |
| Container Runtime | Process-based | Container-based |

### App Settings Transformations

- **FUNCTIONS_EXTENSION_VERSION**: Automatically updated to `~4`
- **Node Version**: Updated from v14 to v18 (if applicable)
- **Other settings**: Preserved as-is

## Sample Metadata

See `sample_export.json` for a complete example of v1 and transformed v2 metadata.

## Workflow

### Step 1: Export v1 Metadata
```bash
python migrate_function_app.py \
  --subscription-id <SUB_ID> \
  --source-rg myresourcegroup \
  --source-app my-function-app-v1 \
  --export-only
```

Output: `v2_metadata.json` with both v1 and v2 metadata

### Step 2: Review Metadata (Optional)
Open `v2_metadata.json` and verify the transformation. Modify if needed.

### Step 3: Deploy v2 Function App
```bash
python migrate_function_app.py \
  --subscription-id <SUB_ID> \
  --source-rg myresourcegroup \
  --source-app my-function-app-v1 \
  --target-rg myresourcegroup \
  --target-app my-function-app-v2 \
  --environment-id /subscriptions/.../managedEnvironments/myenv
```

## Advanced Usage

### Custom Target App Name
```bash
python migrate_function_app.py \
  --subscription-id <SUB_ID> \
  --source-rg myresourcegroup \
  --source-app my-function-app-v1 \
  --target-app my-custom-v2-name \
  --environment-id <ENV_ID>
```

### Different Target Resource Group
```bash
python migrate_function_app.py \
  --subscription-id <SUB_ID> \
  --source-rg source-rg \
  --source-app my-app-v1 \
  --target-rg target-rg \
  --environment-id <ENV_ID>
```

### Using Service Principal
```bash
export AZURE_CLIENT_ID=<CLIENT_ID>
export AZURE_CLIENT_SECRET=<CLIENT_SECRET>
export AZURE_TENANT_ID=<TENANT_ID>

python migrate_function_app.py \
  --subscription-id <SUB_ID> \
  --source-rg myresourcegroup \
  --source-app my-function-app-v1 \
  --environment-id <ENV_ID>
```

## Key Features

✅ **Zero-Downtime Export**: Exports metadata without modifying source app
✅ **Automatic Transformations**: Handles v1→v2 API differences
✅ **App Settings Management**: Preserves and transforms app settings
✅ **Managed Environment Support**: Integrates with Azure Container Apps
✅ **Error Handling**: Comprehensive error messages and validation
✅ **Flexible Workflow**: Export-only or complete migration in one command

## Troubleshooting

### Authentication Errors
```
Error: 'DefaultAzureCredential' has no attribute 'get_token'
```
**Solution**: Ensure you've logged in with `az login`

### Resource Not Found
```
Error: Function App 'my-app' not found in 'my-rg'
```
**Solution**: Verify the app name and resource group are correct

### Managed Environment Required
```
Error: --environment-id is required for deployment
```
**Solution**: Provide a valid Container Apps managed environment ID for deployment

## Next Steps

After deployment, you can:

1. **Configure triggers and bindings** using the Azure Portal or Azure Functions Core Tools
2. **Deploy your code** to the new v2 Function App
3. **Update connection strings** and secrets in Key Vault
4. **Monitor** the new app with Application Insights

## Support

For issues or questions, refer to:
- [Azure Functions Container Apps Documentation](https://learn.microsoft.com/en-us/azure/azure-functions/container-apps-intro)
- [Azure SDK for Python Documentation](https://docs.microsoft.com/python/api/azure-identity/)
