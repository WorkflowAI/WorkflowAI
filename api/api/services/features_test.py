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
from api.tasks.agent_input_output_example import SuggestedAgentInputOutputExampleOutput
from api.tasks.agent_output_example import SuggestedAgentOutputExampleInput
from api.tasks.chat_task_schema_generation.chat_task_schema_generation_task import (
    InputGenericFieldConfig,
    InputObjectFieldConfig,
    InputSchemaFieldType,
    OutputObjectFieldConfig,
    OutputStringFieldConfig,
)
from api.tasks.chat_task_schema_generation.schema_generation_agent import (
    NewAgentSchema,
    SchemaBuilderInput,
    SchemaBuilderOutput,
)
from api.tasks.company_agent_suggestion_agent import (
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
                        FeatureSectionPreview.TagPreview(
                            name="example.com",
                            kind="company_specific",
                        ),  # Placeholder for where the company-specific features will go.
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
                    FeatureSectionPreview.TagPreview(
                        name="",
                        kind="company_specific",
                    ),  # Placeholder for where the company-specific features will go.
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
                                    description="Description 1",
                                    specifications="Spec 1",
                                ),
                                FeatureWithImage(
                                    name="Feature 2",
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
                    description="Description 1",
                    specifications="Spec 1",
                ),
                FeatureWithImage(
                    name="Feature 2",
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
                        SuggestedAgent(name="Feature A", description="Description A"),
                        SuggestedAgent(name="Feature B", description="Description B"),
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
                        BaseFeature(name="Feature A", description="Description A", specifications=""),
                        BaseFeature(name="Feature B", description="Description B", specifications=""),
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
                        SuggestedAgent(name="Generic Feature", description="Generic Description"),
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
                        BaseFeature(name="Generic Feature", description="Generic Description", specifications=""),
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

    async def mock_stream_feature_suggestions(*args: Any, **kwargs: Any) -> AsyncIterator[CompanyFeaturePreviewList]:
        for chunk in feature_suggestion_chunks:
            features: list[BaseFeature] = [
                BaseFeature(name=agent.name, description=agent.description or "", specifications="")
                for agent in chunk.suggested_agents or []
                if agent.name
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
            company_context=SuggestAgentForCompanyInput.CompanyContext(
                company_url=company_domain,
                company_url_content=company_context_chunks[0].private,
                existing_agents=[],
            ),
        )

    with (
        patch.object(service, "_stream_company_context", mock_stream_company_context),
        patch.object(service, "_build_agent_suggestion_input", mock_build_agent_suggestion_input),
        patch.object(service, "_stream_feature_suggestions", mock_stream_feature_suggestions),
    ):
        # Collect all outputs from the generator
        actual_outputs = [output async for output in service.get_features_by_domain(company_domain, Mock())]

        # Compare with expected outputs
        assert len(actual_outputs) == len(expected_outputs)
        for i, actual in enumerate(actual_outputs):
            expected = expected_outputs[i]
            assert actual.company_context == expected.company_context

            # Check feature previews
            if expected.features:
                assert len(actual.features or []) == len(expected.features)
                for j, feature in enumerate(actual.features or []):
                    assert feature.name == expected.features[j].name
                    assert feature.description == expected.features[j].description
            else:
                assert not actual.features or len(actual.features) == 0


@pytest.mark.parametrize(
    "company_domain, company_context, storage_available, expected_agent_types, expected_existing_agents",
    [
        (
            "example.com",
            "Example company info",
            True,
            ["type1", "type2"],  # Simplified for test
            ["agent1", "agent2"],
        ),
        (
            "example.com",
            "Example company info",
            False,
            ["type1", "type2"],
            [],  # No storage means no existing agents
        ),
    ],
)
async def test_build_agent_suggestion_input(
    company_domain: str,
    company_context: str,
    storage_available: bool,
    expected_agent_types: list[str],
    expected_existing_agents: list[str],
) -> None:
    """
    Test the _build_agent_suggestion_input method with various configurations.
    """
    # Create mocks for the imported functions
    with (
        patch("api.services.features.get_supported_task_input_types", return_value=expected_agent_types),
        patch("api.services.features.get_supported_task_output_types", return_value=expected_agent_types),
        patch("api.services.features.safe_map", return_value=[]),
        patch("api.services.features.list_agent_summaries", return_value=expected_existing_agents),
    ):
        # Create service with or without storage
        mock_storage = Mock() if storage_available else None
        service = FeatureService(storage=mock_storage)

        # Call the method
        result = await service._build_agent_suggestion_input(company_domain, company_context, "")  # pyright: ignore[reportPrivateUsage]

        # Verify the result
        assert result.supported_agent_input_types == expected_agent_types
        assert result.supported_agent_output_types == expected_agent_types
        assert result.company_context
        assert result.company_context.company_url == company_domain
        assert result.company_context.company_url_content == company_context

        if storage_available:
            assert result.company_context.existing_agents == expected_existing_agents
        else:
            assert result.company_context.existing_agents == []


@pytest.mark.parametrize(
    "company_context, input_agents, expected_outputs",
    [
        (
            "Example company",
            [
                SuggestAgentForCompanyOutput(
                    suggested_agents=[
                        SuggestedAgent(name="Feature 1", description="Description 1"),
                        SuggestedAgent(name="Feature 2", description="Description 2"),
                    ],
                ),
            ],
            [
                CompanyFeaturePreviewList(
                    company_context="Example company",
                    features=[
                        BaseFeature(name="Feature 1", description="Description 1", specifications=""),
                        BaseFeature(name="Feature 2", description="Description 2", specifications=""),
                    ],
                ),
            ],
        ),
        (
            "Example company",
            [
                SuggestAgentForCompanyOutput(
                    suggested_agents=[
                        # Simulate a bug in the SDK
                        {"name": "Feature Dict", "description": "Description Dict"},  # pyright: ignore[reportArgumentType]
                        SuggestedAgent(name="Feature Object", description="Description Object"),
                    ],
                ),
            ],
            [
                CompanyFeaturePreviewList(
                    company_context="Example company",
                    features=[
                        BaseFeature(name="Feature Dict", description="Description Dict", specifications=""),
                        BaseFeature(name="Feature Object", description="Description Object", specifications=""),
                    ],
                ),
            ],
        ),
        (
            "Example company",
            [
                SuggestAgentForCompanyOutput(
                    suggested_agents=[
                        SuggestedAgent(name="", description="Missing name"),  # Should be skipped
                        SuggestedAgent(name="Valid", description=None),  # Empty description
                    ],
                ),
            ],
            [
                CompanyFeaturePreviewList(
                    company_context="Example company",
                    features=[
                        BaseFeature(name="Valid", description="", specifications=""),
                    ],
                ),
            ],
        ),
    ],
)
async def test_stream_feature_suggestions(
    company_context: str,
    input_agents: list[SuggestAgentForCompanyOutput],
    expected_outputs: list[CompanyFeaturePreviewList],
) -> None:
    """
    Test the _stream_feature_suggestions method with various inputs.
    """
    service = FeatureService()

    # Mock the stream_suggest_agents_for_company function
    async def mock_stream(*args: Any, **kwargs: Any) -> AsyncIterator[SuggestAgentForCompanyOutput]:
        for agent_output in input_agents:
            yield agent_output

    with patch("api.services.features.stream_suggest_agents_for_company", mock_stream):
        # Call the method with any input (it will be ignored due to our mock)
        mock_input = Mock()

        # Collect all outputs
        actual_outputs = [output async for output in service._stream_feature_suggestions(company_context, mock_input)]  # pyright: ignore[reportPrivateUsage]

        # Compare with expected outputs
        assert len(actual_outputs) == len(expected_outputs)
        for i, actual in enumerate(actual_outputs):
            expected = expected_outputs[i]
            assert actual.company_context == expected.company_context

            # Check feature previews
            assert len(actual.features or []) == len(expected.features or [])
            for j, feature in enumerate(actual.features or []):
                assert expected.features is not None
                assert feature.name == expected.features[j].name
                assert feature.description == expected.features[j].description


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
