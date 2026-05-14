#!/usr/bin/env python3
"""
Complete workflow: Export v1 Function App metadata and deploy as v2.

This script orchestrates the entire process:
1. Export v1 Function App metadata from Azure
2. Transform it to v2-compatible format
3. Deploy the v2 Function App

Usage:
    python migrate_function_app.py \
        --source-subscription-id <SOURCE_SUBSCRIPTION_ID> \
        --target-subscription-id <TARGET_SUBSCRIPTION_ID> \
        --source-rg <SOURCE_RG> \
        --source-app <SOURCE_APP_NAME> \
        --target-rg <TARGET_RG> \
        --environment-id <MANAGED_ENV_ID>
"""

import argparse
import json
import sys
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.web import WebSiteManagementClient
from azure.core.exceptions import ResourceNotFoundError

def export_v1_metadata(subscription_id, resource_group, app_name):
    """Export v1 Function App metadata."""
    print(f"\n[Step 1] Exporting v1 metadata from {app_name}...")
    
    try:
        credential = DefaultAzureCredential()
        client = WebSiteManagementClient(credential, subscription_id)
        app = client.web_apps.get(resource_group, app_name)
        app_settings_obj = client.web_apps.list_application_settings(resource_group, app_name)
        app_settings = []
        if app_settings_obj and getattr(app_settings_obj, "properties", None):
            for setting_name, setting_value in app_settings_obj.properties.items():
                app_settings.append({"name": setting_name, "value": setting_value})

        site_config = app.site_config.as_dict() if app.site_config else {}
        site_config["app_settings"] = app_settings

        v1_metadata = {
            "name": app.name,
            "location": app.location,
            "kind": app.kind,
            "managed_by": getattr(app, "managed_by", None),
            "tags": app.tags or {},
            "properties": {
                "server_farm_id": app.server_farm_id,
                "reserved": app.reserved,
                "is_xenon": app.is_xenon,
                "hyper_v": app.hyper_v,
                "site_config": site_config,
            },
        }

        print(f"✓ Exported metadata for {app_name}")
        return v1_metadata

    except ResourceNotFoundError:
        print(f"✗ Function App {app_name} not found in {resource_group}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error exporting metadata: {e}")
        sys.exit(1)

def transform_to_v2(v1_metadata, target_app_name=None, target_location=None):
    """Transform v1 metadata to v2 format."""
    print(f"\n[Step 2] Transforming metadata to v2 format...")

    source_kind = (v1_metadata.get("kind") or "").lower()
    target_kind = v1_metadata.get("kind") if "azurecontainerapps" in source_kind else "functionapp"

    v2_metadata = {
        "name": target_app_name or v1_metadata["name"],
        "location": target_location or v1_metadata["location"],
        "kind": target_kind,
        "managed_by": "Microsoft.App",
        "tags": v1_metadata.get("tags", {}),
        "properties": {
            "server_farm_id": v1_metadata["properties"]["server_farm_id"],
            "reserved": True,
            "is_xenon": v1_metadata["properties"]["is_xenon"],
            "hyper_v": v1_metadata["properties"]["hyper_v"],
            "site_config": transform_site_config(v1_metadata["properties"]["site_config"]),
        },
        "deployment_properties": {
            "container_image": "mcr.microsoft.com/azure-functions/node:4-node18",
            "workload_profile_name": "Consumption"
        }
    }

    print(f"✓ Transformed to v2 format")
    print(f"  - kind: {v2_metadata['kind']}")
    print(f"  - managed_by: {v2_metadata['managed_by']}")

    return v2_metadata

def get_managed_environment_location(subscription_id, environment_id):
    """Return the managed environment location so app create uses a matching region."""
    credential = DefaultAzureCredential()
    resource_client = ResourceManagementClient(credential, subscription_id)

    for api_version in ["2024-03-01", "2023-05-01", "2022-11-01-preview"]:
        try:
            resource = resource_client.resources.get_by_id(environment_id, api_version)
            if getattr(resource, "location", None):
                return resource.location
        except Exception:
            continue

    return None

