import datetime
import logging
from enum import Enum
from typing import AsyncIterator, Literal, NamedTuple

import workflowai
from pydantic import BaseModel, Field

from api.services.api_keys import APIKeyService, find_api_key_in_text
from api.services.documentation_service import DocumentationService
from api.services.runs.runs_service import RunsService
from api.services.versions import VersionsService
from core.agents.agent_name_suggestion_agent import (
    AGENT_ID as AGENT_NAME_SUGGESTION_AGENT_ID,
)
from core.agents.agent_name_suggestion_agent import (
    AgentNameSuggestionAgentInput,
    agent_name_suggestion_agent,
)
from core.agents.integration_agent import (
    INTEGRATION_AGENT_INSTRUCTIONS,
    IntegrationAgentChatMessage,
    IntegrationAgentInput,
    integration_chat_agent,
)
from core.agents.integration_code_block_agent import IntegrationCodeSnippetAgentInput, integration_code_snippet_agent
from core.constants import DEFAULT_AGENT_ID
from core.domain.agent_run import AgentRun
from core.domain.errors import ObjectNotFoundError
from core.domain.events import EventRouter
from core.domain.fields.chat_message import ChatMessage
from core.domain.integration.integration_domain import (
    Integration,
    IntegrationKind,
)
from core.domain.integration.integration_mapping import (
    OFFICIAL_INTEGRATIONS,
    PROPOSED_AGENT_NAME_AND_MODEL_PLACEHOLDER,
    WORKFLOWAI_API_KEY_PLACEHOLDER,
    get_integration_by_kind,
)
from core.domain.task_variant import SerializableTaskVariant
from core.domain.users import User
from core.storage import ObjectNotFoundException, TaskTuple
from core.storage.backend_storage import BackendStorage
from core.utils.redis_cache import redis_cached


class ApiKeyResult(NamedTuple):
    api_key: str
    was_existing: bool


class VersionCode(BaseModel):
    code: str
    integration: Integration


class RelevantRunAndAgent(NamedTuple):
    run: AgentRun
    agent: SerializableTaskVariant


class MessageKind(Enum):
    api_key_code_snippet = "initial_code_snippet"  # The initial message that is sent to the user to show how to integrate WorkflowAI into their code
    agent_naming_code_snippet = "agent_name_definition_code_snippet"  # The message that is sent to the user to show how to define the agent name
    non_specific = "non_specific"  # Any other message that is not one of the above


class IntegrationChatMessage(BaseModel):
    sent_at: datetime.datetime

    role: Literal["USER", "ASSISTANT"] = Field(
        description="The role of the message sender, 'USER' is the actual human user, 'PLAYGROUND' are automated messages, and 'ASSISTANT' is the agent.",
    )
    content: str = Field(
        description="The content of the message",
    )

    message_kind: MessageKind = Field(
        description="The kind of message that is being sent to the user",
        default=MessageKind.non_specific,
    )


class PlaygroundRedirection(BaseModel):
    agent_id: str
    agent_schema_id: int


class IntegrationChatResponse(BaseModel):
    messages: list[IntegrationChatMessage]
    redirect_to_agent_playground: PlaygroundRedirection | None = None


class ObfuscatedString(BaseModel):
    original: str
    obfuscated: str

    def __hash__(self) -> int:
        return hash(self.original + self.obfuscated)


