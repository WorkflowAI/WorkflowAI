import asyncio
import json
import logging
import os
import re
from collections.abc import AsyncIterator, Callable
from datetime import date, datetime, time, timedelta, timezone
from typing import NamedTuple

from pydantic import BaseModel

from api.services import tasks
from api.services.customer_assessment_service import CustomerAssessmentService
from api.services.features import CompanyFeaturePreviewList, FeatureService
from core.domain.analytics_events.analytics_events import UserProperties
from core.domain.consts import ENV_NAME, WORKFLOWAI_APP_URL
from core.domain.errors import InternalError
from core.domain.events import (
    Event,
    FeaturesByDomainGenerationStarted,
    MetaAgentChatMessagesSent,
    ProxyAgentCreatedEvent,
    TaskSchemaCreatedEvent,
)
from core.domain.task_info import PublicTaskInfo
from core.domain.tenant_data import PublicOrganizationData
from core.services.users.user_service import OrganizationDetails, UserDetails, UserService
from core.storage import ObjectNotFoundException
from core.storage.backend_storage import BackendStorage
from core.storage.slack.slack_api_client import SlackApiClient
from core.storage.slack.utils import get_slack_hyperlink
from core.utils.background import add_background_task
from core.utils.coroutines import capture_errors

_logger = logging.getLogger(__name__)


class DailyUserDigest(NamedTuple):
    for_date: date
    tenant_slug: str
    org_id: str | None
    remaining_credits_usd: float
    added_credits_usd: float

    class Agent(NamedTuple):
        name: str
        agent_id: str
        agent_schema_id: int
        description: str | None
        run_count_last_24h: int
        active_run_count_last_24h: int

    agents: list[Agent]


class DailyDigestAndEmail(NamedTuple):
    daily_digest: DailyUserDigest

    class Email(NamedTuple):
        subject: str | None = None
        body: str | None = None

    email: Email


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
                f"{WORKFLOWAI_APP_URL}/{daily_digest.tenant_slug}/agents/{agent.agent_id}/{agent.agent_schema_id}",
            )

            parts.append("\n")
            parts.append(f"Runs (last 24h): {agent.run_count_last_24h}")
            if agent.active_run_count_last_24h:
                parts.append(f"({agent.active_run_count_last_24h} active)")

            return "".join(parts)

        return f"""*Daily User Digest for {daily_digest.for_date.strftime("%Y-%m-%d")}*


Remaining credits: ${daily_digest.remaining_credits_usd:.2f}
Added credits (all time): ${daily_digest.added_credits_usd:.2f}
{DELIMITER}{DELIMITER.join([_get_agent_str(agent) for agent in daily_digest.agents])}"""


