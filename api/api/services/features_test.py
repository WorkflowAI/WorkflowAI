from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from api.services.features import (
    CompanyContext,
    CompanyFeaturePreviewList,
    FeatureOutputPreview,
    FeatureSchemas,
    FeatureSectionPreview,
    FeatureService,
)
from api.services.internal_tasks._internal_tasks_utils import officially_suggested_tools
from core.agents.agent_input_output_example import SuggestedAgentInputOutputExampleOutput
from core.agents.agent_output_example import SuggestedAgentOutputExampleInput
from core.agents.agent_suggestion_validator_agent import (
    SuggestedAgentValidationInput,
    SuggestedAgentValidationOutput,
)
from core.agents.chat_task_schema_generation.chat_task_schema_generation_task import (
    InputGenericFieldConfig,
    InputObjectFieldConfig,
    InputSchemaFieldType,
    OutputObjectFieldConfig,
    OutputStringFieldConfig,
)
from core.agents.chat_task_schema_generation.schema_generation_agent import (
    NewAgentSchema,
    SchemaBuilderInput,
    SchemaBuilderOutput,
)
from core.agents.company_agent_suggestion_agent import (
    CompanyContext as CompanyContextInput,
)
from core.agents.company_agent_suggestion_agent import (
    SuggestAgentForCompanyInput,
    SuggestAgentForCompanyOutput,
    SuggestedAgent,
)
from core.domain.errors import ObjectNotFoundError
from core.domain.features import BaseFeature, FeatureSection, FeatureTag, FeatureWithImage
from core.tools.browser_text.browser_text_tool import FetchUrlContentResult
from tests.utils import mock_aiter