class IntegrationService:
    def __init__(
        self,
        storage: BackendStorage,
        event_router: EventRouter,
        runs_service: RunsService,
        api_keys_service: APIKeyService,
        user: User,
    ):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.storage = storage
        self.event_router = event_router
        self.runs_service = runs_service
        self.api_keys_service = api_keys_service
        self.user = user
        self.obfuscated_strings: set[ObfuscatedString] = set()

    def _get_integration_for_slug(self, slug: IntegrationKind) -> Integration:
        integration = next(
            (integ for integ in OFFICIAL_INTEGRATIONS if integ.slug == slug),
            None,
        )
        if not integration:
            raise ObjectNotFoundError(f"Integration with slug '{slug}' not found in OFFICIAL_INTEGRATIONS.")

        return integration

    async def _build_integration_chat_agent_input(
        self,
        messages: list[IntegrationChatMessage],
        integration: Integration,
    ) -> IntegrationAgentInput:
        doc_service = DocumentationService()
        try:
            relevant_documentation_sections = await doc_service.get_relevant_doc_sections(
                chat_messages=[ChatMessage(role=message.role, content=message.content) for message in messages],
                agent_instructions=INTEGRATION_AGENT_INSTRUCTIONS,
            )
        except Exception as e:
            self._logger.exception("Error getting relevant documentation sections", exc_info=e)
            relevant_documentation_sections = []

        try:
            # Makes sure the integration documentation sections are always included
            integration_documentation_sections = doc_service.get_documentation_by_path(
                integration.documentation_filepaths,
            )
        except Exception as e:
            self._logger.exception("Error getting integration documentation sections", exc_info=e)
            integration_documentation_sections = []

        return IntegrationAgentInput(
            current_datetime=datetime.datetime.now(),
            integration=integration,
            messages=self._get_integration_agent_chat_messages(messages),
            documentation=list(
                set(relevant_documentation_sections + integration_documentation_sections),  # Deduplicate
            ),
        )

    @staticmethod
    def _get_initial_code_snippet_messages(
        now: datetime.datetime,
        integration: Integration,
        api_key_result: ApiKeyResult,
    ) -> IntegrationChatMessage:
        if api_key_result.was_existing:
            api_key_message = f'"{api_key_result.api_key}", # Use your existing WorkflowAI key'
        else:
            api_key_message = f"{api_key_result.api_key}, # Use your new WorkflowAI key"

        MESSAGE_CONTENT = f"""Great. To get started, there are two small code changes needed to use WorkflowAI with your AI agent. You will need to:
Replace your OPENAI_API_KEY with your WORKFLOWAI_API_KEY.
Set the api_base to WorkflowAI's chat completion endpoint URL.

```
{
            integration.integration_chat_initial_snippet.replace(
                WORKFLOWAI_API_KEY_PLACEHOLDER,
                api_key_message,
            )
        }
```

Then, you will need to actually execute ▶️ this code to make your agent first agent run on WorkflowAI.
As soon as your first run is received, we'll take you to the Playground so you can start comparing models!
If you have any questions, just let me know!
"""

        return IntegrationChatMessage(
            sent_at=now,
            role="ASSISTANT",
            content=MESSAGE_CONTENT,
            message_kind=MessageKind.api_key_code_snippet,
        )

    @staticmethod
    def _get_agent_naming_code_snippet_messages(
        now: datetime.datetime,
        proposed_agent_name: str,
        model: str,
        integration: Integration,
    ) -> IntegrationChatMessage:
        MESSAGE_CONTENT = f"""Congratulations on sending your first run 🎉!
Looks like you're building a `{
            proposed_agent_name
        }` agent, one more step is to update the 'model' in the code to get the agent prefix so that things are
well organized (by agent) on WorkflowAI (trust me, makes everything easier).

```
{
            integration.integration_chat_agent_naming_snippet.replace(
                PROPOSED_AGENT_NAME_AND_MODEL_PLACEHOLDER,
                f"{proposed_agent_name}/{model}",
            )
        }
```
"""
        return IntegrationChatMessage(
            sent_at=now,
            role="ASSISTANT",
            content=MESSAGE_CONTENT,
            message_kind=MessageKind.agent_naming_code_snippet,
        )

    def _obfuscate_api_keys(self, text: str) -> str:
        api_keys = find_api_key_in_text(text)
        for api_key in api_keys:
            self.obfuscated_strings.add(ObfuscatedString(original=api_key, obfuscated=api_key[:9] + "****"))
            text = text.replace(api_key, f"{api_key[:9]}****")
        return text

    def _deobfuscate_api_keys(self, text: str) -> str:
        for obfuscated_string in self.obfuscated_strings:
            text = text.replace(obfuscated_string.obfuscated, obfuscated_string.original)
        return text

    def _get_integration_agent_chat_messages(
        self,
        messages: list[IntegrationChatMessage],
    ) -> list[IntegrationAgentChatMessage]:
        return [
            IntegrationAgentChatMessage(
                role=message.role,
                # Make sure we don't send any API key to the agent.
                content=self._obfuscate_api_keys(message.content),
            )
            for message in messages
        ]

    async def has_sent_agent_naming_code_snippet(self, messages: list[IntegrationChatMessage]) -> bool:
        return any(message.message_kind == MessageKind.agent_naming_code_snippet for message in messages)

    @redis_cached(expiration_seconds=60 * 60)  # TTL=1 hour
    async def _get_agent_by_uid(self, uid: int) -> SerializableTaskVariant:
        # Since the frontend will poll to listen for incoming runs, we cache the agent fetching.
        return await self.storage.task_variants.get_task_variant_by_uid(uid)

    async def _find_relevant_run_and_agent(
        self,
        discussion_started_at: datetime.datetime,
    ) -> RelevantRunAndAgent | None:
        """
        The goals of this functions is to spot a run / agent that was (very likely) created by the user currently doing the onboarding flow.
        """

        async for run in self.storage.task_runs.list_latest_runs(
            since_date=discussion_started_at,
            is_active=True,  # TODO: filter on proxy runs
            limit=2,  # TODO: pick a better limit
        ):
            agent = await self._get_agent_by_uid(run.task_uid)

            # There is a change we are capturing a pre-existing, unnamed agent run here, but this is pretty rare, and low impact
            # Especially since the proposed agent name we'll compute will allow the user to understand where the captured run is coming
            # And this will hopefully convince them to name the pre-existing, unnamed agent.
            if agent.task_id == DEFAULT_AGENT_ID:
                return RelevantRunAndAgent(run=run, agent=agent)

            # If the agent is already named we just check that it was created after the discussion started
            if agent.created_at > discussion_started_at:
                return RelevantRunAndAgent(run=run, agent=agent)

        return None

    async def _get_api_key(self) -> ApiKeyResult:
        exisitng_api_key = await self.api_keys_service.get_keys()
        if exisitng_api_key:
            return ApiKeyResult(api_key=exisitng_api_key[0].partial_key, was_existing=True)

        _, api_key = await self.api_keys_service.create_key("workflowai-api-key", self.user.identifier(), 3)

        return ApiKeyResult(api_key=api_key, was_existing=False)

    async def stream_integration_chat_response(
        self,
        integration_slug: IntegrationKind,
        messages: list[IntegrationChatMessage],
    ) -> AsyncIterator[IntegrationChatResponse]:
        integration = self._get_integration_for_slug(integration_slug)
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        if len(messages) == 0:
            # This is the beginning of the onboarding discussion, we'll send the initial code snippet
            yield IntegrationChatResponse(
                messages=[
                    self._get_initial_code_snippet_messages(
                        now,
                        integration,
                        await self._get_api_key(),
                    ),
                ],
            )
            return

        latest_message = messages[-1]

        if latest_message.role == "ASSISTANT":
            # That means the frontend is just polling and we need to check if we received runs

            relevant_run_and_agent = await self._find_relevant_run_and_agent(discussion_started_at=messages[0].sent_at)

            if relevant_run_and_agent is None:
                # No relevant run and agent found, we'll just wait for the next polling from the frontend or a new message from the user
                yield IntegrationChatResponse(
                    messages=[],
                )
                return

            if relevant_run_and_agent.agent.task_id not in [DEFAULT_AGENT_ID, AGENT_NAME_SUGGESTION_AGENT_ID]:
                # The relevant agent is already named, we can redirect to the playground
                # We filter out the agent name suggestion agent, this is mostly useful for debugging
                # Where the onboarded user is from workflowai.

                # Register the integration used for the agent, so we can provide pertinent answers in the playground chat
                await self.storage.task_variants.update_task(
                    relevant_run_and_agent.agent.task_id,
                    used_integration_kind=integration_slug,
                )

                yield IntegrationChatResponse(
                    messages=[],
                    redirect_to_agent_playground=PlaygroundRedirection(
                        agent_id=relevant_run_and_agent.agent.task_id,
                        agent_schema_id=relevant_run_and_agent.agent.task_schema_id,
                    ),
                )
                return

            if not await self.has_sent_agent_naming_code_snippet(messages):
                # We need to propose and agent name for the relevant run
                proposed_agent_name_run = await agent_name_suggestion_agent.run(
                    AgentNameSuggestionAgentInput(
                        raw_llm_content=str(
                            relevant_run_and_agent.run.llm_completions,
                        ),  # Dump everything in the content
                    ),
                )
                # Send the agent naming suggestion code snippet
                yield IntegrationChatResponse(
                    messages=[
                        self._get_agent_naming_code_snippet_messages(
                            now,
                            proposed_agent_name_run.output.agent_name,
                            relevant_run_and_agent.run.group.properties.model or workflowai.Model.GPT_4O_LATEST,
                            integration,
                        ),
                    ],
                )
                return

            # This is the case where the fronted is polling after the agent naming suggestion has been sent, but the user hasn't run the named agent yet
            yield IntegrationChatResponse(
                messages=[],
            )
            return

        # After this point, we know the user triggered the action.
        integration_agent_input = await self._build_integration_chat_agent_input(
            messages,
            integration,
        )

        # Actually run the integration chat agent
        async for chunk in integration_chat_agent.stream(integration_agent_input, temperature=0.5):
            if chunk.output.content:
                yield IntegrationChatResponse(
                    messages=[
                        IntegrationChatMessage(
                            sent_at=now,
                            role="ASSISTANT",
                            content=self._deobfuscate_api_keys(chunk.output.content),
                            message_kind=MessageKind.non_specific,
                        ),
                    ],
                )

    async def _get_messages_payload_for_code_snippet(
        self,
        version: VersionsService.EnrichedVersion,
        task_tuple: TaskTuple,
        task_schema_id: int,
    ) -> str:
        if version.group.properties.messages:
            return str(
                [m.model_dump() for m in version.group.properties.messages],
            )

        # Then we'll need to fetch the messages from the latest task run, if any.
        try:
            latest_run = await self.runs_service.latest_run(
                task_uid=task_tuple,
                schema_id=task_schema_id,
                is_success=True,
                exclude_fields=set(),  # We do want the 'llm_completions'
            )
            version_messages_payload = str(latest_run.task_input)

        except ObjectNotFoundException:
            self._logger.warning(
                "No successful run found for task tuple %s, schema id %s",
                task_tuple,
                task_schema_id,
            )
            # Fallback to a default system message if no successful run is found
            version_messages_payload = str(
                [
                    {
                        "role": "system",
                        "content": "You're a helpful assistant.",
                    },
                ],
            )

        return version_messages_payload

    async def stream_code_for_version(
        self,
        task_tuple: TaskTuple,
        task_schema_id: int,
        version: VersionsService.EnrichedVersion,
        forced_integration_kind: IntegrationKind | None = None,
    ) -> AsyncIterator[VersionCode]:
        if not version.variant:
            raise ObjectNotFoundError(f"Can't resolve the agent for version {version.group.id}")

        agent = version.variant

        integration = get_integration_by_kind(
            forced_integration_kind or agent.used_integration_kind or IntegrationKind.OPENAI_SDK_PYTHON,
        )

        version_messages = await self._get_messages_payload_for_code_snippet(version, task_tuple, agent.task_schema_id)
        doc_gen_input = IntegrationCodeSnippetAgentInput(
            integration=integration,
            agent_id=agent.task_id,
            agent_schema_id=agent.task_schema_id,
            model_used=version.group.properties.model or workflowai.DEFAULT_MODEL,
            version_messages=version_messages,
            integration_documentations=DocumentationService().get_documentation_by_path(
                integration.documentation_filepaths,
            ),
            version_deployment_environment=version.deployments[0].environment if version.deployments else None,
            is_using_instruction_variables=agent.input_schema.json_schema.get("properties", None) is not None,
            input_schema=agent.input_schema.json_schema,
            is_using_structured_generation=not agent.output_schema.json_schema.get("format") == "message",
            output_schema=agent.output_schema.json_schema,
        )

        async for chunk in integration_code_snippet_agent(doc_gen_input):
            yield VersionCode(
                code=chunk,
                integration=integration,
            )


class IntegrationCodeBlockAgentOutput(NamedTuple):
    code: str
