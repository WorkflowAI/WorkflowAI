import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any, NamedTuple

from pydantic import BaseModel

from api.services.internal_tasks._internal_tasks_utils import officially_suggested_tools
from api.services.internal_tasks.agent_suggestions_service import (
    get_supported_task_input_types,
    get_supported_task_output_types,
)
from api.services.slack_notifications import SlackNotificationDestination, get_user_and_org_str, send_slack_notification
from api.services.tasks import list_agent_summaries
from api.tasks.agent_output_example import SuggestedAgentOutputExampleInput, stream_suggested_agent_output_example
from api.tasks.chat_task_schema_generation.chat_task_schema_generation_task_utils import build_json_schema_with_defs
from api.tasks.chat_task_schema_generation.schema_generation_agent import (
    SchemaBuilderInput,
    run_agent_schema_generation,
)
from api.tasks.company_agent_suggestion_agent import (
    SuggestAgentForCompanyInput,
    SuggestedAgent,
    stream_suggest_agents_for_company,
)
from api.tasks.company_domain_from_email_agent import (
    ClassifyEmailDomainAgentInput,
    ClassifyEmailDomainAgentOutput,
    run_classify_email_domain_agent,
)
from core.domain.errors import InternalError, ObjectNotFoundError
from core.domain.events import EventRouter, FeaturesByDomainGenerationStarted
from core.domain.features import BaseFeature, tag_kind
from core.domain.features_mapping import FEATURES_MAPPING
from core.runners.workflowai.workflowai_runner import WorkflowAIRunner
from core.storage.backend_storage import BackendStorage
from core.tools.browser_text.browser_text_tool import fetch_url_content_scrapingbee
from core.tools.search.run_perplexity_search import stream_perplexity_search
from core.utils.iter_utils import safe_map
from core.utils.schema_utils import json_schema_from_json

_logger = logging.getLogger(__name__)


class FeatureSectionPreview(BaseModel):
    name: str

    class TagPreview(BaseModel):
        name: str
        kind: tag_kind

    tags: list[TagPreview]


class FeatureList(BaseModel):
    features: list[BaseFeature] | None = None


class CompanyFeaturePreviewList(BaseModel):
    company_context: str | None = None
    features: list[BaseFeature] | None = None


class FeatureOutputPreview(BaseModel):
    output_schema_preview: dict[str, Any] | None = None
    output_preview: dict[str, Any] | None = None


class FeatureSchemas(BaseModel):
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None


class CompanyContext(NamedTuple):
    """Wrapper for company context.

    Most times 'public' will be equal to 'private', but if Perplexity fails to return a relevant company description,
    the feature suggestion agent will use raw HTML content from the company domain and we do not want to expose that to the frontend.
    """

    public: str  # To be return to the frontend
    private: str  # To be used by the feature suggestion agent


