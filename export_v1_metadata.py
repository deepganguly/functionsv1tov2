import argparse
import json
from azure.identity import DefaultAzureCredential
from azure.mgmt.web import WebSiteManagementClient

def export_function_app_metadata(subscription_id, resource_group, app_name, output_file):
    # Authenticate using Azure Default Credential
    credential = DefaultAzureCredential()
    client = WebSiteManagementClient(credential, subscription_id)

    # Get Function App details
    app = client.web_apps.get(resource_group, app_name)

    # Extract metadata
    metadata = {
        "name": app.name,
        "location": app.location,
        "kind": app.kind,
        "managed_by": app.managed_by,
        "tags": app.tags,
        "properties": {
            "server_farm_id": app.server_farm_id,
            "reserved": app.reserved,
            "is_xenon": app.is_xenon,
            "hyper_v": app.hyper_v,
            "site_config": app.site_config.as_dict() if app.site_config else None,
        },
    }

    # Save metadata to file
    with open(output_file, "w") as f:
        json.dump(metadata, f, indent=4)

    print(f"Metadata exported to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export metadata of a v1 Function App.")
    parser.add_argument("--subscription-id", required=True, help="Azure subscription ID")
    parser.add_argument("--resource-group", required=True, help="Resource group name")
    parser.add_argument("--app-name", required=True, help="Function App name")
    parser.add_argument("--output-file", default="v1_metadata.json", help="Output file for metadata")

    args = parser.parse_args()

    export_function_app_metadata(
        args.subscription_id, args.resource_group, args.app_name, args.output_file
    )