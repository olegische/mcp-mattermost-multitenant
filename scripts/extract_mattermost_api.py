import yaml
import json

def extract_endpoints(openapi_spec, required_endpoints_info):
    extracted_paths = {}
    extracted_components = {
        "schemas": {},
        "responses": {},
        "securitySchemes": openapi_spec.get("components", {}).get("securitySchemes", {})
    }

    # Helper to recursively add referenced schemas
    def add_referenced_schema(schema_ref):
        if schema_ref.startswith("#/components/schemas/"):
            schema_name = schema_ref.split("/")[-1]
            if schema_name not in extracted_components["schemas"]:
                if schema_name in openapi_spec.get("components", {}).get("schemas", {}):
                    schema_def = openapi_spec["components"]["schemas"][schema_name]
                    extracted_components["schemas"][schema_name] = schema_def
                    # Recursively check for nested references
                    for prop in schema_def.get("properties", {}).values():
                        if "$ref" in prop:
                            add_referenced_schema(prop["$ref"])
                        elif "items" in prop and "$ref" in prop["items"]:
                            add_referenced_schema(prop["items"]["$ref"])
                    if "allOf" in schema_def:
                        for item in schema_def["allOf"]:
                            if "$ref" in item:
                                add_referenced_schema(item["$ref"])
        elif schema_ref.startswith("#/components/responses/"):
            response_name = schema_ref.split("/")[-1]
            if response_name not in extracted_components["responses"]:
                if response_name in openapi_spec.get("components", {}).get("responses", {}):
                    response_def = openapi_spec["components"]["responses"][response_name]
                    extracted_components["responses"][response_name] = response_def
                    # Check for schema in content
                    if "content" in response_def and "application/json" in response_def["content"]:
                        if "schema" in response_def["content"]["application/json"]:
                            schema_in_response = response_def["content"]["application/json"]["schema"]
                            if "$ref" in schema_in_response:
                                add_referenced_schema(schema_in_response["$ref"])
                            elif "items" in schema_in_response and "$ref" in schema_in_response["items"]:
                                add_referenced_schema(schema_in_response["items"]["$ref"])
                            elif "additionalProperties" in schema_in_response and "$ref" in schema_in_response["additionalProperties"]:
                                add_referenced_schema(schema_in_response["additionalProperties"]["$ref"])

    for endpoint_info in required_endpoints_info:
        path = endpoint_info["path"]
        method = endpoint_info["method"].lower()

        if path in openapi_spec["paths"] and method in openapi_spec["paths"][path]:
            extracted_paths[path] = extracted_paths.get(path, {})
            operation = openapi_spec["paths"][path][method]
            extracted_paths[path][method] = operation

            # Extract referenced schemas from this operation
            if "requestBody" in operation:
                if "content" in operation["requestBody"] and "application/json" in operation["requestBody"]["content"]:
                    if "schema" in operation["requestBody"]["content"]["application/json"]:
                        req_schema = operation["requestBody"]["content"]["application/json"]["schema"]
                        if "$ref" in req_schema:
                            add_referenced_schema(req_schema["$ref"])
                        elif "items" in req_schema and "$ref" in req_schema["items"]:
                            add_referenced_schema(req_schema["items"]["$ref"])

            if "responses" in operation:
                for status_code, response_ref in operation["responses"].items():
                    if "$ref" in response_ref:
                        add_referenced_schema(response_ref["$ref"])
                    elif "content" in response_ref and "application/json" in response_ref["content"]:
                        if "schema" in response_ref["content"]["application/json"]:
                            res_schema = response_ref["content"]["application/json"]["schema"]
                            if "$ref" in res_schema:
                                add_referenced_schema(res_schema["$ref"])
                            elif "items" in res_schema and "$ref" in res_schema["items"]:
                                add_referenced_schema(res_schema["items"]["$ref"])
                            elif "additionalProperties" in res_schema and "$ref" in res_schema["additionalProperties"]:
                                add_referenced_schema(res_schema["additionalProperties"]["$ref"])

    new_openapi_spec = {
        "openapi": openapi_spec["openapi"],
        "info": openapi_spec["info"],
        "servers": openapi_spec["servers"],
        "paths": extracted_paths,
        "components": extracted_components
    }

    # Clean up empty components
    if not extracted_components["schemas"]:
        del new_openapi_spec["components"]["schemas"]
    if not extracted_components["responses"]:
        del new_openapi_spec["components"]["responses"]
    if not extracted_components["securitySchemes"]:
        del new_openapi_spec["components"]["securitySchemes"]
    if not new_openapi_spec["components"]:
        del new_openapi_spec["components"]

    return new_openapi_spec

# Load the full OpenAPI spec
with open('docs/mattermost/mattermost-openapi.yaml', 'r') as f:
    full_openapi_spec = yaml.safe_load(f)

# Define the required endpoints
required_endpoints = [
    {"path": "/api/v4/users/{user_id}/channels/{channel_id}/unread", "method": "GET"},
    {"path": "/api/v4/posts/{post_id}/thread", "method": "GET"},
    {"path": "/api/v4/posts", "method": "POST"},
    {"path": "/api/v4/channels/direct", "method": "POST"},
    {"path": "/api/v4/channels/group", "method": "POST"},
    {"path": "/api/v4/channels", "method": "POST"},
    {"path": "/api/v4/teams/{team_id}/channels/search", "method": "POST"},
    {"path": "/api/v4/teams/{team_id}/posts/search", "method": "POST"},
    {"path": "/api/v4/channels/{channel_id}/posts", "method": "GET"},
]

# Extract the relevant parts
filtered_openapi_spec = extract_endpoints(full_openapi_spec, required_endpoints)

# Write the filtered spec to a new file
with open('docs/mattermost/mattermost-filtered-api.yaml', 'w') as f:
    yaml.dump(filtered_openapi_spec, f, indent=2, sort_keys=False)

print("Filtered OpenAPI spec written to docs/mattermost/mattermost-filtered-api.yaml")
