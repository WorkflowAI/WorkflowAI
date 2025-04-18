import asyncio
import json
import logging
import os
import re
from contextlib import contextmanager
from datetime import datetime, timedelta

from pydantic import BaseModel

from api.services import tasks
from api.services.customer_assessment_service import CustomerAssessmentService
from api.services.features import CompanyFeaturePreviewList, FeatureService
from core.domain.analytics_events.analytics_events import UserProperties
from core.domain.consts import ENV_NAME, WORKFLOWAI_APP_URL
from core.domain.daily_user_digest import DailyUserDigest
from core.domain.errors import InternalError
from core.domain.events import (
    Event,
    FeaturesByDomainGenerationStarted,
    MetaAgentChatMessagesSent,
    TaskSchemaCreatedEvent,
)
from core.services.users.user_service import OrganizationDetails, UserDetails, UserService
from core.storage import ObjectNotFoundException
from core.storage.backend_storage import BackendStorage
from core.storage.slack.slack_api_client import SlackApiClient
from core.storage.slack.utils import get_slack_hyperlink
from core.utils.background import add_background_task

_logger = logging.getLogger(__name__)

WORKFLOW_APP_URL = os.environ.get("WORKFLOWAI_APP_URL", "https://workflowai.com")


def _get_task_url(event: Event, task_id: str, task_schema_id: int) -> str | None:
    organization_slug = event.organization_properties.organization_slug if event.organization_properties else None
    if organization_slug is None:
        return None

    base_domain = os.environ.get("WORKFLOWAI_APP_URL")
    if base_domain is None:
        return None

    # Not super solid, will break if we change the task URL format in the web app, but we can't access the webapp URL schema from here.
    # Additionally, this code is purely for notification purposes, so it's not critical for the clients
    return f"{base_domain}/{organization_slug}/agents/{task_id}/{task_schema_id}"


def _get_task_str_for_slack(event: Event, task_id: str, task_schema_id: int) -> str:
    task_str = task_id
    task_url = _get_task_url(event=event, task_id=task_id, task_schema_id=task_schema_id)
    if task_url is not None:
        task_str = get_slack_hyperlink(url=task_url, text=task_str)
    return task_str


class SlackMessageFormatter:
    @classmethod
    def get_feature_preview_list_slack_message(
        cls,
        company_domain: str,
        features_suggestions: CompanyFeaturePreviewList | None,
    ) -> str:
        if not features_suggestions or not features_suggestions.features or len(features_suggestions.features) == 0:
            return "No suggested AI roadmap for this customer because the agent did not find any good enough feature"

        DELIMITER = "\n\n-----------------------------------\n\n"

        features_str = DELIMITER.join([feature.display_str for feature in features_suggestions.features])

        return f"🗺️ Suggested AI Roadmap for {company_domain}: {DELIMITER}\n{features_str}"

    @classmethod
    def get_daily_user_digest_slack_message(cls, daily_digest: DailyUserDigest) -> str:
        DELIMITER = "\n\n-----------------------------------\n\n"

        def _get_agent_str(agent: DailyUserDigest.Agent) -> str:
            parts: list[str] = [
                f"*{agent.name}*",
                "\n",
            ]
            if agent.description:
                parts.append(f"{agent.description}")

            parts.append("\n")
            parts.append(
                f"{WORKFLOW_APP_URL}/{daily_digest.tenant_slug}/agents/{agent.agent_id}/{agent.agent_schema_id}",
            )

            parts.append("\n")
            parts.append(f"Runs (last 24h): {agent.run_count_last_24h}")
            if agent.active_run_count_last_24h:
                parts.append(f"({agent.active_run_count_last_24h} active)")

            return "".join(parts)

        return f"""*Daily User Digest for {daily_digest.for_date.strftime("%Y-%m-%d")}*{DELIMITER}{DELIMITER.join([_get_agent_str(agent) for agent in daily_digest.agents])}"""


