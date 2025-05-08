from typing import Any

from api.broker import broker
from api.jobs.common import SystemStorageDep
from core.domain import consts
from core.domain.events import FeedbackCreatedEvent
from core.storage.slack.webhook_client import SlackWebhookClient


@broker.task(retry_on_error=True, max_retries=1)
async def send_slack_message(event: FeedbackCreatedEvent, storage: SystemStorageDep):
    # Event does not have a tenant or task_id strings so we need to use the system storage for now
    task_info = await storage.tasks.get_public_task_info(event.task_uid)
    if not task_info.tenant_uid == event.tenant_uid:
        # That would be super bad
        raise ValueError("Task uid does not match tenant uid")

    slack_hook = await storage.organizations.feedback_slack_hook_for_tenant(event.tenant_uid)
    if not slack_hook:
        return

    # f"New feedback for run {event.run_id}:\nOutcome: {event.outcome}\nComment: {event.comment}\nUser ID: {event.user_id}",

    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{event.outcome == 'positive' and '👍' or '👎'} Received feedback for agent *{task_info.name}*",
            },
        },
    ]
    if event.comment:
        comment = event.comment
        if len(comment) > 250:
            comment = comment[:250] + "..."

        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Comment:*\n{comment}"},
            },
        )

    blocks.append(
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View in dashboard"},
                    "value": "view",
                    "url": f"{consts.WORKFLOWAI_APP_URL}/_/agents/{task_info.task_id}/feedback/{event.run_id}",
                },
            ],
        },
    )

    slack_client = SlackWebhookClient(slack_hook)
    await slack_client.send_message({"blocks": blocks})


JOBS = [send_slack_message]
