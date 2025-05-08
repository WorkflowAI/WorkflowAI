import os
from enum import Enum
from logging import getLogger

from core.domain.events import Event
from core.storage.slack.slack_types import OutboundSlackMessage
from core.storage.slack.webhook_client import SlackWebhookClient

logger = getLogger(__name__)


def _get_user_str(event: Event) -> str:
    return (
        event.user_properties.user_email
        if event.user_properties and event.user_properties.user_email is not None
        else "An unknown user"
    )


def _get_organization_str(event: Event) -> str:
    return (
        f" ({event.organization_properties.organization_slug})"
        if event.organization_properties and event.organization_properties.organization_slug
        else ""
    )


def get_user_and_org_str(event: Event) -> str:
    return f"{_get_user_str(event)}{_get_organization_str(event)}"


def _should_send_slack_notification(user_email: str | None) -> bool:
    ENV_WHITELIST = {"local", "staging"}

    env = os.environ.get("ENV_NAME")
    if env is None:
        logger.warning("ENV_NAME is not set, skip sending slack notification")
        return False
    if env in ENV_WHITELIST:
        # For dev purposes, we want to send notifications to Slack for local and staging
        return True
    if env == "prod":
        PROD_EMAIL_EXCLUDE_LIST = [
            "justinthyme1612@gmail.com",
            "@workflowai.com",
        ]

        is_email_excluded = (
            any(excluded_email in user_email for excluded_email in PROD_EMAIL_EXCLUDE_LIST) if user_email else False
        )
        return not is_email_excluded
    return True


class SlackNotificationDestination(Enum):
    CUSTOMER_JOURNEY = "customer_journey"
    SCHEMA_GENERATION = "schema_generation"
    MODERATION = "moderation"

    @property
    def webhook_url(self) -> str | None:
        match self:
            case SlackNotificationDestination.CUSTOMER_JOURNEY:
                return os.environ.get("SLACK_WEBHOOK_URL_CUSTOMER_JOURNEY")
            case SlackNotificationDestination.SCHEMA_GENERATION:
                return os.environ.get("SLACK_WEBHOOK_URL_SCHEMA_GENERATION")
            case SlackNotificationDestination.MODERATION:
                return os.environ.get("SLACK_WEBHOOK_URL_MODERATION")


# TODO: deprecated ? move to customer service instead
async def send_slack_notification(
    message: str | OutboundSlackMessage,
    user_email: str | None,
    destination: SlackNotificationDestination,
):
    if _should_send_slack_notification(user_email=user_email):
        slack_client = SlackWebhookClient(destination.webhook_url)
        await slack_client.send_message(message)
    else:
        logger.info(
            "Skipping Slack notification",
            extra={
                "slack_message": message,
                "user_email": user_email,
            },
        )
