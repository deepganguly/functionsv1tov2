# Azure Functions v1 → v2 Migration Toolkit

## Purpose

Migrate Azure Function Apps from v1 (App Service / `Microsoft.Web/sites`) to v2 (Azure Functions on Container Apps / `Microsoft.App/containerApps` with `kind=functionapp`).

This toolkit provides inventory, single-app migration, and bulk migration capabilities.

## When to Use

- User says: "migrate function app", "function v1 to v2", "migrate to container apps", "list function apps", "migration inventory", "bulk migrate", "migration progress", "export migration plan"
- User needs to move Function Apps from App Service hosting to Azure Container Apps hosting
- User wants to track migration progress across a fleet of function apps

## Available Commands

### 1. Inventory & Progress

List all v1 function apps and check migration status:

```bash
# List all v1/v2 apps with progress %
python inventory.py --subscription-id <SUB_ID>

# Scan specific resource group
python inventory.py --subscription-id <SUB_ID> --resource-group <RG>

# Check progress against a target location
python inventory.py --subscription-id <SUB_ID> \
    --target-subscription-id <TARGET_SUB> --target-rg <TARGET_RG>

# Output as JSON (for programmatic consumption)
python inventory.py --subscription-id <SUB_ID> --json

# Export to CSV for bulk planning
python inventory.py --subscription-id <SUB_ID> --export-csv inventory.csv
```

**JSON output schema** (when using `--json`):
```json
{
  "summary": {
    "total_v1_apps": 12,
    "migrated": 5,
    "pending": 7,
    "progress_pct": 41.7
  },
  "v1_apps": [...],
  "v2_apps": [...]
}
```

### 2. Single App Migration

Migrate one function app from v1 to v2:

```bash
# Using Azure Portal links (recommended)
python migrate_function_app.py \
    --source-app-link "<PORTAL_LINK_TO_SOURCE_APP>" \
    --target-link "<PORTAL_LINK_TO_TARGET_RG>" \
    --target-app <TARGET_NAME>

# Using explicit IDs
python migrate_function_app.py \
    --source-subscription-id <SOURCE_SUB> \
    --source-rg <SOURCE_RG> \
    --source-app <SOURCE_APP> \
    --target-subscription-id <TARGET_SUB> \
    --target-rg <TARGET_RG> \
    --target-app <TARGET_APP> \
    --environment-id <MANAGED_ENV_ID>

# Export-only (no deploy)
python migrate_function_app.py \
    --source-subscription-id <SUB> \
    --source-rg <RG> \
    --source-app <APP> \
    --export-only
```

### 3. Bulk Migration

Migrate multiple apps from a CSV plan:

```bash
# Step 1: Export inventory to CSV
python inventory.py --subscription-id <SUB_ID> --export-csv migration_plan.csv

# Step 2: Edit the CSV — fill in target_subscription_id, target_resource_group,
#          target_app_name, target_environment_id columns

# Step 3: Dry-run to validate
python bulk_migrate.py --input-csv migration_plan.csv --dry-run

# Step 4: Execute
python bulk_migrate.py --input-csv migration_plan.csv
```

**CSV columns:**
| Column | Required | Description |
|--------|----------|-------------|
| source_app_name | Yes | v1 Function App name |
| source_resource_group | Yes | Source resource group |
| source_subscription_id | Yes | Source subscription |
| source_location | Info | Source region |
| migration_status | Info | Current status (Pending/Migrated) |
| target_subscription_id | For deploy | Target subscription |
| target_resource_group | For deploy | Target resource group |
| target_app_name | For deploy | Desired v2 app name |
| target_environment_id | Optional | Managed env ID (auto-discovered if one exists) |
| notes | Optional | Free-form notes |

## Orchestration Pattern (for Agent Use)

When orchestrating migrations programmatically:

1. **Discover** — Run `inventory.py --json` to get structured inventory
2. **Plan** — Export CSV, modify targets, validate with `bulk_migrate.py --dry-run`
3. **Execute** — Run `bulk_migrate.py --input-csv <file>`
4. **Verify** — Re-run `inventory.py --json` and check `progress_pct`

### Python Import (for in-process orchestration)

```python
from inventory import list_function_apps, compute_migration_status
from migrate_function_app import export_v1_metadata, transform_to_v2, deploy_v2_function_app
from migrate_function_app import _discover_environment_id, get_managed_environment_location
```

## Prerequisites

```bash
pip install -r requirements.txt
az login
```

Required packages: `azure-identity`, `azure-mgmt-web`, `azure-mgmt-resource`

## VNet Handling

The tool automatically:
- Detects if the source v1 app has regional VNet integration or gateway VNet integration
- Checks if the target managed environment is deployed into a VNet
- Warns if the source is VNet-integrated but the target environment is not

**Important:** Container Apps handle VNet at the managed environment level, not per-app.
If your source app uses VNet integration, ensure the target managed environment is deployed
into an appropriate subnet before running the migration.

## Limitations

- Does not migrate custom domains or TLS certificates (manual rebinding required)
- Does not recreate managed identity or RBAC assignments (manual follow-up)
- Networking/private endpoints require target environment to be pre-configured in a VNet
- Diagnostic settings and alerts need manual reattachment
