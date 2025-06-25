import asyncio
from datetime import datetime, timedelta
from typing import Any, cast
from unittest.mock import Mock

import pytest

from core.domain.models import Model
from core.domain.review import ReviewOutcome
from core.utils.uuid import uuid7, uuid7_generation_time
from tests.component.common import (
    IntegrationTestClient,
    result_or_raise,
)
from tests.component.conftest import _INT_DB_NAME  # pyright: ignore [reportPrivateUsage]
from tests.utils import fixtures_json

_now = datetime.now()


@pytest.fixture(scope="module")
async def searchable_runs(int_clickhouse_client: Any):
    searchable_runs = fixtures_json("runs/searchable_runs.json")
    from core.storage.clickhouse.clickhouse_client import ClickhouseClient
    from core.storage.clickhouse.models.runs import ClickhouseRun

    client = cast(ClickhouseClient, int_clickhouse_client)  # pyright: ignore [reportPrivateUsage]

    # Remapping the dates to be closer to the current date
    docs = [ClickhouseRun.model_validate(run) for run in searchable_runs]
    reference_date = max(run.created_at_date for run in docs)
    reference_datetime = max(uuid7_generation_time(run.run_uuid) for run in docs)

    for run in docs:
        run.created_at_date = _now.date() - (reference_date - run.created_at_date)
        new_created_at = _now - (reference_datetime - uuid7_generation_time(run.run_uuid))
        run.run_uuid = uuid7(ms=lambda: int(new_created_at.timestamp() * 1000))
        run.conversation_id = uuid7()

    await client.command("TRUNCATE TABLE runs")
    await client.insert_models("runs", docs, {"async_insert": 0, "wait_for_async_insert": 1})

    from tests.component.conftest import _build_storage  # pyright: ignore [reportPrivateUsage]

    base_storage = _build_storage(mock_encryption=Mock())

    # Manually purge all collections
    db = base_storage.client[_INT_DB_NAME]
    names = await db.list_collection_names()
    await asyncio.gather(
        *(db[c].delete_many({}) for c in names if c != "system.profile"),
    )

    # Forcing the task_uid to be 1, hardcoded values will need to change if the token changes
    await base_storage._tasks_collection.insert_one(  # pyright: ignore [reportPrivateUsage]
        {"tenant": "chiefofstaff.ai", "task_id": "greet", "uid": 1},
    )

    # Also injecting the tenant to get a predicatble tenant_uid
    await base_storage._organization_collection.insert_one(  # pyright: ignore [reportPrivateUsage]
        {"tenant": "chiefofstaff.ai", "uid": 1, "org_id": "org_2iPlfJ5X4LwiQybM9qeT00YPdBe"},
    )

    from core.storage.mongo.models.review_document import ReviewDocument

    async def _add_review_to_run(
        idx: int,
        outcome: ReviewOutcome,
        reviewer: ReviewDocument.UserReviewer | ReviewDocument.AIReviewer | None = None,
    ):
        run = docs[idx]
        doc = ReviewDocument(
            tenant_uid=1,
            tenant="chiefofstaff.ai",
            task_id="greet",
            task_schema_id=run.task_schema_id,
            task_input_hash=run.input_hash,
            task_output_hash=run.output_hash,
            eval_hash=run.eval_hash,
            outcome=outcome,
            comment="test",
            status="completed",
            reviewer=reviewer or ReviewDocument.UserReviewer(),
        )
        await base_storage._reviews_collection.insert_one(doc.model_dump(exclude_none=True))  # pyright: ignore [reportPrivateUsage]

    # Assigning reviews
    await _add_review_to_run(0, "positive")
    await _add_review_to_run(2, "positive")
    await _add_review_to_run(4, "negative")
    await _add_review_to_run(1, "unsure", ReviewDocument.AIReviewer(evaluator_id="test", input_evaluation_id="test"))

    return {str(d.run_uuid): idx for idx, d in enumerate(docs)}