class TestFeatureService:
    async def test_get_feature_sections_preview_company_email_domain(self) -> None:
        with patch.object(FeatureService, "_is_company_email_domain", return_value=True):
            result = await FeatureService.get_feature_sections_preview(user_domain="example.com")
            expected_result = [
                FeatureSectionPreview(
                    name="Categories",
                    tags=[
                        FeatureSectionPreview.TagPreview(name="example.com", kind="company_specific"),
                        FeatureSectionPreview.TagPreview(name="Featured", kind="static"),
                        FeatureSectionPreview.TagPreview(name="E-Commerce", kind="static"),
                        FeatureSectionPreview.TagPreview(name="Healthcare", kind="static"),
                        FeatureSectionPreview.TagPreview(name="Marketing", kind="static"),
                        FeatureSectionPreview.TagPreview(name="Productivity", kind="static"),
                        FeatureSectionPreview.TagPreview(name="Social", kind="static"),
                        FeatureSectionPreview.TagPreview(name="Developer Tools", kind="static"),
                    ],
                ),
                FeatureSectionPreview(
                    name="Inspired by",
                    tags=[
                        FeatureSectionPreview.TagPreview(name="Apple, Google, Amazon", kind="static"),
                        FeatureSectionPreview.TagPreview(name="Our Customers", kind="static"),
                    ],
                ),
                FeatureSectionPreview(
                    name="Use Cases",
                    tags=[
                        FeatureSectionPreview.TagPreview(name="PDFs and Documents", kind="static"),
                        FeatureSectionPreview.TagPreview(name="Scraping", kind="static"),
                        FeatureSectionPreview.TagPreview(name="Image", kind="static"),
                        FeatureSectionPreview.TagPreview(name="Audio", kind="static"),
                    ],
                ),
            ]

            assert result == expected_result

    async def test_get_feature_sections_preview_empty_user_domain(self) -> None:
        result = await FeatureService.get_feature_sections_preview(user_domain=None)
        expected_result = [
            FeatureSectionPreview(
                name="Categories",
                tags=[
                    FeatureSectionPreview.TagPreview(name="", kind="company_specific"),
                    FeatureSectionPreview.TagPreview(name="Featured", kind="static"),
                    FeatureSectionPreview.TagPreview(name="E-Commerce", kind="static"),
                    FeatureSectionPreview.TagPreview(name="Healthcare", kind="static"),
                    FeatureSectionPreview.TagPreview(name="Marketing", kind="static"),
                    FeatureSectionPreview.TagPreview(name="Productivity", kind="static"),
                    FeatureSectionPreview.TagPreview(name="Social", kind="static"),
                    FeatureSectionPreview.TagPreview(name="Developer Tools", kind="static"),
                ],
            ),
            FeatureSectionPreview(
                name="Inspired by",
                tags=[
                    FeatureSectionPreview.TagPreview(name="Apple, Google, Amazon", kind="static"),
                    FeatureSectionPreview.TagPreview(name="Our Customers", kind="static"),
                ],
            ),
            FeatureSectionPreview(
                name="Use Cases",
                tags=[
                    FeatureSectionPreview.TagPreview(name="PDFs and Documents", kind="static"),
                    FeatureSectionPreview.TagPreview(name="Scraping", kind="static"),
                    FeatureSectionPreview.TagPreview(name="Image", kind="static"),
                    FeatureSectionPreview.TagPreview(name="Audio", kind="static"),
                ],
            ),
        ]

        assert result == expected_result

    async def test_get_feature_sections_preview_personal_email_domain(self) -> None:
        with patch.object(FeatureService, "_is_company_email_domain", return_value=False):
            result = await FeatureService.get_feature_sections_preview(user_domain="example.com")
            expected_result = [
                FeatureSectionPreview(
                    name="Categories",
                    tags=[
                        FeatureSectionPreview.TagPreview(name="Featured", kind="static"),
                        FeatureSectionPreview.TagPreview(name="E-Commerce", kind="static"),
                        FeatureSectionPreview.TagPreview(name="Healthcare", kind="static"),
                        FeatureSectionPreview.TagPreview(name="Marketing", kind="static"),
                        FeatureSectionPreview.TagPreview(name="Productivity", kind="static"),
                        FeatureSectionPreview.TagPreview(name="Social", kind="static"),
                        FeatureSectionPreview.TagPreview(name="Developer Tools", kind="static"),
                    ],
                ),
                FeatureSectionPreview(
                    name="Inspired by",
                    tags=[
                        FeatureSectionPreview.TagPreview(name="Apple, Google, Amazon", kind="static"),
                        FeatureSectionPreview.TagPreview(name="Our Customers", kind="static"),
                    ],
                ),
                FeatureSectionPreview(
                    name="Use Cases",
                    tags=[
                        FeatureSectionPreview.TagPreview(name="PDFs and Documents", kind="static"),
                        FeatureSectionPreview.TagPreview(name="Scraping", kind="static"),
                        FeatureSectionPreview.TagPreview(name="Image", kind="static"),
                        FeatureSectionPreview.TagPreview(name="Audio", kind="static"),
                    ],
                ),
            ]

            assert result == expected_result

    async def test_get_feature_sections_preview_with_user_domain(self) -> None:
        result = await FeatureService.get_feature_sections_preview(user_domain="example.com")
        expected_result = expected_result = [
            FeatureSectionPreview(
                name="Categories",
                tags=[
                    FeatureSectionPreview.TagPreview(name="example.com", kind="company_specific"),
                    FeatureSectionPreview.TagPreview(name="Featured", kind="static"),
                    FeatureSectionPreview.TagPreview(name="E-Commerce", kind="static"),
                    FeatureSectionPreview.TagPreview(name="Healthcare", kind="static"),
                    FeatureSectionPreview.TagPreview(name="Marketing", kind="static"),
                    FeatureSectionPreview.TagPreview(name="Productivity", kind="static"),
                    FeatureSectionPreview.TagPreview(name="Social", kind="static"),
                    FeatureSectionPreview.TagPreview(name="Developer Tools", kind="static"),
                ],
            ),
            FeatureSectionPreview(
                name="Inspired by",
                tags=[
                    FeatureSectionPreview.TagPreview(name="Apple, Google, Amazon", kind="static"),
                    FeatureSectionPreview.TagPreview(name="Our Customers", kind="static"),
                ],
            ),
            FeatureSectionPreview(
                name="Use Cases",
                tags=[
                    FeatureSectionPreview.TagPreview(name="PDFs and Documents", kind="static"),
                    FeatureSectionPreview.TagPreview(name="Scraping", kind="static"),
                    FeatureSectionPreview.TagPreview(name="Image", kind="static"),
                    FeatureSectionPreview.TagPreview(name="Audio", kind="static"),
                ],
            ),
        ]

        assert result == expected_result

    def test_validate_tag_uniqueness(self) -> None:
        # Verify that the current FEATURES_MAPPING has no duplicate tags
        duplicate_tags = FeatureService.validate_tag_uniqueness()
        assert duplicate_tags == {}, f"Duplicate tags found in FEATURES_MAPPING: {duplicate_tags}"

    def test_validate_tag_uniqueness_with_duplicates(self) -> None:
        # Test the validation logic with a mock that contains duplicates
        with patch(
            "api.services.features.FEATURES_MAPPING",
            [
                FeatureSection(
                    name="Section1",
                    tags=[
                        FeatureTag(name="Tag1", features=[], kind="static"),
                        FeatureTag(name="Tag2", features=[], kind="static"),
                    ],
                ),
                FeatureSection(
                    name="Section2",
                    tags=[
                        FeatureTag(name="Tag1", features=[], kind="static"),  # Duplicate tag
                        FeatureTag(name="Tag3", features=[], kind="static"),
                    ],
                ),
            ],
        ):
            result = FeatureService.validate_tag_uniqueness()
            assert result == {"tag1": ["Section1", "Section2"]}, "Failed to detect duplicate tags"


