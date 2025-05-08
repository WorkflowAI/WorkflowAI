import logging
from typing import Any

import httpx

from core.storage.slack.slack_types import OutboundSlackMessage

logger = logging.getLogger(__name__)


class SlackErrorSendingError(Exception):
    pass


class SlackWebhookClient:
    def __init__(self, webhook_url: str | None):
        self.webhook_url = webhook_url
        if self.webhook_url is None:
            logger.debug("SLACK_WEBHOOK_URL environment variable is not set. Slack notifications will be skipped.")

    async def send_message(self, message: str | OutboundSlackMessage | dict[str, Any]) -> None:
        if self.webhook_url is None:
            logger.warning(
                "Skipped Slack message sending because 'webhook_url' is not set",
                extra={"slack_message": message},
            )
            return

        data = message if isinstance(message, dict) else {"text": message}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.webhook_url, json=data, timeout=10.0)
                response.raise_for_status()
                if response.status_code != 200:
                    raise SlackErrorSendingError(f"Slack API returned an unexpected response: {response.text}")
            except httpx.TimeoutException:
                raise SlackErrorSendingError("Timeout occurred while sending message to Slack")
            except httpx.HTTPStatusError as e:
                raise SlackErrorSendingError(
                    f"HTTP error occurred while sending message to Slack: {e.response.status_code} {e.response.text}",
                )