# We should be ok without purging here since the requests are idempotent
@pytest.fixture(autouse=True)
async def setup_task(test_client: IntegrationTestClient):
    task = await test_client.create_task(
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "email": {"type": "string"},
                "properties": {"type": "object", "properties": {"test": {"type": "string"}}},
                "validated_input": {"type": "boolean"},
            },
            "required": ["name", "age"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "greeting": {"type": "string"},
                "category": {"type": "string"},
                "list_items": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["greeting", "category"],
        },
    )

    # Update the task info record to have a task_uid of 1

    # Create a version
    version = await test_client.create_version_v1(
        task=task,
        version_properties={
            "model": "gpt-4o-2024-11-20",
            "temperature": 0.1,
        },
    )

    assert version["id"] == "7f79eb255e6848b6cad790024a2fab51", "sanity"
    result_or_raise(
        await test_client.int_api_client.post(
            f"/v1/_/agents/{task['task_id']}/versions/{version['id']}/save",
        ),
    )

    return task


@pytest.mark.no_truncate
async def test_return_all_runs(test_client: IntegrationTestClient, searchable_runs: dict[str, int]):
    response = await test_client.post(
        "/v1/_/agents/greet/runs/search",
        json={},
    )
    assert len(response["items"]) == 5
    indices = [searchable_runs[run["id"]] for run in response["items"]]
    assert indices == [0, 1, 2, 3, 4]
    assert response["count"] == 5


def _sc(key: str, operator: str, values: list[Any], expected: list[int], field_type: str):
    if len(values) == 1:
        value_str = str(values[0])
    elif not values:
        value_str = ""
    else:
        value_str = str(values)
    return pytest.param(key, operator, values, expected, field_type, id=f"{key} {operator} {value_str}")