@pytest.mark.parametrize(
    "mock_features, tag, expected_features",
    [
        (
            [
                FeatureSection(
                    name="Test",
                    tags=[
                        FeatureTag(
                            name="Featured",
                            features=[
                                BaseFeature(
                                    name="Feature 1",
                                    tag_line="Feature 1",
                                    description="Description 1",
                                    specifications="Spec 1",
                                ),
                                FeatureWithImage(
                                    name="Feature 2",
                                    tag_line="Feature 2",
                                    description="Description 2",
                                    specifications="Spec 2",
                                    image_url="https://example.com/image.jpg",
                                ),
                            ],
                            kind="static",
                        ),
                    ],
                ),
                FeatureSection(
                    name="Test1",
                    tags=[
                        FeatureTag(name="Tag1", features=[], kind="static"),
                        FeatureTag(name="Tag2", features=[], kind="static"),
                    ],
                ),
            ],
            "featured",
            [
                BaseFeature(
                    name="Feature 1",
                    tag_line="Feature 1",
                    description="Description 1",
                    specifications="Spec 1",
                ),
                FeatureWithImage(
                    name="Feature 2",
                    tag_line="Feature 2",
                    description="Description 2",
                    specifications="Spec 2",
                    image_url="https://example.com/image.jpg",
                ),
            ],
        ),
        (
            [
                FeatureSection(
                    name="Test",
                    tags=[
                        FeatureTag(
                            name="Featured",
                            features=[
                                BaseFeature(
                                    name="Feature 1",
                                    tag_line="Feature 1",
                                    description="Description 1",
                                    specifications="Spec 1",
                                ),
                            ],
                            kind="static",
                        ),
                    ],
                ),
            ],
            "nonexistent",
            [],
        ),
    ],
)
async def test_search_features_by_tag(
    mock_features: list[FeatureSection],
    tag: str,
    expected_features: list[BaseFeature],
) -> None:
    with patch("api.services.features.FEATURES_MAPPING", mock_features):
        if not expected_features:
            # If no features are expected, test that the appropriate exception is raised
            with pytest.raises(ObjectNotFoundError) as exc_info:
                async for _ in FeatureService.get_features_by_tag(tag):
                    pass  # This should not execute if no features are found
            assert f"No feature tag found with tag: {tag}" in str(exc_info.value)
        else:
            # If features are expected, test that they are yielded correctly
            # Get the last yielded value which should contain all features
            final_features_list: list[BaseFeature] = []
            async for features_list in FeatureService.get_features_by_tag(tag):
                final_features_list = features_list

            # The final list should match the expected features
            assert len(final_features_list) == len(expected_features)
            for i, feature in enumerate(final_features_list):
                assert feature.model_dump() == expected_features[i].model_dump()


