# Azure Function App v1 -> v2 Migration Tool

Simple flow: pass Azure Portal links, app name, and run.

## 1) Install

```bash
pip install -r requirements.txt
az login
```

## 2) Run with links (recommended)

Use the same style you shared:
- source app link (Microsoft.Web/sites/...)
- target link (resource group overview is enough)

```bash
python migrate_function_app.py \
  --source-app-link "https://ms.portal.azure.com/#@microsoft.onmicrosoft.com/resource/subscriptions/<SOURCE_SUB>/resourceGroups/<SOURCE_RG>/providers/Microsoft.Web/sites/<SOURCE_APP>/appServices" \
  --target-link "https://ms.portal.azure.com/#@microsoft.onmicrosoft.com/resource/subscriptions/<TARGET_SUB>/resourceGroups/<TARGET_RG>/overview" \
  --target-app funcacav1-v2-prod-eus
```

What the script auto-resolves from links:
- Source subscription ID
- Source resource group
- Source app name
- Target subscription ID
- Target resource group
- Managed environment ID (auto if exactly one exists in target resource group)

If more than one managed environment exists, pass `--environment-id` explicitly.

## 3) Optional explicit mode

```bash
python migrate_function_app.py \
  --source-subscription-id <SOURCE_SUB> \
  --source-rg <SOURCE_RG> \
  --source-app <SOURCE_APP> \
  --target-subscription-id <TARGET_SUB> \
  --target-rg <TARGET_RG> \
  --target-app funcacav1-v2-prod-eus \
  --environment-id /subscriptions/<TARGET_SUB>/resourceGroups/<TARGET_RG>/providers/Microsoft.App/managedEnvironments/<ENV_NAME>
```

## Notes

- Deploys to `Microsoft.App/containerApps` with `kind=functionapp`.
- Preserves app settings.
- Preserves ingress behavior by enabling external ingress when source app is publicly reachable.

## Same vs Different Subscription: What Is Possible

The script always migrates app metadata and deploys a new target Function App on Azure Container Apps. Other resources depend on migration type.

### Current Script Behavior (Automatic)

- Exports source Function App metadata and app settings.
- Transforms settings for v2 target shape.
- Deploys target app as `Microsoft.App/containerApps` with `kind=functionapp`.
- Preserves ingress default behavior based on source public reachability.

### Capability Matrix

| Area | Same Subscription | Different Subscription |
|---|---|---|
| App settings migration | Yes (automatic) | Yes (automatic) |
| Metadata export/transform/deploy | Yes (automatic) | Yes (automatic) |
| Reuse existing dependencies (Storage, Service Bus, App Insights) | Yes (possible if target has access) | Limited (usually requires reconfiguration/new references) |
| Managed identity and RBAC continuity | Possible, but manual follow-up required | Not direct; manual recreation required |
| Networking reuse (VNet/private endpoints/NSG/IP restrictions) | Possible, but manual follow-up required | Usually not reusable directly; manual redesign/recreation required |
| Key Vault reference reuse | Possible if same vault and permissions are available | Usually requires new permissions/references in target subscription |
| Connection strings to existing resources | Possible with existing reachable resources | Possible only after updating endpoints/permissions as needed |
| Diagnostic settings and alerts continuity | Possible with manual reattachment | Manual recreation/reattachment required |
| Custom domains and certificates reuse | Possible with manual binding validation | Manual rebinding/validation required |

### Points to Note

- Same-subscription migration is generally preferred because resource reuse is easier.
- Different-subscription migration is supported for the app deployment flow, but shared dependencies usually require explicit remapping.
- If resources are private or identity-protected, validate RBAC and networking after migration.
