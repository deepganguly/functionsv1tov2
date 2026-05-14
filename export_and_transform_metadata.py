import argparse
import json
from azure.identity import DefaultAzureCredential
from azure.mgmt.web import WebSiteManagementClient

def export_and_transform_metadata(subscription_id, resource_group, app_name, output_file):
    # Authenticate using Azure Default Credential
    credential = DefaultAzureCredential()
    client = WebSiteManagementClient(credential, subscription_id)

    # Get Function App details
    app = client.web_apps.get(resource_group, app_name)

    # Extract v1 metadata
    v1_metadata = {
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

    # Transform to v2 metadata
    v2_metadata = transform_to_v2(v1_metadata)

    # Save v2 metadata to file
    with open(output_file, "w") as f:
        json.dump(v2_metadata, f, indent=4)

    print(f"Transformed v2 metadata exported to {output_file}")

def transform_to_v2(v1_metadata):
    v2_metadata = v1_metadata.copy()

    # Update kind and managed_by for v2
    v2_metadata["kind"] = "functioncontainerapp"
    v2_metadata["managed_by"] = "Microsoft.App"

    # Add or modify other fields as needed for v2 compatibility
    v2_metadata["properties"]["new_field"] = "example_value"  # Example transformation

    return v2_metadata

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export and transform v1 Function App metadata to v2 deployable format.")
    parser.add_argument("--subscription-id", required=True, help="Azure subscription ID")
    parser.add_argument("--resource-group", required=True, help="Resource group name")
    parser.add_argument("--app-name", required=True, help="Function App name")
    parser.add_argument("--output-file", default="v2_metadata.json", help="Output file for transformed metadata")

    args = parser.parse_args()

    export_and_transform_metadata(
        args.subscription_id, args.resource_group, args.app_name, args.output_file
    )