from unittest.mock import Mock

import pytest

from core.domain.models import Model, Provider
from core.runners.workflowai.provider_pipeline import ProviderPipeline, ProviderPipelineBuilder
from core.runners.workflowai.workflowai_options import WorkflowAIRunnerOptions


@pytest.fixture
def provider_builder():
    builder = Mock(spec=ProviderPipelineBuilder)
    # Last argument is the model data
    builder.side_effect = lambda *args: (Mock(), Mock(), Mock(), args[1])  # type: ignore
    return builder


# TODO: The tests are based on the real model data, we should patch
class TestProviderIterator:
    def test_claude_ordering_and_support(self, provider_builder: Mock, mock_provider_factory: Mock):
        pipeline = ProviderPipeline(
            options=WorkflowAIRunnerOptions(
                model=Model.CLAUDE_3_5_SONNET_20241022,
                provider=None,
                is_structured_generation_enabled=None,
                instructions="",
            ),
            provider_config=None,
            builder=provider_builder,
            factory=mock_provider_factory,
        )

        # List all providers
        providers = list(pipeline.provider_iterator())
        assert len(providers) == 2

        assert provider_builder.call_count == 2

        provider_1 = provider_builder.call_args_list[0].args[0]
        assert provider_1.name() == Provider.AMAZON_BEDROCK
        # Testing the override
        assert not providers[0][-1].supports_input_pdf

        provider_2 = provider_builder.call_args_list[1].args[0]
        assert provider_2.name() == Provider.ANTHROPIC
        assert providers[1][-1].supports_input_pdf
