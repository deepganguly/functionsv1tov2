import argparse
import json
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.web import WebSiteManagementClient
from azure.core.exceptions import ResourceExistsError

def deploy_v2_function_app(subscription_id, resource_group, metadata_file, environment_id=None):
    """
    Deploy a v2 Function App using transformed metadata.
    
    Args:
        subscription_id: Azure subscription ID
        resource_group: Target resource group
        metadata_file: Path to the transformed v2 metadata JSON file
        environment_id: Container Apps managed environment ID (optional)
    """
    # Authenticate
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)
    resource_client = ResourceManagementClient(credential, subscription_id)

    # Load transformed v2 metadata
    with open(metadata_file, "r") as f:
        metadata = json.load(f)

    # Extract v2 metadata
    v2_metadata = metadata.get("v2_metadata", metadata)
    
    app_name = v2_metadata["name"]
    location = v2_metadata["location"]
    kind = v2_metadata.get("kind", "functioncontainerapp")
    tags = v2_metadata.get("tags", {})
    site_config = v2_metadata.get("properties", {}).get("site_config", {})
    deployment_props = v2_metadata.get("deployment_properties", {})

    print(f"Deploying v2 Function App: {app_name}")
    print(f"  Location: {location}")
    print(f"  Kind: {kind}")
    print(f"  Environment ID: {environment_id}")

    try:
        # Prepare the Function App creation parameters
        site_envelope = {
            "location": location,
            "kind": kind,
            "tags": tags,
            "properties": {
                "serverFarmId": v2_metadata.get("properties", {}).get("server_farm_id"),
                "reserved": v2_metadata.get("properties", {}).get("reserved", False),
                "isXenon": v2_metadata.get("properties", {}).get("is_xenon", False),
                "hyperV": v2_metadata.get("properties", {}).get("hyper_v", False),
                "managedEnvironmentId": environment_id or v2_metadata.get("properties", {}).get("managed_environment_id"),
                "siteConfig": prepare_site_config(site_config, deployment_props),
            }
        }

        # Create or update the Function App
        print(f"\nCreating Function App...")
        result = web_client.web_apps.create_or_update(
            resource_group_name=resource_group,
            name=app_name,
            site_envelope=site_envelope
        )

        print(f"✓ Function App created successfully!")
        print(f"  Resource ID: {result.id}")
        print(f"  Default hostname: {result.default_host_name}")

        # Configure app settings from v2 metadata
        app_settings = extract_app_settings(site_config)
        if app_settings:
            print(f"\nApplying {len(app_settings)} app settings...")
            web_client.web_apps.update_application_settings(
                resource_group_name=resource_group,
                name=app_name,
                app_settings=app_settings
            )
            print(f"✓ App settings applied")

        return result

    except ResourceExistsError as e:
        print(f"✗ Function App already exists: {e}")
        raise
    except Exception as e:
        print(f"✗ Error deploying Function App: {e}")
        raise

def prepare_site_config(site_config, deployment_props):
    """Prepare site configuration for v2 Function App."""
    config = {
        "numberOfWorkers": site_config.get("number_of_workers", 1),
        "netFrameworkVersion": site_config.get("net_framework_version", "v4.0"),
        "pythonVersion": site_config.get("python_version", ""),
        "nodeVersion": site_config.get("node_version", ""),
        "use32BitWorkerProcess": site_config.get("use32_bit_worker_process", True),
        "webSocketsEnabled": site_config.get("web_sockets_enabled", False),
        "managedPipelineMode": site_config.get("managed_pipeline_mode", "Integrated"),
        "requestTracingEnabled": site_config.get("request_tracing_enabled", False),
        "remoteDebuggingEnabled": site_config.get("remote_debugging_enabled", False),
        "httpLoggingEnabled": site_config.get("http_logging_enabled", False),
        "detailedErrorLoggingEnabled": site_config.get("detailed_error_logging_enabled", False),
    }

    # Add container settings if available
    if deployment_props:
        config["linuxFxVersion"] = deployment_props.get("container_image", "")
        config["acrUseManagedIdentityCreds"] = True

    return config

def extract_app_settings(site_config):
    """Extract app settings from site configuration."""
    app_settings_list = site_config.get("app_settings", [])
    
    # Convert to the format expected by Azure SDK
    app_settings = {
        "properties": {}
    }

    for setting in app_settings_list:
        name = setting.get("name")
        value = setting.get("value")
        if name and value:
            app_settings["properties"][name] = value

    return app_settings if app_settings["properties"] else None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy a v2 Function App using transformed metadata.")
    parser.add_argument("--subscription-id", required=True, help="Azure subscription ID")
    parser.add_argument("--resource-group", required=True, help="Target resource group")
    parser.add_argument("--metadata-file", required=True, help="Path to transformed v2 metadata JSON file")
    parser.add_argument("--environment-id", help="Container Apps managed environment ID (optional)")

    args = parser.parse_args()

    deploy_v2_function_app(
        args.subscription_id, 
        args.resource_group, 
        args.metadata_file,
        args.environment_id
    )