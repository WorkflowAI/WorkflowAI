import asyncio
import json
import logging
import os
import re
from collections.abc import AsyncIterator, Callable
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum

from pydantic import BaseModel

from api.services import tasks
from api.services.customer_assessment_service import CustomerAssessmentService
from api.services.features import FeatureService
from api.services.storage import storage_for_tenant
from core.agents.customer_success_helper_chat import (
    CustomerSuccessHelperChatAgentInput,
    CustomerSuccessHelperChatAgentOutput,
    customer_success_helper_chat,
)
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
from core.domain.fields.chat_message import ChatMessageWithTimestamp
from core.domain.helpscout_email import HelpScoutEmail
from core.domain.task_info import PublicTaskInfo
from core.domain.tenant_data import PublicOrganizationData
from core.services.customers.customer_service_models import ActiveRunsReport, AgentStat, DailyUserDigest
from core.services.customers.customer_service_slack_message_formatter import SlackMessageFormatter
from core.services.users.clerk_user_service import ClerkUserService
from core.services.users.shared_user_service import shared_user_service
from core.services.users.user_service import OrganizationDetails, UserDetails, UserService
from core.storage import ObjectNotFoundException
from core.storage.backend_storage import BackendStorage, SystemBackendStorage
from core.storage.helpscout.helpscout_client import HelpScoutClient
from core.storage.slack.slack_api_client import SlackApiClient
from core.storage.slack.slack_types import (
    OutboundSlackMessage,
    SlackBlockActionWebhookEvent,
    SlackWebhookEvent,
)
from core.storage.slack.utils import get_slack_hyperlink
from core.utils import no_op
from core.utils.background import add_background_task
from core.utils.coroutines import capture_errors
from core.utils.redis_cache import redis_cached

_logger = logging.getLogger(__name__)


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


class SlackCommand(str, Enum):
    ACTIVE_RUNS_REPORT = "active_runs_report"

    @classmethod
    def from_text(cls, text: str) -> "SlackCommand | None":
        """
        Match text to a SlackCommand value using defined aliases.
        Returns the matching SlackCommand or None if no match is found.
        """
        if not text:
            return None

        normalized_text = text.lower().strip()

        # Direct match - exact match to the enum value
        try:
            return cls(normalized_text)
        except ValueError:
            pass

        # Check against aliases
        aliases = {
            cls.ACTIVE_RUNS_REPORT: [
                "active",
                "active runs",
                "active_runs",
            ],
        }

        for cmd, cmd_aliases in aliases.items():
            if normalized_text in cmd_aliases:
                return cmd

        return None


