#!/usr/bin/env python3
"""
Inventory and migration progress tracker.

Lists all v1 Function Apps (Microsoft.Web/sites with kind containing 'functionapp')
and checks which have been migrated to v2 (Microsoft.App/containerApps with kind=functionapp).

Usage:
    # List all v1 function apps in a subscription
    python inventory.py --subscription-id <SUB_ID>

    # List in a specific resource group
    python inventory.py --subscription-id <SUB_ID> --resource-group <RG>

    # Export inventory to CSV for bulk migration planning
    python inventory.py --subscription-id <SUB_ID> --export-csv inventory.csv

    # Check progress against a target subscription/RG
    python inventory.py --subscription-id <SUB_ID> \
        --target-subscription-id <TARGET_SUB> --target-rg <TARGET_RG>
"""

import argparse
import csv
import json
import sys
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.web import WebSiteManagementClient


def _is_function_app_v1(resource):
    """Check if a resource is a v1 Function App (Microsoft.Web/sites)."""
    kind = (getattr(resource, "kind", "") or "").lower()
    resource_type = (getattr(resource, "type", "") or "").lower()
    return resource_type == "microsoft.web/sites" and "functionapp" in kind


def _is_function_app_v2(resource):
    """Check if a resource is a v2 Function App on Container Apps."""
    kind = (getattr(resource, "kind", "") or "").lower()
    resource_type = (getattr(resource, "type", "") or "").lower()
    return resource_type == "microsoft.app/containerapps" and "functionapp" in kind


def list_function_apps(subscription_id, resource_group=None):
    """List all function apps (v1 and v2) in a subscription or resource group."""
    credential = DefaultAzureCredential()
    resource_client = ResourceManagementClient(credential, subscription_id)

    v1_apps = []
    v2_apps = []

    if resource_group:
        resources = resource_client.resources.list_by_resource_group(resource_group)
    else:
        resources = resource_client.resources.list()

    for resource in resources:
        if _is_function_app_v1(resource):
            v1_apps.append({
                "name": resource.name,
                "resource_group": _extract_rg_from_id(resource.id),
                "location": resource.location,
                "kind": resource.kind,
                "id": resource.id,
                "tags": resource.tags or {},
            })
        elif _is_function_app_v2(resource):
            v2_apps.append({
                "name": resource.name,
                "resource_group": _extract_rg_from_id(resource.id),
                "location": resource.location,
                "kind": resource.kind,
                "id": resource.id,
                "tags": resource.tags or {},
            })

    return v1_apps, v2_apps


def _extract_rg_from_id(resource_id):
    """Extract resource group name from a resource ID."""
    if not resource_id:
        return ""
    parts = resource_id.split("/")
    for i, part in enumerate(parts):
        if part.lower() == "resourcegroups" and i + 1 < len(parts):
            return parts[i + 1]
    return ""


def get_vnet_integration(subscription_id, resource_group, app_name):
    """Check if a v1 function app has VNet integration configured."""
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)

    try:
        vnet_info = web_client.web_apps.get_vnet_connection(resource_group, app_name, "primary")
        return getattr(vnet_info, "vnet_resource_id", None)
    except Exception:
        pass

    # Check swift (regional VNet integration)
    try:
        site_config = web_client.web_apps.get_configuration(resource_group, app_name)
        # vnet_route_all_enabled indicates regional VNet integration
        if getattr(site_config, "vnet_route_all_enabled", False):
            return "regional-vnet-integration-enabled"
    except Exception:
        pass

    return None


def compute_migration_status(v1_apps, v2_apps):
    """Match v1 apps to v2 counterparts and compute migration status."""
    v2_names = {app["name"].lower() for app in v2_apps}

    results = []
    for app in v1_apps:
        name = app["name"]
        # Check common naming patterns for migrated apps
        migrated = False
        matched_v2 = None
        candidates = [
            name.lower(),
            f"{name}-v2".lower(),
            f"{name}v2".lower(),
            name.lower().replace("-v1", "-v2"),
            name.lower().replace("v1", "v2"),
        ]
        for candidate in candidates:
            if candidate in v2_names:
                migrated = True
                matched_v2 = candidate
                break

        # Also check tags for migration tracking
        if not migrated:
            for v2_app in v2_apps:
                source_tag = (v2_app.get("tags") or {}).get("migrated-from", "").lower()
                if source_tag == name.lower():
                    migrated = True
                    matched_v2 = v2_app["name"]
                    break

        results.append({
            **app,
            "migrated": migrated,
            "v2_name": matched_v2,
            "status": "Migrated" if migrated else "Pending",
        })

    return results