class CustomerService:
    _SLEEP_BETWEEN_RETRIES = 0.1

    def __init__(self, storage: BackendStorage, user_service: UserService):
        self._storage = storage
        self._user_service = user_service

    def _channel_name(self, slug: str, uid: int):
        prefix = "customer" if ENV_NAME == "prod" else f"customer-{ENV_NAME}"
        if slug:
            # Remove any non-alphanumeric characters
            slug = re.sub(r"[^a-zA-Z0-9-]", "", slug)
            return f"{prefix}-{slug}"
        return f"{prefix}-{uid}"

    async def _get_organization(self):
        return await self._storage.organizations.get_organization(
            include={"slack_channel_id", "slug", "uid", "org_id", "owner_id"},
        )

    async def _get_or_create_slack_channel(self, clt: SlackApiClient, retries: int = 3):
        org = await self._get_organization()
        if org.slack_channel_id:
            return org.slack_channel_id

        # Locking
        try:
            await self._storage.organizations.set_slack_channel_id("")
        except ObjectNotFoundException:
            # Slack channel already set so we can just try to get it again
            for _ in range(retries):
                await asyncio.sleep(self._SLEEP_BETWEEN_RETRIES)
                updated_org = await self._storage.organizations.get_organization(include={"slack_channel_id"})
                if updated_org.slack_channel_id:
                    return updated_org.slack_channel_id

            raise InternalError("Failed to get or create slack channel", extra={"org_id": org.uid, "slug": org.slug})

        try:
            channel_id = await clt.create_channel(self._channel_name(org.slug, org.uid))
        except Exception as e:
            await self._storage.organizations.set_slack_channel_id(None)
            raise InternalError("Failed to create slack channel", extra={"org_id": org.uid, "slug": org.slug}) from e

        await self._storage.organizations.set_slack_channel_id(channel_id, force=True)
        add_background_task(self._on_channel_created(channel_id, org.slug, org.org_id, org.owner_id))
        return channel_id

    async def _update_channel_purpose(
        self,
        clt: SlackApiClient,
        channel_id: str,
        slug: str,
        user: UserDetails | None,
        org: OrganizationDetails | None,
    ):
        if not slug:
            # That can happen for anonymous users for example
            return

        components = ["Customer", f"WorkflowAI: {WORKFLOWAI_APP_URL}/{slug}/agents"]
        if user:
            components.append(f"User: {user.name} ({user.email})")
        if org:
            components.append(f"Organization: {org.name})")

        await clt.set_channel_purpose(channel_id, "\n".join(components))

    async def _on_channel_created(
        self,
        channel_id: str,
        slug: str,
        org_id: str | None,
        owner_id: str | None,
        invite_users: bool = True,
    ):
        with self._slack_client() as clt:
            if invite_users and (invitees := os.environ.get("SLACK_BOT_INVITEES")):
                await clt.invite_users(channel_id, invitees.split(","))

            if not slug or org_id:
                # That can happen for anonymous users for example
                return

            user = await self._user_service.get_user(owner_id) if owner_id else None
            org = await self._user_service.get_organization(org_id) if org_id else None

            await self._update_channel_purpose(clt, channel_id, org.slug if org else slug, user, org)

            if user:
                assessment = await CustomerAssessmentService.run_customer_assessment(user.email)
                await clt.send_message(channel_id, {"text": str(assessment)})

                # Only run AI roadmap generation if the customer has a company website
                if assessment.company_website_url:
                    features_suggestions = await FeatureService().get_features_by_domain(
                        assessment.company_website_url,
                    )
                    features_suggestions_message = SlackMessageFormatter.get_feature_preview_list_slack_message(
                        assessment.company_website_url,
                        features_suggestions,
                    )
                    await clt.send_message(channel_id, {"text": features_suggestions_message})
                else:
                    await clt.send_message(
                        channel_id,
                        {
                            "text": "No suggested AI roadmap for this customer because we could not find a company website",
                        },
                    )

    @contextmanager
    def _slack_client(self):
        bot_token = os.environ.get("SLACK_BOT_TOKEN")
        if not bot_token:
            _logger.warning("SLACK_BOT_TOKEN is not set, skipping message sending")
            return

        yield SlackApiClient(bot_token=bot_token)

    async def _send_message(self, message: str):
        with self._slack_client() as clt:
            channel_id = await self._get_or_create_slack_channel(clt)
            if channel_id == "skipped":
                return

            await clt.send_message(channel_id, {"text": message})

    async def handle_customer_migrated(self, from_user_id: str | None, from_anon_id: str | None):
        # TODO: rename slack channel
        org = await self._get_organization()
        if not org.slack_channel_id:
            _logger.warning("No slack channel id found for organization", extra={"org_uid": org.uid, "slug": org.slug})
            return

        with self._slack_client() as clt:
            await clt.rename_channel(org.slack_channel_id, self._channel_name(org.slug, org.uid))

        add_background_task(
            self._on_channel_created(
                org.slack_channel_id,
                org.slug,
                org.org_id,
                org.owner_id,
                invite_users=False,  # We don't need to invite staff users again, as they should already be in the channel
            ),
        )

    async def send_chat_started(self, user: UserProperties | None, existing_task_name: str | None, user_message: str):
        username = _readable_name(user)
        action_str = "update " + existing_task_name if existing_task_name else "create a new task"
        message = f'{username} started a chat to {action_str}\nmessage: "{user_message}"'

        await self._send_message(message)

    # TODO: avoid using event directly here
    async def send_task_update(self, event: TaskSchemaCreatedEvent):
        username = _readable_name(event.user_properties)
        task_str = _get_task_str_for_slack(event=event, task_id=event.task_id, task_schema_id=event.task_schema_id)

        if event.task_schema_id == 1:  # task creation
            message = f"{username} created a new task: {task_str}"
        else:  # task update
            message = f"{username} updated a task schema: {task_str} (schema #{event.task_schema_id})"

        await self._send_message(message)

    async def notify_features_by_domain_generation_started(self, event: FeaturesByDomainGenerationStarted):
        username = _readable_name(event.user_properties)
        message = f"{username} started to generate features for domain: {event.company_domain}"

        await self._send_message(message)

    async def notify_meta_agent_messages_sent(self, event: MetaAgentChatMessagesSent):
        username = _readable_name(event.user_properties)

        for message in event.messages:
            if message.role == "USER":
                message_str = f"{username} sent a message to the meta-agent:\n\n```{message.content}```"
            else:
                message_str = f"Meta-agent sent a message to {username}:\n\n```{message.content}```"

                if message.tool_call:
                    message_str += f"\n\n```Tool call: {json.dumps(message.tool_call.model_dump(), indent=2)}```"

            await self._send_message(message_str)

    async def send_became_active(self, task_id: str):
        message = f"Task {task_id} became active"
        await self._send_message(message)

    async def build_daily_user_digest(self) -> DailyUserDigest:
        class AgentStat(BaseModel):
            agent_uid: int
            run_count: int
            total_cost_usd: float

        storage = self._storage
        tenant = await self._get_organization()

        existing_agents = await tasks.list_tasks(storage)

        from_date = datetime.now() - timedelta(hours=24)
        items_stats = [
            AgentStat(agent_uid=stat.agent_uid, run_count=stat.run_count, total_cost_usd=stat.total_cost_usd)
            async for stat in storage.task_runs.run_count_by_agent_uid(from_date)
        ]
        active_items_stats = [
            AgentStat(agent_uid=stat.agent_uid, run_count=stat.run_count, total_cost_usd=stat.total_cost_usd)
            async for stat in storage.task_runs.run_count_by_agent_uid(from_date, is_active=True)
        ]

        return DailyUserDigest(
            for_date=datetime.now().date(),
            tenant_slug=tenant.slug,
            org_id=tenant.org_id,
            remaining_credits_usd=tenant.current_credits_usd,
            added_credits_usd=tenant.added_credits_usd,
            agents=[
                DailyUserDigest.Agent(
                    name=agent.name,
                    agent_id=agent.id,
                    agent_schema_id=max(v.schema_id for v in agent.versions),
                    description=agent.description,
                    run_count_last_24h=next((stat.run_count for stat in items_stats if stat.agent_uid == agent.uid), 0),
                    active_run_count_last_24h=next(
                        (stat.run_count for stat in active_items_stats if stat.agent_uid == agent.uid),
                        0,
                    ),
                )
                for agent in existing_agents
            ],
        )

    async def send_daily_user_digest(self) -> DailyUserDigest:
        daily_digest = await self.build_daily_user_digest()
        message = SlackMessageFormatter.get_daily_user_digest_slack_message(daily_digest)
        await self._send_message(message)
        return daily_digest


def _readable_name(user: UserProperties | None) -> str:
    if user:
        return user.user_email or "missing email"
    return "unknown user"
