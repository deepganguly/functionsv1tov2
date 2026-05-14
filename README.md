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

## Advantages of Same-Subscription Migrations

- **Dependency Reuse**: Existing resources such as storage accounts, service bus, and app insights can be reused without additional configuration.
- **Identity and RBAC**: Managed identities and role assignments are preserved, reducing manual intervention.
- **Networking**: VNet integrations and private endpoints remain intact, ensuring seamless connectivity.
- **Cost Efficiency**: Avoids duplication of resources, leading to reduced operational costs.

## Points to Note

For same-subscription migrations, the following configurations and resources can be preserved or reused:

- **Identity**: Managed identity assignments and RBAC roles are preserved, avoiding the need for reconfiguration.
- **Networking**: VNet integrations, private endpoints, IP restrictions, and NSGs remain intact, ensuring seamless connectivity.
- **Key Vault References**: Key Vault references can be reused if the Key Vault exists in the same subscription and the target app has the necessary access permissions.
- **Connection Strings**: Connection strings can be reused if the referenced resources (e.g., databases, storage accounts) are in the same subscription and accessible from the target environment.
- **Diagnostic Settings and Alerts**: Diagnostic settings and alerts can be preserved if the monitoring resources (e.g., Log Analytics workspace, Application Insights) are in the same subscription.
- **Custom Domains and Certificates**: Custom domains and certificates can be reused if the DNS and certificate resources are managed within the same subscription.