class FeatureService:
    def __init__(self, storage: BackendStorage | None = None):
        self.storage = storage

    @staticmethod
    async def _is_company_email_domain(user_email_domain: str) -> bool:
        try:
            company_domain_classification = await run_classify_email_domain_agent(
                ClassifyEmailDomainAgentInput(email_domain=user_email_domain),
            )
            return company_domain_classification.result == ClassifyEmailDomainAgentOutput.Result.COMPANY_EMAIL_DOMAIN
        except Exception as e:
            _logger.exception("Error classifying email domain", exc_info=e)
            # If anything wrong happens, we'll show the company-specific features, since it's less bad to show "gmail.com" to non-company users
            # Than to hide the company-specific features for real company users
            return True

    @staticmethod
    async def get_feature_sections_preview(user_domain: str | None = None) -> list[FeatureSectionPreview]:
        # We want to show company specific section for anonymous user because they must be able to enter any URL and get suggestion for this URL.
        show_company_section = user_domain is None or await FeatureService._is_company_email_domain(user_domain)

        return [
            FeatureSectionPreview(
                name=section.name,
                tags=[
                    FeatureSectionPreview.TagPreview(
                        name=user_domain  # fills the company_specific" name section with the company name
                        if user_domain and tag.kind == "company_specific"
                        else tag.name,
                        kind=tag.kind,
                    )
                    for tag in section.tags
                    # If the user's email domain is not a company email domain, we don't want to show the "company_specific" section
                    if tag.kind != "company_specific" or show_company_section
                ],
            )
            for section in FEATURES_MAPPING
        ]

    @staticmethod
    async def get_features_by_tag(
        tag: str,
    ) -> AsyncIterator[list[BaseFeature]]:
        accumulated_features: list[BaseFeature] = []

        for section in FEATURES_MAPPING:
            for feature_tag in section.tags:
                if feature_tag.name.lower() == tag.lower():
                    for feature in feature_tag.features:
                        accumulated_features.append(feature)
                        yield accumulated_features
                    return

        raise ObjectNotFoundError(msg=f"No feature tag found with tag: {tag}")

    async def _stream_company_context(self, company_url: str) -> AsyncIterator[CompanyContext]:
        try:
            async for chunk in stream_perplexity_search(
                f"What does this company do:{company_url} ? Provide a concise description of the company and its products. Do not add any markdown or formatting (ex: bold, italic, underline, etc.) in the response, except line breaks, punctation and eventual bullet points.",
            ):
                yield CompanyContext(public=chunk, private=chunk)
        except Exception as e:
            # If anything wrong happens with Perplexity, we'll try to get the company description from the URL content with ScrapingBee
            _logger.exception("Error getting company description from Perplexity", exc_info=e)

            try:
                raw_url_content = await fetch_url_content_scrapingbee(
                    company_url if company_url.startswith("http") else f"http://{company_url}",
                )
                if not raw_url_content.error and raw_url_content.content:
                    # In this case, we have managed to get the URL content, we don't want to display a warning in the UI, but
                    # the feature suggestion agent will use the raw HTML content as company context
                    yield CompanyContext(public="", private=raw_url_content.content)
                    return
                else:
                    _logger.error(
                        f"Error getting company description from browser text: {raw_url_content.error}",  # noqa: G004
                    )

            except Exception as e:
                _logger.exception("Error getting company description from browser text", exc_info=e)

            fallback_message = (
                f"Could not get context from {company_url}, we'll fallback on generic features suggestions"
            )

            # Perplexity and Scrapping has failed, we'll fallback on a generic message for bot
            # The fallback message will be displayed in the UI and be passed to the feature
            # For established companies, there are good chances the LLM knows about them just based on the URL
            # and will be able to provide some decent feature suggestions
            yield CompanyContext(public=fallback_message, private=fallback_message)

    async def _build_agent_suggestion_input(
        self,
        company_domain: str,
        company_context: str,
        latest_news: str,
    ) -> SuggestAgentForCompanyInput:
        return SuggestAgentForCompanyInput(
            supported_agent_input_types=get_supported_task_input_types(),
            supported_agent_output_types=get_supported_task_output_types(),
            available_tools=safe_map(
                WorkflowAIRunner.internal_tools.values(),
                SuggestAgentForCompanyInput.ToolDescription.from_internal_tool,
            ),
            company_context=SuggestAgentForCompanyInput.CompanyContext(
                company_url=company_domain,
                company_url_content=company_context,
                existing_agents=[str(a) for a in await list_agent_summaries(self.storage, limit=10)]
                if self.storage
                else [],
                latest_news=latest_news,
            ),
        )

    async def _stream_feature_suggestions(
        self,
        company_context: str,
        input: SuggestAgentForCompanyInput,
    ) -> AsyncIterator[CompanyFeaturePreviewList]:
        async for chunk in stream_suggest_agents_for_company(input):
            features: list[BaseFeature] = []
            for agent in chunk.suggested_agents or []:
                if isinstance(agent, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
                    # For some reason, a dict is sometimes returned instead of a SuggestedAgent
                    # TODO: investigate SDK
                    safe_agent = SuggestedAgent.model_validate(agent)
                else:
                    safe_agent = agent
                if safe_agent.name:
                    features.append(
                        BaseFeature(
                            name=safe_agent.name,
                            description=safe_agent.description or "",
                            specifications="",  # Specifications are not used for company-specific features
                        ),
                    )

            yield CompanyFeaturePreviewList(
                company_context=company_context,
                features=features,
            )

    async def _get_company_latest_news(self, company_domain: str) -> str:
        try:
            result = ""
            async for chunk in stream_perplexity_search(
                f"You are a world-class expert in software market intelligence with an emphasis on tech startups and artificial intelligence. You goal is to gather and summarize the latest news for {company_domain}, especially new product and new features. Any product or feature mentioned must also explain what the feature/product does. Focus on software oriented features and products. Stay concise and to the point.",
                max_tokens=250,
            ):
                result = chunk
            return result
        except Exception as e:
            _logger.exception("Error getting company latest news", exc_info=e)
            return ""

    async def get_features_by_domain(
        self,
        company_domain: str,
        event_router: EventRouter,
    ) -> AsyncIterator[CompanyFeaturePreviewList]:
        event_router(FeaturesByDomainGenerationStarted(company_domain=company_domain))

        # Start collecting AI features in the background
        company_latest_news_task = asyncio.create_task(self._get_company_latest_news(company_domain))

        company_context: CompanyContext = CompanyContext(public="", private="")
        async for chunk in self._stream_company_context(company_domain):
            company_context = chunk
            yield CompanyFeaturePreviewList(
                company_context=company_context.public,
                features=[],
            )

        # Wait for AI features collection to complete
        company_latest_news = await company_latest_news_task

        agent_suggestion_input = await self._build_agent_suggestion_input(
            company_domain,
            company_context.private,
            company_latest_news,
        )

        async for chunk in self._stream_feature_suggestions(company_context.public, agent_suggestion_input):
            yield chunk

    async def notify_features_by_domain_generation_started(self, event: FeaturesByDomainGenerationStarted):
        user_and_org_str = get_user_and_org_str(event=event)
        message = f"{user_and_org_str} started to generate features for domain: {event.company_domain}"

        await send_slack_notification(
            message=message,
            user_email=event.user_properties.user_email if event.user_properties else None,
            destination=SlackNotificationDestination.CUSTOMER_JOURNEY,
        )

    @classmethod
    async def get_agent_preview(
        cls,
        agent_name: str,
        agent_description: str,
        agent_specifications: str | None = None,
        company_context: str | None = None,
    ) -> AsyncIterator[FeatureOutputPreview]:
        async for chunk in stream_suggested_agent_output_example(
            SuggestedAgentOutputExampleInput(
                agent_name=agent_name,
                agent_description=agent_description,
                agent_specifications=agent_specifications,
                company_context=company_context,
            ),
        ):
            yield FeatureOutputPreview(
                output_schema_preview=json_schema_from_json(chunk.agent_output_example)
                if chunk.agent_output_example
                else None,
                output_preview=chunk.agent_output_example,
            )

    @classmethod
    async def get_agent_schemas(
        cls,
        agent_name: str,
        agent_description: str,
        agent_specifications: str | None = None,
        company_context: str | None = None,
    ) -> FeatureSchemas:
        schema_run = await run_agent_schema_generation(
            SchemaBuilderInput(
                agent_name=agent_name,
                agent_description=agent_description,
                agent_specifications=agent_specifications,
                company_context=company_context,
                available_tools_description=officially_suggested_tools(),
            ),
        )

        if not schema_run.new_agent_schema:
            raise InternalError(msg="No new agent schema returned from the schema builder")
        input_schema = build_json_schema_with_defs(schema_run.new_agent_schema.input_schema)
        output_schema = build_json_schema_with_defs(schema_run.new_agent_schema.output_schema)

        return FeatureSchemas(input_schema=input_schema, output_schema=output_schema)

    @classmethod
    def validate_tag_uniqueness(cls) -> dict[str, list[str]]:
        """Validate that each tag name appears only once in the feature mapping.

        Returns:
            A dictionary mapping duplicate tag names to the sections they appear in
        """
        tag_to_sections: dict[str, list[str]] = defaultdict(list)

        for section in FEATURES_MAPPING:
            for feature_tag in section.tags:
                tag_name = feature_tag.name.lower()
                tag_to_sections[tag_name].append(section.name)

        return {tag: sections for tag, sections in tag_to_sections.items() if len(sections) > 1}