@pytest.mark.parametrize(
    "company_domain, company_context_chunks, feature_suggestion_chunks, expected_outputs",
    [
        (
            "example.com",
            [CompanyContext(public="Example company info", private="Example company info")],
            [
                SuggestAgentForCompanyOutput(
                    suggested_agents=[
                        SuggestedAgent(name="Feature A", description="Description A", tag_line="Tag A"),
                        SuggestedAgent(name="Feature B", description="Description B", tag_line="Tag B"),
                    ],
                ),
            ],
            [
                CompanyFeaturePreviewList(
                    company_context="Example company info",
                    features=[],
                ),
                CompanyFeaturePreviewList(
                    company_context="Example company info",
                    features=[
                        BaseFeature(name="Tag A", description="Description A", specifications="", tag_line="Tag A"),
                        BaseFeature(name="Tag B", description="Description B", specifications="", tag_line="Tag B"),
                    ],
                ),
            ],
        ),
        (
            "nocompany.com",
            [
                CompanyContext(
                    public="Could not get context from nocompany.com, we'll fallback on generic features suggestions",
                    private="Could not get context from nocompany.com, we'll fallback on generic features suggestions",
                ),
            ],
            [
                SuggestAgentForCompanyOutput(
                    suggested_agents=[
                        SuggestedAgent(
                            name="Generic Feature",
                            tag_line="Generic Tag",
                            description="Generic Description",
                        ),
                    ],
                ),
            ],
            [
                CompanyFeaturePreviewList(
                    company_context="Could not get context from nocompany.com, we'll fallback on generic features suggestions",
                    features=[],
                ),
                CompanyFeaturePreviewList(
                    company_context="Could not get context from nocompany.com, we'll fallback on generic features suggestions",
                    features=[
                        BaseFeature(
                            name="Generic Tag",
                            description="Generic Description",
                            specifications="",
                            tag_line="Generic Tag",
                        ),
                    ],
                ),
            ],
        ),
    ],
)
async def test_get_features_by_domain_e2e(  # noqa: C901
    company_domain: str,
    company_context_chunks: list[CompanyContext],
    feature_suggestion_chunks: list[SuggestAgentForCompanyOutput],
    expected_outputs: list[CompanyFeaturePreviewList],
) -> None:
    """
    Test the full flow of get_features_by_domain, mocking the internal methods.
    """
    service = FeatureService()

    async def mock_stream_company_context(*args: Any, **kwargs: Any) -> AsyncIterator[CompanyContext]:
        for chunk in company_context_chunks:
            yield chunk

    async def mock_stream_feature_suggestions(
        *args: Any,
        **kwargs: Any,
    ) -> AsyncIterator[CompanyFeaturePreviewList]:
        for chunk in feature_suggestion_chunks:
            features: list[BaseFeature] = [
                BaseFeature(
                    name=agent.tag_line,
                    description=agent.description or "",
                    specifications="",
                    tag_line=agent.tag_line,
                )
                for agent in chunk.suggested_agents or []
                if agent.name and agent.tag_line and agent.description
            ]

            yield CompanyFeaturePreviewList(
                company_context=company_context_chunks[0].public,
                features=features,
            )

    # Create a mock _build_agent_suggestion_input that returns a simple input
    async def mock_build_agent_suggestion_input(*args: Any, **kwargs: Any) -> SuggestAgentForCompanyInput:
        return SuggestAgentForCompanyInput(
            supported_agent_input_types=[],
            supported_agent_output_types=[],
            available_tools=[],
            company_context=CompanyContextInput(
                company_url=company_domain,
                company_url_content=company_context_chunks[0].private,
                existing_agents=[],
                latest_news="",
            ),
        )

    with (
        patch.object(service, "_stream_company_context", mock_stream_company_context),
        patch.object(service, "_build_agent_suggestion_input", mock_build_agent_suggestion_input),
        patch.object(service, "_stream_feature_suggestions", mock_stream_feature_suggestions),
        patch.object(service, "_get_company_latest_news", AsyncMock(return_value="")),
        # Ensure validation passes for simplicity in this e2e test
        patch.object(service, "_is_agent_validated", AsyncMock(return_value=True)),
    ):
        # Collect all outputs from the generator
        mock_event_router = Mock()
        actual_outputs = [output async for output in service.get_features_by_domain(company_domain, mock_event_router)]

        # Compare with expected outputs
        assert len(actual_outputs) == len(expected_outputs)
        for i, actual in enumerate(actual_outputs):
            expected = expected_outputs[i]
            assert actual == expected


@pytest.mark.parametrize(
    "company_domain, company_context, storage_available, expected_agent_types, expected_existing_agents, latest_news",
    [
        (
            "example.com",
            "Example company info",
            True,
            ["type1", "type2"],  # Simplified for test
            ["agent1", "agent2"],
            "Latest news example",
        ),
        (
            "example.com",
            "Example company info",
            False,
            ["type1", "type2"],
            [],  # No storage means no existing agents
            "",
        ),
    ],
)
async def test_build_agent_suggestion_input(
    company_domain: str,
    company_context: str,
    storage_available: bool,
    expected_agent_types: list[str],
    expected_existing_agents: list[str],
    latest_news: str,
) -> None:
    """
    Test the _build_agent_suggestion_input method with various configurations.
    """
    # Create mocks for the imported functions
    with (
        patch("api.services.features.get_supported_task_input_types", return_value=expected_agent_types),
        patch("api.services.features.get_supported_task_output_types", return_value=expected_agent_types),
        patch("api.services.features.safe_map", return_value=[]),
    ):
        # Create service with or without storage
        mock_storage = Mock() if storage_available else None
        service = FeatureService(storage=mock_storage)

        # Call the method
        result = await service._build_agent_suggestion_input(company_domain, company_context, latest_news)  # pyright: ignore[reportPrivateUsage]

        # Verify the result
        assert result.supported_agent_input_types == expected_agent_types
        assert result.supported_agent_output_types == expected_agent_types
        assert result.company_context
        assert result.company_context.company_url == company_domain
        assert result.company_context.company_url_content == company_context
        assert result.company_context.latest_news == latest_news

        # Mocking storage directly, so existing_agents should always be empty based on current implementation
        assert result.company_context.existing_agents == []