class CustomerService:
    _SLEEP_BETWEEN_RETRIES = 0.1

    def __init__(self, storage: BackendStorage, user_service: UserService):
        self._storage = storage
        self._user_service = user_service

    @classmethod
    def _channel_name(cls, slug: str, uid: int):
        prefix = "customer" if ENV_NAME == "prod" else f"customer-{ENV_NAME}"
        if slug:
            # Remove any non-alphanumeric characters
            slug = re.sub(r"[^a-zA-Z0-9-]", "", slug)
            return f"{prefix}-{slug}"
        return f"{prefix}-{uid}"

    async def _get_organization(self):
        return await self._storage.organizations.get_organization(
            include={
                "slack_channel_id",
                "slug",
                "uid",
                "org_id",
                "owner_id",
                "current_credits_usd",
                "added_credits_usd",
            },
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
            components.append(f"Organization: {org.name}")

        await clt.set_channel_purpose(channel_id, "\n".join(components))

        if clerk_link := self._clerk_link(org_id=org.id if org else None, owner_id=user.id if user else None):
            await clt.set_channel_topic(channel_id, clerk_link)

    @classmethod
    def _clerk_link(cls, org_id: str | None, owner_id: str | None) -> str | None:
        dashboard = os.environ.get("CLERK_DASHBOARD_PREFIX")
        if not dashboard:
            return None
        if owner_id:
            return f"{dashboard}/users/{owner_id}"
        if org_id:
            return f"{dashboard}/organizations/{org_id}"
        return None

    async def _on_channel_created(
        self,
        channel_id: str,
        slug: str,
        org_id: str | None,
        owner_id: str | None,
    ):
        if clt := self._slack_client():
            # We only invite users when the channel is not for an anonymous user
            if (org_id or owner_id) and (invitees := os.environ.get("SLACK_BOT_INVITEES")):
                with capture_errors(_logger, "Failed to invite users to channel"):
                    await clt.invite_users(channel_id, invitees.split(","))

            if not slug or org_id:
                # That can happen for anonymous users for example
                return

            user = await self._user_service.get_user(owner_id) if owner_id else None
            org = await self._user_service.get_organization(org_id) if org_id else None

            await self._update_channel_purpose(
                clt,
                channel_id,
                org.slug if org else slug,
                user,
                org,
            )

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

    @classmethod
    def _slack_client(cls):
        bot_token = os.environ.get("SLACK_BOT_TOKEN")
        if not bot_token:
            _logger.warning("SLACK_BOT_TOKEN is not set, skipping message sending")
            return None

        return SlackApiClient(bot_token=bot_token)

    async def _send_message(self, message: str):
        if clt := self._slack_client():
            channel_id = await self._get_or_create_slack_channel(clt)
            if channel_id.startswith("skipped"):
                return

            await clt.send_message(channel_id, {"text": message})

    async def handle_customer_migrated(self, from_user_id: str | None, from_anon_id: str | None):
        org = await self._get_organization()
        if not org.slack_channel_id:
            _logger.warning("No slack channel id found for organization", extra={"org_uid": org.uid, "slug": org.slug})
            return

        if clt := self._slack_client():
            await clt.rename_channel(org.slack_channel_id, self._channel_name(org.slug, org.uid))

        add_background_task(
            self._on_channel_created(
                org.slack_channel_id,
                org.slug,
                org.org_id,
                org.owner_id,
            ),
        )

    async def send_chat_started(self, user: UserProperties | None, existing_task_name: str | None, user_message: str):
        username = _readable_name(user)
        action_str = "update " + existing_task_name if existing_task_name else "create a new task"
        message = f'{username} started a chat to {action_str}\nmessage: "{user_message}"'

        await self._send_message(message)

    async def send_proxy_agent_created(self, event: ProxyAgentCreatedEvent):
        username = _readable_name(event.user_properties)
        agent_str = _get_task_str_for_slack(event=event, task_id=event.task_id, task_schema_id=event.task_schema_id)

        if event.task_schema_id == 1:  # task creation
            message = f"{username} created a new agent via OpenAI proxy: {agent_str}"
        else:  # task update
            message = f"{username} updated an agent via OpenAI proxy: {agent_str}"

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

    @classmethod
    async def build_daily_report(
        cls,
        user_service: UserService,
        today: date,
        active_task_fetcher: Callable[[datetime], AsyncIterator[tuple[PublicOrganizationData, list[PublicTaskInfo]]]],
    ):
        yesterday = datetime.combine(today - timedelta(days=1), time(0, 0), tzinfo=timezone.utc)

        count = await user_service.count_registrations(since=yesterday)
        active_tasks = [a async for a in active_task_fetcher(yesterday) if a[0].slug != "workflowai"]

        parts = [
            f"**Daily report for {today}**",
            f"Total registrations: **{count}**",
            f"Active tenants (Org with runs from API or SDK in the last 24h): **{len(active_tasks)}**",
            f"Active agents: (Agents with runs from API or SDK in the last 24h): **{sum(len(tasks) for _, tasks in active_tasks)}**",
            "",
        ]

        for org, ts in active_tasks:
            parts.append("-------")
            parts.append(f"**{org.slug}** (#{cls._channel_name(org.slug, org.uid)})")
            parts.extend(f" - {t.name}: ({WORKFLOWAI_APP_URL}/{org.slug}/agents/{t.task_id})" for t in ts)

        return "\n".join(parts)

    @classmethod
    async def send_daily_report(
        cls,
        user_service: UserService,
        today: date,
        active_task_fetcher: Callable[[datetime], AsyncIterator[tuple[PublicOrganizationData, list[PublicTaskInfo]]]],
    ):
        customers_channel = os.environ.get("SLACK_CUSTOMERS_CHANNEL_ID")
        if not customers_channel:
            _logger.info("SLACK_CUSTOMERS_CHANNEL_ID is not set, skipping daily report")
            return

        if clt := cls._slack_client():
            report = await cls.build_daily_report(user_service, today, active_task_fetcher)
            await clt.send_message(customers_channel, {"text": report})

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