def transform_site_config(v1_site_config):
    """Transform v1 site configuration to v2."""
    if not v1_site_config:
        return {}

    v2_config = {
        "number_of_workers": v1_site_config.get("number_of_workers", v1_site_config.get("numberOfWorkers", 1)),
        "net_framework_version": v1_site_config.get("net_framework_version", v1_site_config.get("netFrameworkVersion", "v4.0")),
        "python_version": v1_site_config.get("python_version", v1_site_config.get("pythonVersion", "")),
        "node_version": v1_site_config.get("node_version", v1_site_config.get("nodeVersion", "")),
        "linux_fx_version": v1_site_config.get("linux_fx_version", v1_site_config.get("linuxFxVersion", "")),
        "use32_bit_worker_process": v1_site_config.get("use32_bit_worker_process", v1_site_config.get("use32BitWorkerProcess", True)),
        "web_sockets_enabled": v1_site_config.get("web_sockets_enabled", v1_site_config.get("webSocketsEnabled", False)),
        "managed_pipeline_mode": v1_site_config.get("managed_pipeline_mode", v1_site_config.get("managedPipelineMode", "Integrated")),
        "app_settings": transform_app_settings(v1_site_config.get("app_settings", v1_site_config.get("appSettings", []))),
    }

    return v2_config

def transform_app_settings(v1_app_settings):
    """Transform app settings from v1 to v2."""
    if not v1_app_settings:
        return []

    v2_settings = []
    for setting in v1_app_settings:
        name = setting.get("name", "")
        value = setting.get("value", "")

        # Update FUNCTIONS_EXTENSION_VERSION to v4
        if name == "FUNCTIONS_EXTENSION_VERSION":
            value = "~4"
        
        # Update Node version if needed
        if name == "WEBSITE_NODE_DEFAULT_VERSION" and value.startswith("14"):
            value = "18.0.0"

        v2_settings.append({"name": name, "value": value})

    return v2_settings

def save_metadata(metadata, filename):
    """Save metadata to JSON file."""
    with open(filename, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"✓ Saved to {filename}")