_search_cases = [
    # Status queries (updated counts)
    _sc("status", "is", ["success"], [0, 2, 3, 4], "string"),
    _sc("status", "is", ["failure"], [1], "string"),
    # Metadata queries (updated counts)
    _sc("metadata.provider", "is", ["openai"], [1, 2, 4], "string"),
    _sc("metadata.provider", "is not", ["anthropic"], [0, 1, 2, 3, 4], "string"),
    _sc("metadata.model_release_quarter", "is not", ["Q4 2024"], [0, 1, 2, 3, 4], "string"),
    _sc("metadata.user-agent", "contains", ["OpenAI"], [0], "string"),
    _sc("metadata.a key with a space", "contains", ["Ola"], [1], "string"),
    # # Model queries (updated counts)
    _sc("model", "is", ["gemini-1.5-pro-001"], [4], "string"),
    _sc("model", "is not", [Model.CLAUDE_3_5_SONNET_20240620], [3, 4], "string"),
    _sc("model", "contains", ["gpt"], [3], "string"),
    _sc("model", "does not contain", ["claude"], [3, 4], "string"),
    # Price queries (updated counts)
    _sc("price", "is", [0.005], [3], "number"),
    _sc("price", "is not", [0.005], [0, 1, 2, 4], "number"),
    _sc("price", "less than", [1.00], [0, 1, 2, 3], "number"),
    _sc("price", "less than or equal to", [1.00], [0, 1, 2, 3, 4], "number"),
    _sc("price", "greater than", [0.005], [0, 1, 2, 4], "number"),
    _sc("price", "greater than or equal to", [4.79], [], "number"),
    # Temperature queries (updated counts)
    _sc("temperature", "is", ["0.1"], [3], "string"),
    _sc("temperature", "is not", ["0.24"], [0, 3, 4], "string"),
    # # Version queries
    _sc("version", "is", ["Production"], [4], "string"),
    _sc("version", "is", ["Dev"], [3], "string"),
    _sc("version", "is", ["Staging"], [], "string"),
    _sc("version", "is not", ["Production"], [0, 1, 2, 3], "string"),
    _sc("version", "is", ["827dd7a95a573adf8498fa63f4318cda"], [4], "string"),
    _sc("version", "is not", ["d0614ae5bf6b878706e112c3846553a8"], [0, 3, 4], "string"),
    _sc("version", "is", ["1.1"], [3], "string"),
    # Schema queries
    _sc("schema", "is", [1], [0, 2, 3, 4], "number"),
    _sc("schema", "is not", [1], [1], "number"),
    # Review queries
    _sc("review", "is", ["positive"], [0, 2], "string"),
    _sc("review", "is", ["negative"], [4], "string"),
    _sc("review", "is", ["unsure"], [1], "string"),
    _sc("review", "is", ["any"], [0, 1, 2, 4], "string"),
    # Source queries
    _sc("source", "is", ["my app"], [1, 2], "string"),
    _sc("source", "is", ["WorkflowAI"], [0, 3, 4], "string"),
    # Input name queries
    _sc("input.age", "is", ["Empty"], [1, 2], "number"),
    _sc("input.age", "is not", ["Empty"], [0, 3, 4], "number"),
    _sc("input.email", "is", ["Empty"], [0], "string"),
    _sc("input.email", "is not", ["Empty"], [1, 2, 3, 4], "string"),
    _sc("input.properties.test", "is", ["Empty"], [0, 2, 3, 4], "string"),
    _sc("input.properties.test", "is not", ["Empty"], [1], "string"),
    _sc("input.validated_input", "is", [True], [3], "boolean"),
    _sc("input.validated_input", "is not", [True], [0, 1, 2, 4], "boolean"),
    # For now we return any non truthy value as false
    _sc("input.validated_input", "is", [False], [0, 1, 2, 4], "boolean"),
    # TODO: fix
    # _sc("input.validated_input", "is", ["Empty"], [4, 1, 3], "boolean"),
    # # Output greeting queries
    # ("output.greeting", "is", ["Empty"], 1, "string"),
    # ("output.category", "is not", ["Empty"], 5, "string"),
    # ("output.greeting", "contains", ["Bob!"], 1, "string"),
    # ("output.list_items", "is", ["Empty"], 3, "array"),
    # ("output.list_items", "is not", ["Empty"], 2, "array"),
    # Search length
    _sc("output.list_items.length", "is", [1], [0], "array_length"),
    # Date queries, value is expressed as a number of days ago
    _sc("time", "is before", [-1], [4], "date"),
    _sc("time", "is after", [-1], [0, 1, 2, 3], "date"),
]


@pytest.mark.no_truncate
@pytest.mark.parametrize("field_name,operator,values,expected,field_type", _search_cases)
async def test_search_runs_with_field_queries(
    test_client: IntegrationTestClient,
    searchable_runs: dict[str, int],
    field_name: str,
    operator: str,
    values: list[Any],
    expected: list[int],
    field_type: str,
) -> None:
    """
    Unified test for searching runs with different field queries.
    Tests status, metadata, model, price, and temperature queries in a single parameterized test.
    """

    if field_type == "date":
        values = [(_now + timedelta(days=value)).date().isoformat() for value in values]

    response = await test_client.post(
        "/v1/_/agents/greet/runs/search",
        json={
            "field_queries": [{"field_name": field_name, "values": values, "operator": operator, "type": field_type}],
        },
    )

    indices = [searchable_runs[run["id"]] for run in response["items"]]
    assert indices == expected
    assert response["count"] == len(expected)