def print_inventory(results, v2_apps):
    """Print inventory table with migration progress."""
    total = len(results)
    migrated = sum(1 for r in results if r["migrated"])
    pending = total - migrated
    pct = (migrated / total * 100) if total > 0 else 0

    print("=" * 80)
    print("Azure Function Apps — Migration Inventory")
    print("=" * 80)
    print()

    # Progress bar
    bar_width = 40
    filled = int(bar_width * pct / 100)
    bar = "█" * filled + "░" * (bar_width - filled)
    print(f"  Migration Progress: [{bar}] {pct:.1f}%")
    print(f"  Total v1 Apps: {total} | Migrated: {migrated} | Pending: {pending}")
    print(f"  v2 Apps Found: {len(v2_apps)}")
    print()

    # Table header
    print(f"  {'Status':<10} {'App Name':<35} {'Resource Group':<25} {'Location':<15} {'v2 Name':<30}")
    print(f"  {'─' * 10} {'─' * 35} {'─' * 25} {'─' * 15} {'─' * 30}")

    for r in sorted(results, key=lambda x: (x["migrated"], x["name"])):
        status_icon = "✓" if r["migrated"] else "○"
        status = f"{status_icon} {r['status']}"
        v2_name = r["v2_name"] or "—"
        print(f"  {status:<10} {r['name']:<35} {r['resource_group']:<25} {r['location']:<15} {v2_name:<30}")

    print()
    print("=" * 80)


def export_csv(results, output_file):
    """Export inventory to CSV with columns for bulk migration planning."""
    fieldnames = [
        "source_app_name",
        "source_resource_group",
        "source_subscription_id",
        "source_location",
        "migration_status",
        "target_subscription_id",
        "target_resource_group",
        "target_app_name",
        "target_environment_id",
        "notes",
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "source_app_name": r["name"],
                "source_resource_group": r["resource_group"],
                "source_subscription_id": r.get("subscription_id", ""),
                "source_location": r["location"],
                "migration_status": r["status"],
                "target_subscription_id": "",  # User fills in
                "target_resource_group": "",  # User fills in
                "target_app_name": f"{r['name']}-v2",  # Default suggestion
                "target_environment_id": "",  # User fills in
                "notes": "",
            })

    print(f"✓ Exported {len(results)} apps to {output_file}")
    print(f"  Edit the CSV to fill in target_subscription_id, target_resource_group,")
    print(f"  target_app_name, and target_environment_id columns, then run:")
    print(f"  python bulk_migrate.py --input-csv {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="List v1/v2 Function Apps and track migration progress",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--subscription-id", required=True, help="Azure subscription ID to scan")
    parser.add_argument("--resource-group", help="Limit scan to a specific resource group")
    parser.add_argument("--target-subscription-id", help="Target subscription to check for v2 apps")
    parser.add_argument("--target-rg", help="Target resource group to check for v2 apps")
    parser.add_argument("--export-csv", help="Export inventory to CSV file for bulk migration")
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of table")

    args = parser.parse_args()

    print(f"\nScanning subscription {args.subscription_id}...")
    v1_apps, v2_apps = list_function_apps(args.subscription_id, args.resource_group)

    # Also scan target subscription/RG if provided
    if args.target_subscription_id:
        target_rg = args.target_rg
        _, target_v2_apps = list_function_apps(args.target_subscription_id, target_rg)
        v2_apps.extend(target_v2_apps)

    # Add subscription_id to each app for CSV export
    for app in v1_apps:
        app["subscription_id"] = args.subscription_id

    # Compute status
    results = compute_migration_status(v1_apps, v2_apps)

    if args.json:
        total = len(results)
        migrated = sum(1 for r in results if r["migrated"])
        output = {
            "summary": {
                "total_v1_apps": total,
                "migrated": migrated,
                "pending": total - migrated,
                "progress_pct": round((migrated / total * 100) if total > 0 else 0, 1),
            },
            "v1_apps": results,
            "v2_apps": v2_apps,
        }
        print(json.dumps(output, indent=2))
    elif args.export_csv:
        export_csv(results, args.export_csv)
    else:
        print_inventory(results, v2_apps)


if __name__ == "__main__":
    main()
