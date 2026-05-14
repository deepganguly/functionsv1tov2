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

## Caveats: What Is Not Fully Cloned

This tool is a metadata migration helper, not a full infrastructure clone.

### Cloned Today

- Basic app metadata: name, location alignment, tags.
- App settings: exported from source and applied to target.
- Ingress default behavior: external ingress enabled when source app appears publicly reachable.

### Not Fully Cloned (Manual Follow-up Required)

- Scale rules: only default scale is set (`minReplicas=0`, `maxReplicas=10`).
- KEDA/custom scale triggers: not copied.
- Dapr settings: not copied (`dapr.enabled`, appId, components, pub/sub bindings).
- Identity: managed identity assignments and RBAC are not copied.
- Networking: VNet integration, private endpoints, IP restrictions, NSGs are not copied.
- AuthN/AuthZ: App Service auth settings (EasyAuth) are not migrated.
- Custom domains and certificates: not copied.
- Connection strings object: App Service connection strings are not exported as a dedicated section.
- Key Vault references: not converted to target secret references automatically.
- Deployment artifacts/code package: function code content is not cloned from source site filesystem.
- Slots and slot-specific settings: not migrated.
- Diagnostic settings and alerts: not cloned.

### Secrets Behavior

- App settings with names containing `secret`, `password`, `token`, `key`, `connection`, or `connstr` are converted to Container Apps secrets.
- Other app settings are stored as plain environment variables.
- Secret names are sanitized and truncated for Container Apps naming rules; review for collisions in edge cases.
- If you use Key Vault-backed references, reconfigure them explicitly after migration.

### Dependencies Caveat

- External dependencies (storage accounts, service bus, event hubs, databases, app insights resource wiring) are not recreated.
- The migrated app assumes those dependencies already exist and are reachable from the target environment.

## Points to Note

For same-subscription migrations, the following configurations and resources can be preserved or reused:

- **Identity**: Managed identity assignments and RBAC roles are preserved, avoiding the need for reconfiguration.
- **Networking**: VNet integrations, private endpoints, IP restrictions, and NSGs remain intact, ensuring seamless connectivity.
- **Key Vault References**: Key Vault references can be reused if the Key Vault exists in the same subscription and the target app has the necessary access permissions.
- **Connection Strings**: Connection strings can be reused if the referenced resources (e.g., databases, storage accounts) are in the same subscription and accessible from the target environment.
- **Diagnostic Settings and Alerts**: Diagnostic settings and alerts can be preserved if the monitoring resources (e.g., Log Analytics workspace, Application Insights) are in the same subscription.
- **Custom Domains and Certificates**: Custom domains and certificates can be reused if the DNS and certificate resources are managed within the same subscription.