class CustomerService:
    """A service that handles customer success"""

    # TODO: this should not be in this repo
    _SLEEP_BETWEEN_RETRIES = 0.1

    def __init__(self, storage: BackendStorage, user_service: UserService):
        self._storage = storage
        self._user_service = user_service
        self._is_disabled = os.environ.get("CUSTOMER_SERVICE_DISABLED") == "true"

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
        if self._is_disabled:
            return

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
        if self._is_disabled:
            return
        username = _readable_name(user)
        action_str = "update " + existing_task_name if existing_task_name else "create a new task"
        message = f'{username} started a chat to {action_str}\nmessage: "{user_message}"'

        await self._send_message(message)

    async def send_proxy_agent_created(self, event: ProxyAgentCreatedEvent):
        if self._is_disabled:
            return
        username = _readable_name(event.user_properties)
        agent_str = _get_task_str_for_slack(event=event, task_id=event.task_id, task_schema_id=event.task_schema_id)

        if event.task_schema_id == 1:  # task creation
            message = f"{username} created a new agent via OpenAI proxy: {agent_str}"
        else:  # task update
            message = f"{username} updated an agent via OpenAI proxy: {agent_str}"

        await self._send_message(message)

    # TODO: avoid using event directly here
    async def send_task_update(self, event: TaskSchemaCreatedEvent):
        if self._is_disabled:
            return
        username = _readable_name(event.user_properties)
        task_str = _get_task_str_for_slack(event=event, task_id=event.task_id, task_schema_id=event.task_schema_id)

        if event.task_schema_id == 1:  # task creation
            message = f"{username} created a new task: {task_str}"
        else:  # task update
            message = f"{username} updated a task schema: {task_str} (schema #{event.task_schema_id})"

        await self._send_message(message)

    async def notify_features_by_domain_generation_started(self, event: FeaturesByDomainGenerationStarted):
        if self._is_disabled:
            return
        username = _readable_name(event.user_properties)
        message = f"{username} started to generate features for domain: {event.company_domain}"

        await self._send_message(message)

    async def notify_meta_agent_messages_sent(self, event: MetaAgentChatMessagesSent):
        if self._is_disabled:
            return
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

    @classmethod
    async def build_active_runs_report(
        cls,
        tenant_storage: BackendStorage,
        num_weeks: int = 4,
    ) -> ActiveRunsReport:
        """Return a report of active runs for the last *num_weeks*.

        The previous implementation used several intermediate data structures and
        nested loops making it hard to follow. The new version:
        1. Creates a mapping of *agent_uid -> agent_name* once.
        2. Iterates over the requested weeks, fetching the run statistics once
           per week.
        3. Populates *stats_by_agent_name* directly, avoiding the need for an
           additional conversion step.
        """

        today = datetime.now(timezone.utc).date()

        # Fetch existing agents once and keep useful look-ups ready.
        existing_agents = await tasks.list_tasks(tenant_storage)
        agents_by_uid = {agent.uid: agent.name for agent in existing_agents}
        stats_by_agent_name: dict[str, list[AgentStat]] = {agent_name: [] for agent_name in agents_by_uid.values()}

        weeks: list[ActiveRunsReport.Week] = []

        for week_idx in reversed(range(num_weeks)):  # Reversed to oldest weeks first
            week_end = today - timedelta(days=week_idx * 7)
            week_start = week_end - timedelta(days=7)
            weeks.append(
                ActiveRunsReport.Week(start_of_week=week_start, end_of_week=week_end),
            )

            week_from_date = datetime.combine(week_start, time.min, tzinfo=timezone.utc)
            week_to_date = datetime.combine(week_end, time.max, tzinfo=timezone.utc)

            # Build a quick lookup for the current week: agent_uid -> stat
            week_stats = {
                stat.agent_uid: stat
                async for stat in tenant_storage.task_runs.run_count_by_agent_uid(
                    from_date=week_from_date,
                    to_date=week_to_date,
                    is_active=True,
                )
            }

            # Fill stats for each agent ensuring we push a value for every week
            for agent_uid, agent_name in agents_by_uid.items():
                stat = week_stats.get(agent_uid)
                stats_by_agent_name[agent_name].append(
                    AgentStat(
                        run_count=stat.run_count if stat else 0,
                        total_cost_usd=stat.total_cost_usd if stat else 0,
                    ),
                )

        # Sort agents by the total run count across all weeks (descending)
        stats_by_agent_name = {
            name: stats
            for name, stats in sorted(
                stats_by_agent_name.items(),
                key=lambda item: sum(s.run_count for s in item[1]),
                reverse=True,
            )
        }

        return ActiveRunsReport(weeks=weeks, stats=stats_by_agent_name)

    @classmethod
    def _should_process_webhook_event(cls, webhook_event: SlackWebhookEvent) -> tuple[bool, SlackCommand | None]:
        bot_id: str | None = None

        if webhook_event.event.text and (command := SlackCommand.from_text(webhook_event.event.text)):
            return False, command

        # Filter out message that do not contain "@WorkflowAI Bot"
        if len(webhook_event.authorizations) > 0:
            # TODO: use an env var to store the bot id
            bot_id = webhook_event.authorizations[0].user_id

            if webhook_event.event and webhook_event.event.text and bot_id not in webhook_event.event.text:
                _logger.info(
                    "The message is not addressed to the bot, skipping",
                    extra={"event": webhook_event.event.text},
                )
                return False, None

        # Filter messages send by the bot itself
        if webhook_event.is_bot_triggered():
            _logger.info("Skipping bot triggered event", extra={"event": webhook_event})
            return False, None

        return True, None

    @staticmethod
    @redis_cached(expiration_seconds=60 * 60)  # TTL=1 hour
    async def get_slack_channel_description(channel_id: str) -> str:
        slack = CustomerService._slack_client()
        if not slack:
            return ""

        channel_info = await slack.get_channel_info(channel_id)
        return channel_info.short_description

    @classmethod
    async def _generate_roadmap_for_company(
        cls,
        company_domain: str,
        additional_instructions: str | None,
        channel_id: str,
    ) -> None:
        streamed_features_indexes: set[int] = set()

        slack = cls._slack_client()
        if not slack:
            return

        async for chunk in FeatureService.stream_features_by_domain(
            company_domain=company_domain,
            additional_instructions=additional_instructions,
        ):
            if chunk.features and len(chunk.features or []) <= 1:
                continue

            # The logic below allow to only stream a feature when it's ready and only once.
            second_to_last_feature_index = len(chunk.features or []) - 2
            if chunk.features and second_to_last_feature_index not in streamed_features_indexes:
                await slack.send_message(
                    channel_id,
                    {
                        "text": f"""• *{chunk.features[second_to_last_feature_index].name}*
{chunk.features[second_to_last_feature_index].description or ""}""",
                    },
                )
                streamed_features_indexes.add(second_to_last_feature_index)

        await slack.send_message(
            channel_id,
            {
                "text": "AI roadmap generation completed",
            },
        )

    @classmethod
    async def _get_storage_for_slack_channel(
        cls,
        channel_id: str,
        system_storage: SystemBackendStorage,
    ) -> BackendStorage:
        tenant = await system_storage.organizations.get_organization_by_slack_channel_id(channel_id)
        if not tenant:
            raise InternalError("No tenant found for slack channel", extra={"channel_id": channel_id})

        return storage_for_tenant(tenant.tenant, tenant.uid, no_op.event_router)

    @classmethod
    async def _handle_command(
        cls,
        command: SlackCommand,
        channel_id: str,
        system_storage: SystemBackendStorage,
    ):
        slack = cls._slack_client()
        if not slack:
            return

        match command:
            case SlackCommand.ACTIVE_RUNS_REPORT:
                tenant_storage = await cls._get_storage_for_slack_channel(channel_id, system_storage)
                report = await cls.build_active_runs_report(tenant_storage)
                await slack.send_message(
                    channel_id,
                    {"text": SlackMessageFormatter.get_active_runs_report_slack_message(report)},
                )

    @classmethod
    async def process_slack_webhook_message(
        cls,
        webhook_event: SlackWebhookEvent,
        system_storage: SystemBackendStorage,
    ) -> None:
        should_process, command = cls._should_process_webhook_event(webhook_event=webhook_event)
        if command:
            await cls._handle_command(command, webhook_event.event.channel, system_storage)
            return

        if not should_process:
            return

        channel_id = webhook_event.event.channel

        slack = cls._slack_client()
        if not slack:
            return

        messages = await slack.fetch_channel_messages(channel_id)
        short_channel_description = await cls.get_slack_channel_description(channel_id)

        csm_agent_input = CustomerSuccessHelperChatAgentInput(
            channel_description=short_channel_description,
            messages=[
                ChatMessageWithTimestamp(
                    role="USER",
                    content=SlackMessageFormatter.get_slack_message_display_str(message),
                    timestamp=datetime.fromtimestamp(float(message.ts)),
                )
                for message in messages
            ],
            current_datetime=datetime.now(),
        )

        csm_agent_run = await customer_success_helper_chat(csm_agent_input)

        if (
            not csm_agent_run.response
            and not csm_agent_run.email_draft
            and not csm_agent_run.roadmap_generation_command
        ):
            _logger.error("No response from the CSM agent", extra={"channel_id": channel_id})
            await slack.send_message(
                channel_id,
                OutboundSlackMessage(text="No response from the CSM agent, contact the engineering team"),
            )
            return

        if csm_agent_run.response:
            await slack.send_message(
                channel_id,
                OutboundSlackMessage(text=csm_agent_run.response),
            )

        if (
            csm_agent_run.email_draft
            and csm_agent_run.email_draft.to
            and csm_agent_run.email_draft.subject
            and csm_agent_run.email_draft.body
        ):
            await slack.send_message(
                channel_id,
                SlackMessageFormatter.get_slack_action_message_for_email_draft(csm_agent_run.email_draft),
            )

        if csm_agent_run.roadmap_generation_command and csm_agent_run.roadmap_generation_command.company_domain:
            await slack.send_message(
                channel_id,
                OutboundSlackMessage(text="AI roadmap generation trigger received, processing..."),
            )
            add_background_task(
                cls._generate_roadmap_for_company(
                    csm_agent_run.roadmap_generation_command.company_domain,
                    csm_agent_run.roadmap_generation_command.additional_instructions,
                    channel_id,
                ),
            )

    @classmethod
    async def _handle_send_email_draft(
        cls,
        email_draft: CustomerSuccessHelperChatAgentOutput.EmailDraft,
        channel_id: str,
        message_ts: str,
    ):
        slack_client = cls._slack_client()
        if not slack_client:
            return

        try:
            if not email_draft.to:
                raise InternalError("No to in the email draft", extra={"email_draft": email_draft})
            if not email_draft.subject:
                raise InternalError("No subject in the email draft", extra={"email_draft": email_draft})
            if not email_draft.body:
                raise InternalError("No body in the email draft", extra={"email_draft": email_draft})

            if email_draft.conversation_id:
                # TODO: support sending message to multiple customers
                await HelpScoutClient().send_reply(
                    conversation_id=email_draft.conversation_id,
                    text=email_draft.body,
                    customer_email=email_draft.to[0],
                )
            else:
                # TODO: support sending message to multiple customers
                await HelpScoutClient().create_conversation(
                    customer_email=email_draft.to[0],
                    email_subject=email_draft.subject,
                    email_body=email_draft.body,
                )

            # No need to send confirmation message since the webhook will be triggered and add a message to the channel

            await slack_client.delete_message(channel_id, message_ts)
        except Exception as e:
            await slack_client.send_message(
                channel_id,
                OutboundSlackMessage(text="Error sending email, contact the engineering team"),
            )
            _logger.exception("Error sending email", exc_info=e)

    @classmethod
    async def process_slack_block_action(cls, validated_action_event: SlackBlockActionWebhookEvent):
        email_draft = SlackMessageFormatter.get_email_draft_slack_action_event(validated_action_event)
        if email_draft:
            add_background_task(
                cls._handle_send_email_draft(
                    email_draft,
                    validated_action_event.container.channel_id,
                    validated_action_event.message.ts,
                ),
            )
        else:
            slack_client = SlackApiClient(bot_token=os.environ["SLACK_BOT_TOKEN"])
            # Action is discarded, delete the message
            await slack_client.delete_message(
                validated_action_event.container.channel_id,
                validated_action_event.message.ts,
            )

    @staticmethod
    async def _find_slack_channel_ids_for_email(
        email_address: str,
        storage: SystemBackendStorage,
    ) -> list[str]:
        if not isinstance(shared_user_service, ClerkUserService):
            raise InternalError("Clerk is needed to process incoming emails")

        # First, try to find the customer organization
        user_id = await shared_user_service.get_user_id_by_email(email_address)
        org_ids = await shared_user_service.get_user_organization_ids(user_id)

        slack_channel_ids: list[str] = []

        # We could fetch the organization concurrently, but this part of the code is not performance critical
        try:
            user_own_org = await storage.organizations.find_tenant_for_owner_id(user_id)
            if user_own_org and user_own_org.slack_channel_id:
                slack_channel_ids.append(user_own_org.slack_channel_id)
        except ObjectNotFoundException:
            # user has no "own" organization
            pass

        for org_id in org_ids:
            user_org = await storage.organizations.find_tenant_for_org_id(org_id)
            if user_org and user_org.slack_channel_id:
                slack_channel_ids.append(user_org.slack_channel_id)

        return slack_channel_ids

    @classmethod
    async def _send_email_to_slack_channel(cls, email: HelpScoutEmail, channel_id: str):
        slack_api_client = SlackApiClient(bot_token=os.environ["SLACK_BOT_TOKEN"])
        await slack_api_client.send_message(channel_id, SlackMessageFormatter.get_email_activity_slack_message(email))

    @classmethod
    async def handle_helpscout_email_sent(cls, email: HelpScoutEmail, storage: SystemBackendStorage):
        slack_channel_ids = await cls._find_slack_channel_ids_for_email(email.customer_email, storage)

        # We post the email to each Slack channel the user is part of, because a user could have his own Slack channel, and one for his organization
        for channel_id in slack_channel_ids:
            await cls._send_email_to_slack_channel(email, channel_id)


def _readable_name(user: UserProperties | None) -> str:
    if user:
        return user.user_email or "missing email"
    return "unknown user"
