import logging
import os

from fastapi import APIRouter, Request

from api.dependencies.security import SystemStorageDep
from core.services.customers.customer_service import CustomerService
from core.storage.slack.slack_api_client import SlackApiClient

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/slack", include_in_schema=False)


# Accept both "" and "/" withouth yield a 307 that would provoke the webhook to be called several times
@router.post("/")
@router.post("")
async def slack_webhook(request: Request, storage: SystemStorageDep):
    try:
        payload = await request.json()
        _logger.info("Received Slack webhook", extra={"payload": payload})
        # Handle Slack URL verification
        if "challenge" in payload:
            return {"challenge": payload["challenge"]}

        slack_client = SlackApiClient(bot_token=os.environ["SLACK_BOT_TOKEN"])
        validated_event = await slack_client.handle_webhook(payload)
        if validated_event:
            await CustomerService.process_slack_webhook_message(validated_event, storage)

    except Exception as e:
        _logger.exception("Error processing Slack webhook", extra={"error": e})

    # Always return a 200 response for Slack webhooks
    return {"status": "success"}


# Accept both "" and "/" withouth yield a 307 that would provoke the webhook to be called several times
@router.post("/actions")
@router.post("/actions/")
async def slack_actions_webhook(request: Request):
    try:
        # Slack sends form data with a 'payload' parameter
        form_data = await request.form()
        if "payload" in form_data:
            import json

            # Convert form value to string explicitly
            payload_data = form_data["payload"]
            if isinstance(payload_data, str):
                payload_json = json.loads(payload_data)
                _logger.info("Received Slack action webhook", extra={"payload": payload_json})

                slack_client = SlackApiClient(bot_token=os.environ["SLACK_BOT_TOKEN"])
                validated_action_event = await slack_client.handle_block_action(payload_json)
                if validated_action_event:
                    await CustomerService.process_slack_block_action(validated_action_event)
        else:
            raise ValueError("No payload found in form data")

    except Exception as e:
        _logger.exception("Error processing Slack actions webhook", extra={"error": e})

    # Always return a 200 response for Slack webhooks
    return {"status": "success"}