@pytest.mark.parametrize(
    "agent_name, instructions, validation_decisions, mock_validation_result, expected_result, expected_final_decisions",
    [
        (
            "AgentA",
            "instr",
            {},
            SuggestedAgentValidationOutput(
                enforces_instructions=True,
                is_customer_facing=True,
                requires_llm_capabilities=True,
            ),
            True,
            {"AgentA": True},
        ),
        (
            "AgentB",
            "instr",
            {"AgentB": False},
            None,  # Should not be called
            False,
            {"AgentB": False},
        ),
        (
            "AgentC",
            "instr",
            {},
            SuggestedAgentValidationOutput(
                enforces_instructions=False,
                is_customer_facing=True,
                requires_llm_capabilities=True,
            ),
            False,
            {"AgentC": False},
        ),
        (
            "AgentD",
            "instr",
            {},
            SuggestedAgentValidationOutput(
                enforces_instructions=True,
                is_customer_facing=False,
                requires_llm_capabilities=True,
            ),
            False,
            {"AgentD": False},
        ),
        (
            "AgentE",
            "instr",
            {},
            SuggestedAgentValidationOutput(
                enforces_instructions=True,
                is_customer_facing=True,
                requires_llm_capabilities=False,
            ),
            False,
            {"AgentE": False},
        ),
        (
            "AgentF",
            "instr",
            {},
            SuggestedAgentValidationOutput(
                enforces_instructions=False,
                is_customer_facing=False,
                requires_llm_capabilities=False,
            ),
            False,
            {"AgentF": False},
        ),
        (
            "AgentG",
            "instr",
            {},
            Exception("Validation error"),  # Simulate exception
            True,  # Should default to True on error
            {"AgentG": True},
        ),
        (
            "AgentH",
            "instr",
            {"AgentA": True},  # Test with existing unrelated decisions
            SuggestedAgentValidationOutput(
                enforces_instructions=True,
                is_customer_facing=True,
                requires_llm_capabilities=True,
            ),
            True,
            {"AgentA": True, "AgentH": True},
        ),
    ],
)
async def test_is_agent_validated(
    agent_name: str,
    instructions: str,
    validation_decisions: dict[str, bool],
    mock_validation_result: SuggestedAgentValidationOutput | Exception | None,
    expected_result: bool,
    expected_final_decisions: dict[str, bool],
) -> None:
    """Test the _is_agent_validated method."""
    service = FeatureService()
    initial_decisions = validation_decisions.copy()  # Preserve initial state

    mock_validator = AsyncMock()
    if isinstance(mock_validation_result, Exception):
        mock_validator.side_effect = mock_validation_result
    else:
        mock_validator.return_value = mock_validation_result

    with patch("api.services.features.run_suggested_agent_validation", mock_validator):
        result = await service._is_agent_validated(agent_name, instructions, initial_decisions)  # pyright: ignore[reportPrivateUsage]

        assert result == expected_result
        assert initial_decisions == expected_final_decisions  # Check if the dict was updated correctly

        if mock_validation_result is None:  # Cache hit case
            mock_validator.assert_not_called()
        elif agent_name not in validation_decisions:  # Cache miss case
            mock_validator.assert_called_once_with(
                SuggestedAgentValidationInput(
                    instructions=instructions,
                    proposed_agent_name=agent_name,
                ),
            )