def deploy_v2_function_app(subscription_id, resource_group, target_app_name, v2_metadata, environment_id=None):
    """Deploy v2 Function App."""
    print(f"\n[Step 3] Deploying v2 Function App...")

    try:
        credential = DefaultAzureCredential()
        web_client = WebSiteManagementClient(credential, subscription_id)

        site_config = v2_metadata["properties"]["site_config"]
        
        linux_fx_version = site_config.get("linux_fx_version")
        if not linux_fx_version:
            linux_fx_version = f"DOCKER|{v2_metadata.get('deployment_properties', {}).get('container_image', 'mcr.microsoft.com/azure-functions/node:4-node18')}"

        properties = {
            "managedEnvironmentId": environment_id,
            "siteConfig": {
                "linuxFxVersion": linux_fx_version,
            }
        }

        if v2_metadata["properties"].get("server_farm_id"):
            properties["serverFarmId"] = v2_metadata["properties"]["server_farm_id"]

        site_envelope = {
            "location": v2_metadata["location"],
            "kind": v2_metadata["kind"],
            "tags": v2_metadata.get("tags", {}),
            "properties": properties
        }

        poller = web_client.web_apps.begin_create_or_update(
            resource_group_name=resource_group,
            name=target_app_name,
            site_envelope=site_envelope
        )
        result = poller.result()

        print(f"✓ v2 Function App deployed successfully!")
        print(f"  - Resource ID: {result.id}")
        print(f"  - Default hostname: {result.default_host_name}")

        # Apply app settings
        app_settings = site_config.get("app_settings", [])
        if app_settings:
            print(f"\n[Step 4] Applying {len(app_settings)} app settings...")
            settings_dict = {"properties": {}}
            for setting in app_settings:
                settings_dict["properties"][setting["name"]] = setting["value"]
            
            web_client.web_apps.update_application_settings(
                resource_group_name=resource_group,
                name=target_app_name,
                app_settings=settings_dict
            )
            print(f"✓ App settings applied")

        return result

    except Exception as e:
        print(f"✗ Error deploying Function App: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Migrate Function App from v1 to v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export and deploy with new name
    python migrate_function_app.py \
        --source-subscription-id <SOURCE_SUB_ID> \
        --target-subscription-id <TARGET_SUB_ID> \
    --source-rg myresourcegroup \\
    --source-app my-function-app-v1 \\
    --target-rg myresourcegroup \\
    --environment-id /subscriptions/.../managedEnvironments/myenv \\
    --target-app my-function-app-v2

  # Just export metadata
    python migrate_function_app.py \
        --source-subscription-id <SOURCE_SUB_ID> \
        --target-subscription-id <TARGET_SUB_ID> \
    --source-rg myresourcegroup \\
    --source-app my-function-app-v1 \\
    --export-only
        """
    )

    parser.add_argument("--source-subscription-id", required=True, help="Source Azure subscription ID")
    parser.add_argument("--target-subscription-id", required=True, help="Target Azure subscription ID")
    parser.add_argument("--source-rg", required=True, help="Source resource group")
    parser.add_argument("--source-app", required=True, help="Source v1 Function App name")
    parser.add_argument("--target-rg", help="Target resource group for v2 (default: same as source)")
    parser.add_argument("--target-app", help="Target v2 Function App name (default: append '-v2')")
    parser.add_argument("--environment-id", help="Container Apps managed environment ID (required for v2 deployment)")
    parser.add_argument("--export-only", action="store_true", help="Only export metadata, don't deploy")
    parser.add_argument("--output-file", default="v2_metadata.json", help="Output metadata file")

    args = parser.parse_args()

    # Set defaults
    target_rg = args.target_rg or args.source_rg
    target_app = args.target_app or f"{args.source_app}-v2"

    print("=" * 70)
    print("Azure Function App v1 → v2 Migration Workflow")
    print("=" * 70)

    # Step 1: Export v1 metadata
    v1_metadata = export_v1_metadata(args.source_subscription_id, args.source_rg, args.source_app)

    target_location = None
    if not args.export_only and args.environment_id:
        target_location = get_managed_environment_location(args.target_subscription_id, args.environment_id)
        if target_location:
            print(f"\n[Step 1b] Target managed environment location: {target_location}")

    # Step 2: Transform to v2
    v2_metadata = transform_to_v2(v1_metadata, target_app, target_location=target_location)

    # Save metadata
    print(f"\n[Step 2b] Saving transformed metadata...")
    save_metadata({"v1_metadata": v1_metadata, "v2_metadata": v2_metadata}, args.output_file)

    # Step 3: Deploy (if not export-only)
    if not args.export_only:
        if not args.environment_id:
            print("\n✗ --environment-id is required for deployment")
            sys.exit(1)

        deploy_v2_function_app(
            args.target_subscription_id,
            target_rg,
            target_app,
            v2_metadata,
            args.environment_id
        )

        print("\n" + "=" * 70)
        print(f"✓ Migration complete!")
        print(f"  Source (v1): {args.source_app} in {args.source_rg}")
        print(f"  Target (v2): {target_app} in {target_rg}")
        print(f"  Metadata saved to: {args.output_file}")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print(f"✓ Export complete!")
        print(f"  Metadata saved to: {args.output_file}")
        print(f"\nTo deploy the v2 Function App, run:")
        print(f"  python migrate_function_app.py \\\\")
        print(f"    --source-subscription-id {args.source_subscription_id} \\\\")
        print(f"    --target-subscription-id {args.target_subscription_id} \\\\")
        print(f"    --source-rg {args.source_rg} \\")
        print(f"    --source-app {args.source_app} \\")
        print(f"    --target-rg {target_rg} \\")
        print(f"    --target-app {target_app} \\")
        print(f"    --environment-id <MANAGED_ENV_ID> \\")
        print(f"    --output-file {args.output_file}")
        print("=" * 70)

if __name__ == "__main__":
    main()
