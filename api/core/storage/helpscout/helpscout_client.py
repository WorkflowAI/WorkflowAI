import datetime
import json
import logging
import os
from typing import Any, Optional

import httpx

from core.domain.errors import InternalError

_logger = logging.getLogger(__name__)


class HelpScoutClient:
    def __init__(self):
        self.client_id = os.getenv("HELPSCOUT_CLIENT_ID")
        self.client_secret = os.getenv("HELPSCOUT_CLIENT_SECRET")
        self.webhook_url = os.getenv("HELPSCOUT_WEBHOOK_URL")
        self.is_webhook_checked: bool = False
        self.access_token: str | None = None
        self.token_expiry: datetime.datetime | None = None
        self.mailbox_id: int | None = None

    async def _get_token(self) -> None:
        """Get a new access token using client credentials flow"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.helpscout.net/v2/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )

            parsed = self._parse_response(response, "get access token")

            self.access_token = parsed["access_token"]
            # Token is valid for 2 days (172800 seconds)
            self.token_expiry = datetime.datetime.now() + datetime.timedelta(seconds=parsed["expires_in"])

            _logger.info(f"Successfully obtained HelpScout access token: {self.access_token}")  # noqa: G004

    async def _ensure_mailbox_id(self) -> None:
        if not self.mailbox_id:
            async with httpx.AsyncClient() as client:
                _logger.info(f"Getting mailbox ID with token: {self.access_token}")  # noqa: G004
                response = await client.get(
                    "https://api.helpscout.net/v2/mailboxes",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                )
                parsed = self._parse_response(response, "get mailbox ID")
                # Because we don't want to mess arround with multiple mailboxes, for now
                if (num_mailboxes := len(parsed["_embedded"]["mailboxes"])) != 1:
                    raise InternalError(
                        "Unexpected number of mailboxes found",
                        extra={"mailboxes": num_mailboxes},
                    )

                self.mailbox_id = parsed["_embedded"]["mailboxes"][0]["id"]

    async def _ensure_token(self) -> None:
        """Ensure we have a valid access token"""
        if not self.access_token or (self.token_expiry and datetime.datetime.now() >= self.token_expiry):
            await self._get_token()

    def _parse_response(
        self,
        response: httpx.Response,
        operation_name: str,
        parse_json: bool = True,
    ) -> dict[str, Any]:
        """Check if HelpScout API response is valid, log and possibly raise error if not"""
        response.raise_for_status()

        try:
            parsed = response.json()
        except json.JSONDecodeError:
            raise InternalError(f"HelpScout client failed to {operation_name}")

        if "error" in parsed:
            error_msg = f"HelpScout client failed to {operation_name}"
            error = parsed.get("error", "Unknown error")
            error_description = parsed.get("error_description", "No description")

            _logger.error(error_msg, extra={"error": error, "description": error_description})
            raise InternalError(error_msg, extra={"error": error, "description": error_description})

        return parsed

    async def _http_client(self) -> httpx.AsyncClient:
        """Create an authenticated client with the current access token"""
        return httpx.AsyncClient(
            base_url="https://api.helpscout.net/v2",
            headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"},
        )

    async def _ensure_webhook_setup(self) -> None:
        if not self.is_webhook_checked:
            existing_webhooks = await self.list_webhooks()
            if not any(webhook.get("url") == self.webhook_url for webhook in existing_webhooks):
                _logger.info("Setting up webhook for %s", self.webhook_url)
                if not self.webhook_url:
                    _logger.warning("No HelpScout webhook URL set, skipping HelpScout webhook setup")
                else:
                    await self.setup_webhook(self.webhook_url)
                    _logger.info("HelpScout webhook setup complete")
            self.is_webhook_checked = True

    async def _ensure_client_ready(self) -> None:
        await self._ensure_webhook_setup()
        await self._ensure_token()
        await self._ensure_mailbox_id()

    async def get(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        operation_name: str = "get resource",
    ) -> dict[str, Any]:
        """Make a GET request to HelpScout API and check response"""
        try:
            await self._ensure_client_ready()
            async with await self._http_client() as client:
                response = await client.get(endpoint, params=params)
                return self._parse_response(response, operation_name)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                # Token expired, clear it and retry once
                self.access_token = None
                async with await self._http_client() as client:
                    response = await client.get(endpoint, params=params)
                    return self._parse_response(response, operation_name)
            raise

    async def post(
        self,
        endpoint: str,
        json_data: Optional[dict[str, Any]] = None,
        operation_name: str = "post resource",
    ):
        await self._ensure_client_ready()
        async with await self._http_client() as client:
            response = await client.post(endpoint, json=json_data)
            response.raise_for_status()

    async def delete(
        self,
        endpoint: str,
        operation_name: str = "delete resource",
    ):
        await self._ensure_client_ready()
        async with await self._http_client() as client:
            response = await client.delete(endpoint)
            response.raise_for_status()

    async def create_conversation(
        self,
        customer_email: str,
        email_subject: str,
        email_body: str,
        tags: Optional[list[str]] = None,
    ) -> None:
        """Create a new conversation with a user"""

        # Needed to ensure we have a valid mailbox ID
        await self._ensure_client_ready()

        customer_data = {"email": customer_email}
        data: dict[str, Any] = {
            "subject": email_subject,
            "customer": customer_data,
            "mailboxId": self.mailbox_id,
            "type": "email",
            "status": "active",
            "threads": [
                {
                    "type": "reply",
                    "customer": customer_data,
                    "text": email_body,
                },
            ],
            "tags": ["from_slack"],
        }

        await self.post(
            "/conversations",
            json_data=data,
            operation_name="create conversation",
        )

    async def send_reply(
        self,
        conversation_id: int,
        text: str,
        customer_email: str,
    ) -> None:
        # Needed to ensure we have a valid mailbox ID
        await self._ensure_client_ready()

        customer_data = {"email": customer_email}
        data: dict[str, Any] = {
            "text": text,
            "customer": customer_data,
        }

        await self.post(
            f"/conversations/{conversation_id}/reply",
            json_data=data,
            operation_name="create reply",
        )

    async def setup_webhook(self, webhook_url: str) -> None:
        data: dict[str, Any] = {
            "url": webhook_url,
            "events": ["convo.created", "convo.customer.reply.created", "convo.agent.reply.created"],
            "secret": "mZ9XbGHodX",
            "payloadVersion": "V2",
            "label": "WorkflowAI HelpScout Webhook",
        }
        async with await self._http_client() as client:
            response = await client.post(
                "/webhooks",
                headers={"Authorization": f"Bearer {self.access_token}"},
                json=data,
            )
            response.raise_for_status()

    async def list_webhooks(self) -> list[dict[str, Any]]:
        """List all webhooks"""
        await self._ensure_token()
        async with await self._http_client() as client:
            response = await client.get("/webhooks", headers={"Authorization": f"Bearer {self.access_token}"})
            response.raise_for_status()
            return self._parse_response(response, "list webhooks")["_embedded"]["webhooks"]

    async def delete_webhook(self, webhook_id: int) -> None:
        """Delete a webhook"""
        await self.delete(
            f"/webhooks/{webhook_id}",
            operation_name="delete webhook",
        )