@pytest.mark.parametrize(
    "company_context, input_chunks, validation_map, expected_outputs",
    [
        # Basic case: one valid agent
        (
            "Context 1",
            [
                SuggestAgentForCompanyOutput(
                    suggested_agents=[
                        SuggestedAgent(
                            name="ValidAgent",
                            tag_line="Tag Valid",
                            description="Desc Valid",
                        ),
                    ],
                ),
            ],
            {"ValidAgent": True},
            [
                CompanyFeaturePreviewList(
                    company_context="Context 1",
                    features=[
                        BaseFeature(
                            name="Tag Valid",
                            tag_line="Tag Valid",
                            description="Desc Valid",
                            specifications="",
                        ),
                    ],
                ),
            ],
        ),
        # Case: one invalid agent
        (
            "Context 2",
            [
                SuggestAgentForCompanyOutput(
                    suggested_agents=[
                        SuggestedAgent(
                            name="InvalidAgent",
                            tag_line="Tag Invalid",
                            description="Desc Invalid",
                        ),
                    ],
                ),
            ],
            {"InvalidAgent": False},
            [CompanyFeaturePreviewList(company_context="Context 2", features=[])],
        ),
        # Case: one valid, one invalid
        (
            "Context 3",
            [
                SuggestAgentForCompanyOutput(
                    suggested_agents=[
                        SuggestedAgent(
                            name="ValidAgent",
                            tag_line="Tag Valid",
                            description="Desc Valid",
                        ),
                        SuggestedAgent(
                            name="InvalidAgent",
                            tag_line="Tag Invalid",
                            description="Desc Invalid",
                        ),
                    ],
                ),
            ],
            {"ValidAgent": True, "InvalidAgent": False},
            [
                CompanyFeaturePreviewList(
                    company_context="Context 3",
                    features=[
                        BaseFeature(
                            name="Tag Valid",
                            tag_line="Tag Valid",
                            description="Desc Valid",
                            specifications="",
                        ),
                    ],
                ),
            ],
        ),
        # Case: Agent becomes valid across chunks (name/tagline first, then description) - Should only appear when fully formed AND valid
        (
            "Context 4",
            [
                SuggestAgentForCompanyOutput(
                    suggested_agents=[
                        SuggestedAgent(
                            name="AgentStream",
                            tag_line="Tag Stream",
                            description=None,  # Description missing initially
                        ),
                    ],
                ),
                SuggestAgentForCompanyOutput(
                    suggested_agents=[
                        SuggestedAgent(
                            name="AgentStream",
                            tag_line="Tag Stream",
                            description="Desc Stream",  # Description added
                        ),
                    ],
                ),
            ],
            {"AgentStream": True},
            [
                CompanyFeaturePreviewList(
                    company_context="Context 4",
                    features=[
                        BaseFeature(
                            name="Tag Stream",
                            tag_line="Tag Stream",
                            description="",
                            specifications="",
                        ),
                    ],
                ),  # Yielded in second chunk
                CompanyFeaturePreviewList(
                    company_context="Context 4",
                    features=[
                        BaseFeature(
                            name="Tag Stream",
                            tag_line="Tag Stream",
                            description="Desc Stream",
                            specifications="",
                        ),
                    ],
                ),  # Yielded in second chunk
            ],
        ),
        # Case: Agent completes but is invalid
        (
            "Context 5",
            [
                SuggestAgentForCompanyOutput(
                    suggested_agents=[
                        SuggestedAgent(
                            name="InvalidAgentComplete",
                            tag_line="Tag Invalid Complete",
                            description="Desc Invalid Complete",
                        ),
                    ],
                ),
            ],
            {"InvalidAgentComplete": False},
            [CompanyFeaturePreviewList(company_context="Context 5", features=[])],  # Never yielded
        ),
        # Case: Agent completes but validation fails with exception (should be included)
        (
            "Context 6",
            [
                SuggestAgentForCompanyOutput(
                    suggested_agents=[
                        SuggestedAgent(
                            name="ErrorAgent",
                            tag_line="Tag Error",
                            description="Desc Error",
                        ),
                    ],
                ),
            ],
            {"ErrorAgent": True},  # _is_agent_validated returns True on exception
            [
                CompanyFeaturePreviewList(
                    company_context="Context 6",
                    features=[
                        BaseFeature(
                            name="Tag Error",
                            tag_line="Tag Error",
                            description="Desc Error",
                            specifications="",
                        ),
                    ],
                ),
            ],
        ),
        # Case: Multiple agents, mix of valid/invalid/streaming
        (
            "Context 7",
            [
                SuggestAgentForCompanyOutput(
                    suggested_agents=[
                        SuggestedAgent(name="Valid1", tag_line="TagV1", description=None),  # Starts valid
                        SuggestedAgent(
                            name="Invalid1",
                            tag_line="TagI1",
                            description="DescI1",
                        ),  # Invalid from start
                    ],
                ),
                SuggestAgentForCompanyOutput(
                    suggested_agents=[
                        SuggestedAgent(name="Valid1", tag_line="TagV1", description="DescV1"),  # Completes valid
                        SuggestedAgent(name="Valid2", tag_line="TagV2", description="DescV2"),  # New valid
                    ],
                ),
            ],
            {"Valid1": True, "Invalid1": False, "Valid2": True},
            [
                CompanyFeaturePreviewList(
                    company_context="Context 7",
                    features=[
                        BaseFeature(name="TagV1", description="", specifications="", tag_line="TagV1"),
                    ],
                ),  # Chunk 1: Valid1 incomplete, Invalid1 filtered
                CompanyFeaturePreviewList(
                    company_context="Context 7",
                    features=[
                        BaseFeature(name="TagV1", description="DescV1", specifications="", tag_line="TagV1"),
                        BaseFeature(name="TagV2", description="DescV2", specifications="", tag_line="TagV2"),
                    ],
                ),  # Chunk 2: Valid1 complete, Valid2 complete
            ],
        ),
    ],
)
async def test_stream_feature_suggestions_with_validation(
    company_context: str,
    input_chunks: list[SuggestAgentForCompanyOutput],
    validation_map: dict[str, bool],
    expected_outputs: list[CompanyFeaturePreviewList],
) -> None:
    """
    Test the _stream_feature_suggestions method, specifically focusing on the
    interaction with _is_agent_validated.
    """
    service = FeatureService()

    # Mock the stream_suggest_agents_for_company function
    async def mock_stream(*args: Any, **kwargs: Any) -> AsyncIterator[SuggestAgentForCompanyOutput]:
        for chunk in input_chunks:
            yield chunk

    # Mock _is_agent_validated to return predefined values
    async def mock_is_validated(agent_name: str, instructions: str, validation_decisions: dict[str, bool]) -> bool:
        # Simulate the behavior of caching/calculating
        if agent_name not in validation_decisions:
            validation_decisions[agent_name] = validation_map.get(
                agent_name,
                False,
            )  # Default to False if not in map
        return validation_decisions[agent_name]

    with (
        patch("api.services.features.stream_suggest_agents_for_company", mock_stream),
        patch.object(service, "_is_agent_validated", side_effect=mock_is_validated),  # Use side_effect to pass args
    ):
        mock_input = Mock(spec=SuggestAgentForCompanyInput)
        mock_input.company_context = None

        actual_outputs = [
            output
            async for output in service._stream_feature_suggestions(company_context, mock_input)  # pyright: ignore[reportPrivateUsage]
        ]

        # Compare actual outputs with expected outputs
        assert len(actual_outputs) == len(expected_outputs)
        for i, actual in enumerate(actual_outputs):
            expected = expected_outputs[i]
            assert actual == expected


