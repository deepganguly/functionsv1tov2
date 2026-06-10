# Azure Function App v1 → v2 Migration Toolkit

## Problem

Azure Functions v1 (hosted on App Service / `Microsoft.Web/sites`) is approaching end-of-life. Teams need to migrate these function apps to the newer **Azure Functions on Azure Container Apps** (`Microsoft.App/containerApps` with `kind=functionapp`) — referred to here as "v2".

Doing this manually is painful:

- You must export the existing app's metadata, app settings, and site configuration.
- App settings contain secrets and connection strings that need to be mapped to Container Apps secrets.
- The resource model changes entirely — from `Microsoft.Web/sites` to `Microsoft.App/containerApps` — so you can't simply redeploy.
- Ingress, networking, identity, and RBAC don't carry over automatically.
- Different subscriptions, resource groups, or regions add further complexity.

There is no first-party tooling today that handles this end-to-end.

## What This Toolkit Does

| Script | Purpose |
|--------|---------|
| `inventory.py` | List all v1/v2 function apps, show migration progress %, export CSV |
| `migrate_function_app.py` | Migrate a single function app (export → transform → deploy) |
| `bulk_migrate.py` | Run migrations in batch from a CSV plan |
| `SKILL.md` | Agent skill file for Copilot/Claude orchestration |

---

## 1) Install

```bash
pip install -r requirements.txt
az login
```

---

## 2) Inventory & Migration Progress

Scan a subscription to find all v1 function apps and check which have been migrated:

```bash
# List all with progress bar
python inventory.py --subscription-id <SUB_ID>

# Limit to a resource group
python inventory.py --subscription-id <SUB_ID> --resource-group <RG>

# Check against a target subscription/RG for v2 counterparts
python inventory.py --subscription-id <SUB_ID> \
    --target-subscription-id <TARGET_SUB> --target-rg <TARGET_RG>

# JSON output (for programmatic use / agent orchestration)
python inventory.py --subscription-id <SUB_ID> --json

# Export CSV for bulk migration planning
python inventory.py --subscription-id <SUB_ID> --export-csv migration_plan.csv
```

Sample output:

```
  Migration Progress: [████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 30.0%
  Total v1 Apps: 10 | Migrated: 3 | Pending: 7
```

---

## 3) Single App Migration

### Using Portal links (recommended)

```bash
python migrate_function_app.py \
  --source-app-link "https://ms.portal.azure.com/#@microsoft.onmicrosoft.com/resource/subscriptions/<SOURCE_SUB>/resourceGroups/<SOURCE_RG>/providers/Microsoft.Web/sites/<SOURCE_APP>/appServices" \
  --target-link "https://ms.portal.azure.com/#@microsoft.onmicrosoft.com/resource/subscriptions/<TARGET_SUB>/resourceGroups/<TARGET_RG>/overview" \
  --target-app funcacav1-v2-prod-eus
```

What the script auto-resolves from links:
- Source subscription ID, resource group, app name
- Target subscription ID, resource group
- Managed environment ID (auto if exactly one exists in target resource group)

If more than one managed environment exists, pass `--environment-id` explicitly.

### Explicit mode

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

### Export-only (no deploy)

```bash
python migrate_function_app.py \
  --source-subscription-id <SUB> --source-rg <RG> --source-app <APP> \
  --export-only
```

---

## 4) Bulk Migration (CSV-driven)

For migrating multiple apps at once:

```bash
# Step 1: Generate the plan CSV
python inventory.py --subscription-id <SUB_ID> --export-csv migration_plan.csv

# Step 2: Edit the CSV
#   Fill in: target_subscription_id, target_resource_group, target_app_name
#   Optionally: target_environment_id (auto-discovered if omitted)

# Step 3: Dry-run (validate without deploying)
python bulk_migrate.py --input-csv migration_plan.csv --dry-run

# Step 4: Execute
python bulk_migrate.py --input-csv migration_plan.csv
```

The bulk tool prints a live progress bar, tracks success/failure per app, and writes results to `bulk_migration_results.json`.

---

## 5) VNet Handling

The tool automatically detects VNet integration on the source v1 app:

- **Regional VNet integration** (swift connection) — detects the delegated subnet
- **Gateway-required VNet integration** (legacy) — detects the VNet resource ID

**How Container Apps handle networking:**
Container Apps manage VNet at the *managed environment* level, not per-app. The migration tool:
1. Detects if source has VNet integration
2. Checks if target managed environment is deployed into a VNet
3. Warns if there's a mismatch (source is VNet-integrated, target env is not)

**Action required:** If your source app uses VNet integration, ensure the target managed environment is deployed into an appropriate subnet *before* running migration.

---

## 6) Agent Orchestration (SKILL.md)

The `SKILL.md` file allows Copilot, Claude, or other AI agents to discover and invoke this toolkit. Agents can:

1. Run `inventory.py --json` to get structured inventory
2. Export a CSV, validate with `--dry-run`, then execute bulk migration
3. Re-run inventory to verify progress

For in-process Python orchestration:

```python
from inventory import list_function_apps, compute_migration_status
from migrate_function_app import export_v1_metadata, transform_to_v2, deploy_v2_function_app
```

---

## Notes

- Deploys to `Microsoft.App/containerApps` with `kind=functionapp`
- Preserves app settings (secrets auto-mapped to Container Apps secrets)
- Preserves ingress behavior based on source public network access
- Supports same-subscription and cross-subscription migration

## Same vs Different Subscription: What Is Possible

The script always migrates app metadata and deploys a new target Function App on Azure Container Apps. Other resources depend on migration type.

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
