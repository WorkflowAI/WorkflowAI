# pyright: reportPrivateUsage=false

from typing import Any

import pytest

from core.domain.tool import Tool
from core.tools import ToolKind

from .task_group_properties import _SIMILARITY_HASH_FIELDS, FewShotConfiguration, FewShotExample, TaskGroupProperties


class TestComputeTags:
    def test_with_few_shot(self):
        properties = TaskGroupProperties(
            few_shot=FewShotConfiguration(
                count=5,
                selection="latest",
                examples=[
                    FewShotExample(
                        task_input={"name": "1"},
                        task_output={"say_hello": "2"},
                    ),
                ],
            ),
        )
        assert properties.compute_tags() == [
            "few_shot.count=5",
            "few_shot.selection=latest",
        ]
        assert properties.model_dump(mode="json", exclude_none=True) == {
            "few_shot": {
                "count": 5,
                "examples": [
                    {
                        "task_input": {
                            "name": "1",
                        },
                        "task_output": {
                            "say_hello": "2",
                        },
                    },
                ],
                "selection": "latest",
            },
        }


class TestComputeSimilarityHash:
    @pytest.mark.parametrize(
        "overrides",
        [
            {"is_structured_generation_enabled": True},
            {"is_structured_generation_enabled": False},
            {"runner_name": "a"},
            {"runner_version": "3"},
            {"enabled_tools": ["WEB_SEARCH_GOOGLE"]},
            {"model": "gpt-4o-mini"},
        ],
    )
    def test_similar_properties(self, overrides: dict[str, Any]):
        base = {
            "model": "gpt-4o",
            "instructions": "You are a helpful assistant.",
            "task_variant_id": "bla",
            **overrides,
        }
        properties = TaskGroupProperties.model_validate(base)
        assert properties.similarity_hash == "540ace3df9f476b8d3e916811b64a3e5"

    @pytest.mark.parametrize(
        "overrides",
        [
            pytest.param({"instructions": "You are not a helpful assistant."}, id="instructions"),
            pytest.param({"task_variant_id": "bla1"}, id="task_variant_id"),
            pytest.param({"messages": [{"role": "user", "content": [{"text": "Hello, world!"}]}]}, id="messages"),
            pytest.param({"top_p": 0.5}, id="top_p"),
            pytest.param({"frequency_penalty": 0.5}, id="frequency_penalty"),
            pytest.param({"presence_penalty": 0.5}, id="presence_penalty"),
        ],
    )
    def test_different_properties(self, overrides: dict[str, Any]):
        base = {
            "instructions": "You are a helpful assistant.",
            "task_variant_id": "bla",
        }
        properties = TaskGroupProperties.model_validate({**base, **overrides})
        assert "540ace3df9f476b8d3e916811b64a3e5" == TaskGroupProperties.model_validate(base).similarity_hash, "sanity"
        assert properties.similarity_hash != "540ace3df9f476b8d3e916811b64a3e5"


class TestValidate:
    def test_with_enabled_tools(self):
        properties = TaskGroupProperties.model_validate(
            {
                "enabled_tools": [
                    "whatever",
                    "@search-google",
                    {"name": "h", "input_schema": {}, "output_schema": {}},
                ],
            },
        )
        assert properties.enabled_tools == [
            ToolKind.WEB_SEARCH_GOOGLE,
            Tool(name="h", input_schema={}, output_schema={}),
        ]


class TestModelHash:
    def test_model_hash_with_templated_instructions(self):
        properties = TaskGroupProperties(
            instructions="Hello, {{ name }}!",
        )
        assert properties.model_hash() == "38274190bcf9f42037f7800fc2b764f1"
        assert properties.has_templated_instructions, "sanity"

        # Change should be ignored
        properties.has_templated_instructions = False
        assert properties.model_hash() == "38274190bcf9f42037f7800fc2b764f1"

    def test_model_hash_constant(self):
        # Computing the model hash should not change over time to avoid creating duplicate groups
        properties = TaskGroupProperties.model_validate(
            {
                "model": "gemini-1.5-pro-latest",
                "temperature": 0,
                "instructions": "You are a culinary measurement specialist focused on recipe scaling and practical kitchen measurements. Given a recipe with its original servings and ingredients list, along with a desired number of servings, calculate the adjusted quantities for each ingredient.\n\nFor each ingredient:\n\n- Calculate the scaling factor by dividing desired servings by original servings.\n- Multiply the original amount by the scaling factor to get the adjusted amount.\n- Convert the adjusted amount into practical kitchen measurements using standard cooking units (e.g., cups, tablespoons, teaspoons).\n- When converting measurements:\n  - Use common fraction increments for easier reading and practicality (1/4, 1/3, 1/2, 2/3, 3/4).\n  - Avoid uncommon fractions that are not typically available in standard kitchen measuring tools (e.g., 1/6, 3/8, 3/16).\n  - If rounding results in an uncommon fraction, adjust the measurement by combining units to make it practical (e.g., use multiple teaspoons instead of a fraction of a teaspoon).\n  - Round to the nearest practical measurement based on the common fractions above.\n  - Consider common kitchen tool measurements:\n    * 1 cup = 16 tablespoons.\n    * 1 tablespoon = 3 teaspoons.\n    * Use smaller units when amounts are less than 1/4 of the larger unit.\n\nReturn both the precise numerical measurements and their practical kitchen equivalents for each ingredient.",
                "runner_name": "WorkflowAI",
                "runner_version": "v0.1.0",
                "is_chain_of_thought_enabled": False,
                "task_variant_id": "0b111218c774e3eadb6c1f01319cb62f",
            },
        )
        assert properties.model_hash() == "b80049b0a1735ec3eed8fff127a32494"
        assert properties.similarity_hash == "0f47ae72d7ef5a74553690c258476737"


def test_similarity_hash_fields():
    # Check that all required fields in the version properties are included
    # This is just to make sure that we think twice about whether a new field in version
    # properties should be included in the similarity hash or not
    all_fields = {*set(TaskGroupProperties.model_fields), "task_variant_id"}
    excluded_fields = {
        "model",
        "provider",
        "max_tokens",
        "runner_name",
        "runner_version",
        "is_chain_of_thought_enabled",
        "enabled_tools",
        "is_structured_generation_enabled",
        "has_templated_instructions",
        "image_options",
        "tool_choice",
        "few_shot",
        "parallel_tool_calls",
        "template_name",
    }

    assert all_fields - excluded_fields == _SIMILARITY_HASH_FIELDS