async def test_get_agent_preview() -> None:
    with (
        patch(
            "api.services.features.stream_suggested_agent_output_example",
            return_value=mock_aiter(
                SuggestedAgentInputOutputExampleOutput(agent_output_example={"foo": "bar"}),
            ),
        ) as mock_stream_suggested_agent_output_example,
    ):
        results = [
            chunk
            async for chunk in FeatureService.get_agent_preview(
                agent_name="Test Agent",
                agent_description="Test Description",
                agent_specifications="Test Specifications",
                company_context="Some company context",
            )
        ]

        mock_stream_suggested_agent_output_example.assert_called_once_with(
            SuggestedAgentOutputExampleInput(
                agent_name="Test Agent",
                agent_description="Test Description",
                agent_specifications="Test Specifications",
                company_context="Some company context",
            ),
        )
        assert len(results) == 1
        assert results == [
            FeatureOutputPreview(
                output_schema_preview={
                    "type": "object",
                    "properties": {"foo": {"type": "string"}},
                },
                output_preview={"foo": "bar"},
            ),
        ]


@pytest.mark.parametrize(
    "company_url, perplexity_chunks, expected_contexts",
    [
        (
            "example.com",
            ["Company description chunk"],
            [CompanyContext(public="Company description chunk", private="Company description chunk")],
        ),
        (
            "http://example.com",
            ["First chunk", "Second chunk"],
            [
                CompanyContext(public="First chunk", private="First chunk"),
                CompanyContext(public="Second chunk", private="Second chunk"),
            ],
        ),
    ],
)
async def test_stream_company_context_perplexity_success(
    company_url: str,
    perplexity_chunks: list[str],
    expected_contexts: list[CompanyContext],
) -> None:
    """Test _stream_company_context when Perplexity search succeeds."""

    async def mock_stream_perplexity(*args: Any, **kwargs: Any) -> AsyncIterator[str]:
        for chunk in perplexity_chunks:
            yield chunk

    with patch(
        "api.services.features.stream_perplexity_search",
        side_effect=mock_stream_perplexity,
    ):
        feature_service = FeatureService()
        result = []
        result = [context async for context in feature_service._stream_company_context(company_url)]  # pyright: ignore[reportPrivateUsage]

        assert result == expected_contexts


