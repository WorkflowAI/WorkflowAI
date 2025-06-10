from typing import Any

from pydantic import BaseModel

from tests.component.common import IntegrationTestClient


async def test_create_agent(test_client: IntegrationTestClient):
    class GreetInput(BaseModel):
        class Embedded(BaseModel):
            embedded_field: str

        name: str
        embedded: Embedded

    schema = GreetInput.model_json_schema()
    assert "Embedded" in schema["$defs"], "sanity"
    assert schema["type"] == "object", "sanity"

    agent = await test_client.create_agent_v1(
        input_schema=schema,
    )
    assert agent["id"] == "greet", "sanity"
    assert agent["uid"], "sanity"  # a random number that will be generated
    assert agent["schema_id"] == 1, "sanity"

    # Now create the same agent again, by adding examples and inlining the def

    agent_1 = await test_client.create_agent_v1(
        id="greet",
        # Same schema but defined differently
        input_schema={
            # Skipping type and inlining def
            "properties": {
                "name": {
                    "type": "string",
                },
                "embedded": {
                    "properties": {
                        "embedded_field": {
                            "type": "string",
                            "examples": ["test"],
                            "description": "A field",
                        },
                    },
                    "required": ["embedded_field"],
                },
            },
            "required": ["name", "embedded"],
        },
    )
    assert agent_1["id"] == "greet", "sanity"
    assert agent_1["schema_id"] == 1, "sanity"
    assert agent_1["uid"] == agent["uid"], "sanity"


async def test_schema_updater(test_client: IntegrationTestClient, integration_storage: Any):
    # Test that the schema updater will fix old schema mappings
    class GreetInput(BaseModel):
        class Embedded(BaseModel):
            embedded_field: str

        name: str
        embedded: Embedded

    # Creating a task with the old schema
    agent = await test_client.create_agent_v1(
        input_schema=GreetInput.model_json_schema(),
        sanitize_schemas=False,
    )
    assert agent["id"] == "greet", "sanity"
    assert agent["schema_id"] == 1, "sanity"

    # Run the task with the old schema
    # It should work without issues
    test_client.mock_openai_call()
    run0 = await test_client.run_task_v1(
        task=agent,
        task_input={"name": "John", "embedded": {"embedded_field": "test"}},
    )
    # Fetch the version obkect and check that the schema is indeed unaltered
    version = await test_client.fetch_version(agent, version_id=run0["version"]["id"])
    assert "$defs" in version["input_schema"] and "Embedded" in version["input_schema"]["$defs"], "sanity"

    from scripts.update_task_schema_mappings import SchemaIDXMappingUpdater

    updater = SchemaIDXMappingUpdater(integration_storage)
    await updater.run(tenant=None, task_id=None, task_schema_id=None, limit=1, commit=True)

    # Now create an agent with the same schema but the new endpoing
    agent_1 = await test_client.create_agent_v1(
        input_schema=GreetInput.model_json_schema(),
    )
    assert agent_1["id"] == "greet", "sanity"
    assert agent_1["schema_id"] == 1, "sanity"

    # For sanity check, see that I can run the task with the new variant id
    test_client.mock_openai_call()
    run1 = await test_client.run_task_v1(
        task=agent,
        task_input={"name": "John", "embedded": {"embedded_field": "test"}},
    )
    fetched_version = await test_client.fetch_version(agent, version_id=run1["version"]["id"])
    assert fetched_version["properties"]["task_variant_id"] == agent_1["variant_id"], "sanity"
    assert fetched_version["input_schema"] == {
        "type": "object",
        "properties": {
            "name": {"type": "string", "title": "Name"},
            "embedded": {
                "type": "object",
                "properties": {
                    "embedded_field": {"title": "Embedded Field", "type": "string"},
                },
                "required": ["embedded_field"],
                "title": "Embedded",
            },
        },
        "title": "GreetInput",
        "required": ["embedded", "name"],
    }