@pytest.mark.no_truncate
async def test_search_fields_suggestions(test_client: IntegrationTestClient, searchable_runs: dict[str, int]):
    result = await test_client.get(
        "/v1/_/agents/greet/schemas/1/runs/search/fields",
    )

    assert "fields" in result

    # Input fields
    input_fields = [field for field in result["fields"] if field["field_name"].startswith("input.")]
    assert len(input_fields) == 5

    output_fields = [field for field in result["fields"] if field["field_name"].startswith("output.")]
    assert len(output_fields) == 4

    metadata_fields = [field for field in result["fields"] if field["field_name"].startswith("metadata.")]
    metadata_fields.sort(key=lambda x: x["field_name"])
    m_field_names = [field["field_name"] for field in metadata_fields]

    assert m_field_names == [
        "metadata.completion_tokens",
        "metadata.model_release_quarter",
        "metadata.prompt_tokens",
        "metadata.provider",
    ]

    # field = next((field for field in result["fields"] if field["field_name"] == field_name), None)

    # assert field is not None, f"{field_name} field not found in the response"

    # assert field["field_name"] == field_name
    # assert field["type"] == expected_type
    # assert set(field["operators"]) == set(expected_operators)

    # if has_suggestions:
    #     assert "suggestions" in field
    #     assert isinstance(field["suggestions"], list)
    #     assert len(field["suggestions"]) > 0

    #     for suggestion in expected_suggestions:
    #         assert suggestion in field["suggestions"], (
    #             f"Expected suggestion {suggestion} not found in {field_name} suggestions"
    #         )
    # else:
    #     assert "suggestions" not in field or not field["suggestions"]

    # if field_name == "model":
    #     assert any(field["field_name"] == "input.name" for field in result["fields"])
    #     assert any(field["field_name"] == "input.age" for field in result["fields"])
    #     assert any(field["field_name"] == "output.greeting" for field in result["fields"])
    #     assert any(field["field_name"] == "output.category" for field in result["fields"])


# @pytest.mark.parametrize(
#     "field_queries,expected",
#     [
#         (
#             [
#                 {"field_name": "input.age", "operator": "is", "values": ["Empty"]},
#                 {"field_name": "input.properties.test", "operator": "is", "values": ["Empty"]},
#             ],
#             1,
#         ),
#         (
#             [
#                 {"field_name": "input.age", "operator": "is not", "values": ["Empty"]},
#                 {"field_name": "output.list_items", "operator": "is not", "values": ["Empty"]},
#             ],
#             2,
#         ),
#         (
#             [
#                 {"field_name": "input.age", "operator": "is", "values": ["Empty"], "type": "integer"},
#                 {"field_name": "output.greeting", "operator": "is not", "values": ["Empty"], "type": "string"},
#             ],
#             1,
#         ),
#         (
#             [
#                 {"field_name": "input.age", "operator": "is", "values": ["Empty"]},
#                 {"field_name": "output.list_items", "operator": "is", "values": ["Empty"]},
#                 {"field_name": "output.category", "operator": "is", "values": ["Empty"]},
#             ],
#             0,
#         ),
#         (
#             [
#                 {"field_name": "input.age", "operator": "is not", "values": ["Empty"], "type": "integer"},
#                 {"field_name": "output.list_items", "operator": "is not", "values": ["Empty"], "type": "array"},
#                 {"field_name": "output.category", "operator": "is not", "values": ["Empty"], "type": "string"},
#             ],
#             2,
#         ),
#         (
#             [
#                 {"field_name": "input.email", "operator": "is", "values": ["Empty"], "type": "string"},
#                 {"field_name": "output.list_items", "operator": "is not", "values": ["Empty"], "type": "array"},
#                 {"field_name": "output.category", "operator": "is not", "values": ["Empty"], "type": "string"},
#             ],
#             1,
#         ),
#         (
#             [
#                 {"field_name": "input.age", "operator": "is not", "values": ["Empty"], "type": "integer"},
#                 {"field_name": "output.list_items", "operator": "is not", "values": ["Empty"], "type": "array"},
#                 {"field_name": "input.email", "operator": "is", "values": ["Empty"], "type": "string"},
#             ],
#             1,
#         ),
#     ],
# )
# async def test_search_empty_fields_with_multiple_fields(
#     int_api_client: AsyncClient,
#     search_task_with_runs: dict[str, Any],
#     field_queries: list[dict[str, Any]],
#     expected: int | list[int],
# ) -> None:
#     result = await perform_search_query(
#         int_api_client,
#         search_task_with_runs["task_id"],
#         field_queries=field_queries,
#     )
#     assert len(result["items"]) == expected