@pytest.mark.parametrize(
    "company_url, scraping_bee_response, expected_contexts",
    [
        (
            "example.com",
            FetchUrlContentResult(content="<html>Company content</html>", error=None),
            [CompanyContext(public="", private="<html>Company content</html>")],
        ),
        (
            "http://example.com",
            FetchUrlContentResult(content="<html>Different content</html>", error=None),
            [CompanyContext(public="", private="<html>Different content</html>")],
        ),
    ],
)
async def test_stream_company_context_perplexity_failure_scrapingbee_success(
    company_url: str,
    scraping_bee_response: FetchUrlContentResult,
    expected_contexts: list[CompanyContext],
) -> None:
    """Test _stream_company_context when Perplexity fails but ScrapingBee succeeds."""

    async def mock_stream_perplexity(*args: Any, **kwargs: Any) -> AsyncIterator[str]:
        raise Exception("Perplexity error")

    async def mock_fetch_url_content(*args: Any, **kwargs: Any) -> FetchUrlContentResult:
        return scraping_bee_response

    with (
        patch(
            "api.services.features.stream_perplexity_search",
            side_effect=mock_stream_perplexity,
        ),
        patch(
            "api.services.features.fetch_url_content_scrapingbee",
            side_effect=mock_fetch_url_content,
        ),
    ):
        feature_service = FeatureService()
        result = [context async for context in feature_service._stream_company_context(company_url)]  # pyright: ignore[reportPrivateUsage]

        assert result == expected_contexts


@pytest.mark.parametrize(
    "company_url, scraping_bee_error_response",
    [
        (
            "example.com",
            FetchUrlContentResult(content=None, error="content_not_reachable"),
        ),
        (
            "http://example.com",
            FetchUrlContentResult(content="", error="unknown_error"),
        ),
    ],
)
async def test_stream_company_context_both_services_fail(
    company_url: str,
    scraping_bee_error_response: FetchUrlContentResult,
) -> None:
    """Test _stream_company_context when both Perplexity and ScrapingBee fail."""

    async def mock_stream_perplexity(*args: Any, **kwargs: Any) -> AsyncIterator[str]:
        raise Exception("Perplexity error")

    async def mock_fetch_url_content(*args: Any, **kwargs: Any) -> FetchUrlContentResult:
        return scraping_bee_error_response

    with (
        patch(
            "api.services.features.stream_perplexity_search",
            side_effect=mock_stream_perplexity,
        ),
        patch(
            "api.services.features.fetch_url_content_scrapingbee",
            side_effect=mock_fetch_url_content,
        ),
    ):
        feature_service = FeatureService()
        result = [context async for context in feature_service._stream_company_context(company_url)]  # pyright: ignore[reportPrivateUsage]

        assert result == [
            CompanyContext(
                public=f"Could not get context from {company_url}, we'll fallback on generic features suggestions",
                private=f"Could not get context from {company_url}, we'll fallback on generic features suggestions",
            ),
        ]


async def test_get_agent_schemas() -> None:
    with patch(
        "api.services.features.run_agent_schema_generation",
        new_callable=AsyncMock,
        return_value=SchemaBuilderOutput(
            new_agent_schema=NewAgentSchema(
                input_schema=InputObjectFieldConfig(
                    name="mock input_schema",
                    fields=[
                        InputGenericFieldConfig(
                            name="input_string_field",
                            type=InputSchemaFieldType.STRING,
                        ),
                    ],
                ),
                output_schema=OutputObjectFieldConfig(
                    name="mock output_schema",
                    fields=[OutputStringFieldConfig(name="output_string_field")],
                ),
            ),
        ),
    ) as mock_run_agent_schema_and_preview:
        feature_service = FeatureService()
        schemas = await feature_service.get_agent_schemas(
            agent_name="Test Agent",
            agent_description="Test Description",
            agent_specifications="Test Specifications",
            company_context="Some company context",
        )

        mock_run_agent_schema_and_preview.assert_called_once_with(
            SchemaBuilderInput(
                agent_name="Test Agent",
                agent_description="Test Description",
                agent_specifications="Test Specifications",
                available_tools_description=officially_suggested_tools(),
                company_context="Some company context",
            ),
        )

        assert schemas == FeatureSchemas(
            input_schema={"type": "object", "properties": {"input_string_field": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"output_string_field": {"type": "string"}}},
        )