_DEPRECATED_INPUT_SCHEMA: dict[str, Any] = {
    "$defs": {
        "Image": {
            "properties": {
                "name": {
                    "anyOf": [
                        {
                            "type": "string",
                        },
                        {
                            "type": "null",
                        },
                    ],
                    "default": None,
                    "deprecated": True,
                    "description": "An optional name for the file [no longer used]",
                    "title": "Name",
                },
                "content_type": {
                    "anyOf": [
                        {
                            "type": "string",
                        },
                        {
                            "type": "null",
                        },
                    ],
                    "default": None,
                    "description": "The content type of the file. Not needed if content type can be inferred from the URL.",
                    "examples": [
                        "image/png",
                        "image/jpeg",
                    ],
                    "title": "Content Type",
                },
                "data": {
                    "anyOf": [
                        {
                            "type": "string",
                        },
                        {
                            "type": "null",
                        },
                    ],
                    "default": None,
                    "description": "The base64 encoded data of the file. Required if no URL is provided.",
                    "title": "Data",
                },
                "url": {
                    "anyOf": [
                        {
                            "type": "string",
                        },
                        {
                            "type": "null",
                        },
                    ],
                    "default": None,
                    "description": "The URL of the file. Required if no data is provided.",
                    "title": "Url",
                },
            },
            "title": "Image",
            "type": "object",
        },
    },
    "properties": {
        "image": {
            "$ref": "#/$defs/Image",
            "description": "The image to analyze",
        },
    },
    "required": [
        "image",
    ],
    "title": "ImageInput",
    "type": "object",
}


async def test_schema_updater_with_images(test_client: IntegrationTestClient, integration_storage: Any):
    # Creating a task with the old schema
    agent = await test_client.create_agent_v1(
        input_schema=_DEPRECATED_INPUT_SCHEMA,
        sanitize_schemas=False,
    )
    assert agent["id"] == "greet", "sanity"
    assert agent["schema_id"] == 1, "sanity"

    # Run the task with the old schema
    # It should work without issues
    test_client.mock_openai_call()
    run0 = await test_client.run_task_v1(
        task=agent,
        task_input={"image": {"data": "test", "content_type": "image/jpeg"}},
    )
    # Fetch the version obkect and check that the schema is indeed unaltered
    version = await test_client.fetch_version(agent, version_id=run0["version"]["id"])
    assert version["input_schema"] == _DEPRECATED_INPUT_SCHEMA, "sanity"

    from scripts.update_task_schema_mappings import SchemaIDXMappingUpdater

    updater = SchemaIDXMappingUpdater(integration_storage)
    await updater.run(tenant=None, task_id=None, task_schema_id=None, limit=1, commit=True)

    # Now create an agent with the same schema but the new endpoing
    agent_1 = await test_client.create_agent_v1(
        input_schema=_DEPRECATED_INPUT_SCHEMA,
    )
    assert agent_1["id"] == "greet", "sanity"
    assert agent_1["schema_id"] == 1, "sanity"

    # # For sanity check, see that I can run the task with the new variant id
    test_client.httpx_mock.add_response(url="https://test.com/image.jpg", status_code=200, content=b"test")
    test_client.mock_openai_call()
    run1 = await test_client.run_task_v1(
        task=agent,
        task_input={"image": {"url": "https://test.com/image.jpg"}},
    )
    fetched_version = await test_client.fetch_version(agent, version_id=run1["version"]["id"])
    assert fetched_version["properties"]["task_variant_id"] == agent_1["variant_id"], "sanity"


async def test_create_agent_with_optional_values(test_client: IntegrationTestClient):
    """Check that registering schemas that both result in an optional field
    does not create new schemas"""

    class GreetInput1(BaseModel):
        name: str | None = None

    class GreetInput2(BaseModel):
        name: str = ""

    agent = await test_client.create_agent_v1(
        input_schema=GreetInput1.model_json_schema(),
    )
    assert agent["id"] == "greet", "sanity"
    assert agent["schema_id"] == 1, "sanity"

    agent_2 = await test_client.create_agent_v1(
        input_schema=GreetInput2.model_json_schema(),
    )
    assert agent_2["id"] == "greet", "sanity"
    assert agent_2["schema_id"] == 1

    agent_3 = await test_client.create_agent_v1(
        input_schema={"properties": {"name": {"type": "string"}}},
    )
    assert agent_3["id"] == "greet", "sanity"
    assert agent_3["schema_id"] == 1
