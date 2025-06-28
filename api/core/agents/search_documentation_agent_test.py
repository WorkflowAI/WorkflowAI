from core.agents.search_documentation_agent import (
    SearchDocumentationOutput,
    create_search_documentation_json_schema,
)


def test_json_schema_and_pydantic_model_fields_are_in_sync():
    """Test that create_search_documentation_json_schema and SearchDocumentationOutput have the same field names."""
    # Create a sample JSON schema
    sample_file_paths = ["path1", "path2"]
    json_schema = create_search_documentation_json_schema(sample_file_paths)

    # Extract field names from JSON schema
    json_schema_fields = set(json_schema["properties"].keys())

    # Extract field names from Pydantic model
    pydantic_fields = set(SearchDocumentationOutput.model_fields.keys())

    # Assert they are the same
    assert json_schema_fields == pydantic_fields, (
        f"JSON schema fields {json_schema_fields} do not match Pydantic model fields {pydantic_fields}"
    )
