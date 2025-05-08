from typing import Any, Optional, cast

from jsonschema import ValidationError
from pydantic import BaseModel, TypeAdapter

from api.services.features import CompanyFeaturePreviewList
from core.agents.customer_success_helper_chat import CustomerSuccessHelperChatAgentOutput
from core.domain.consts import WORKFLOWAI_APP_URL
from core.domain.helpscout_email import HelpScoutEmail
from core.services.customers.customer_service_models import ActiveRunsReport, DailyUserDigest
from core.storage.slack.slack_types import (
    SlackActionsBlock,
    SlackBlockActionWebhookEvent,
    SlackBlockUnion,
    SlackHeaderBlock,
    SlackMessage,
    SlackRichTextBlock,
    SlackSectionBlock,
)

DRAFT_HEADER_TEXT = "📧 Email Draft Generated"
DRAFT_ACCEPTED_VALUE = "accept_email_draft"
DRAFT_DISCARDED_VALUE = "discard_email_draft"

DRAFT_TO_BLOCK_ID = "to_input"
DRAFT_SUBJECT_BLOCK_ID = "subject_input"
DRAFT_BODY_BLOCK_ID = "body_input"
DRAFT_CONVERSATION_ID_BLOCK_ID = "conversation_id_input"


def get_markdown_table(header: list[str], rows: list[list[str]]) -> str:
    # Determine the maximum width of each column to align cells.
    col_widths = [max(len(row[col_idx]) for row in ([header] + rows)) for col_idx in range(len(header))]

    def _fmt_row(cells: list[str]) -> str:  # noqa: WPS430 – nested helper for clarity
        """Return a single formatted table row."""

        return " | ".join(cell.ljust(col_widths[idx]) for idx, cell in enumerate(cells))

    # Assemble the table with a separator after the header.
    lines: list[str] = [
        _fmt_row(header),
        "-+-".join("-" * width for width in col_widths),
        *(_fmt_row(row) for row in rows),
    ]

    # Wrap the table in a code-block so that Slack and other Markdown renderers keep the whitespace
    return "```\n" + "\n".join(lines) + "\n```"


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

    @classmethod
    def get_slack_action_message_for_email_draft(
        cls,
        email_draft: CustomerSuccessHelperChatAgentOutput.EmailDraft,
    ) -> dict[str, Any]:
        """Use Slack Block Kit to return an action message where the user can directly accept or discard a draft."""

        # Format recipients
        recipients_text = ""
        if email_draft.to and len(email_draft.to) > 0:
            recipients_text = ", ".join(email_draft.to)

        return {
            "text": f"Email Draft: {email_draft.subject}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": DRAFT_HEADER_TEXT,
                        "emoji": True,
                    },
                },
                {
                    "type": "input",
                    "block_id": DRAFT_TO_BLOCK_ID,
                    "label": {
                        "type": "plain_text",
                        "text": "To",
                        "emoji": True,
                    },
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "to_value",
                        "initial_value": recipients_text,
                    },
                },
                {
                    "type": "input",
                    "block_id": DRAFT_CONVERSATION_ID_BLOCK_ID,
                    "label": {
                        "type": "plain_text",
                        "text": "Conversation ID",
                        "emoji": True,
                    },
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "conversation_id_value",
                        "initial_value": str(email_draft.conversation_id) if email_draft.conversation_id else "",
                    },
                },
                {
                    "type": "input",
                    "block_id": DRAFT_SUBJECT_BLOCK_ID,
                    "label": {
                        "type": "plain_text",
                        "text": "Subject",
                        "emoji": True,
                    },
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "subject_value",
                        "initial_value": email_draft.subject or "subject from conversation",
                    },
                },
                {
                    "type": "input",
                    "block_id": DRAFT_BODY_BLOCK_ID,
                    "label": {
                        "type": "plain_text",
                        "text": "Body",
                        "emoji": True,
                    },
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "body_value",
                        "multiline": True,
                        "initial_value": email_draft.body,
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "✅ Accept Draft",
                                "emoji": True,
                            },
                            "style": "primary",
                            "value": DRAFT_ACCEPTED_VALUE,
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "❌ Discard Draft",
                                "emoji": True,
                            },
                            "style": "danger",
                            "value": DRAFT_DISCARDED_VALUE,
                        },
                    ],
                },
            ],
        }

    @classmethod
    def get_email_draft_slack_action_event(
        cls,
        slack_action_event: SlackBlockActionWebhookEvent,
    ) -> CustomerSuccessHelperChatAgentOutput.EmailDraft | None:
        """The goal of this function is to convert back the Slack action event to an email draft. It needs to double check that all the fields are present based on IDs and all before returning a draft or raise an error if the action seems corrupted."""

        if not slack_action_event.actions or len(slack_action_event.actions) == 0:
            # No actions found
            return None

        action_value = slack_action_event.actions[0].value
        if action_value != DRAFT_ACCEPTED_VALUE:
            # If it's not accepted (either discarded or invalid), return None
            return None

        # Verify all the required block IDs exist in the message
        block_ids = [block.block_id for block in slack_action_event.message.blocks if hasattr(block, "block_id")]
        state_block_ids = [block_id for block_id in slack_action_event.state.values.keys()]
        required_block_ids = [
            DRAFT_TO_BLOCK_ID,
            DRAFT_SUBJECT_BLOCK_ID,
            DRAFT_BODY_BLOCK_ID,
            DRAFT_CONVERSATION_ID_BLOCK_ID,
        ]

        for required_id in required_block_ids:
            if required_id not in block_ids:
                raise ValueError(f"Required block '{required_id}' not found in Slack message")
            if required_id not in state_block_ids:
                raise ValueError(f"Required block '{required_id}' not found in Slack state")

        try:
            # WARNING: always use the state values, because they contain the UPDATED values, in case the user has edited the message
            to_value = slack_action_event.state.values[DRAFT_TO_BLOCK_ID]["to_value"].value
            subject_value = slack_action_event.state.values[DRAFT_SUBJECT_BLOCK_ID]["subject_value"].value
            body_value = slack_action_event.state.values[DRAFT_BODY_BLOCK_ID]["body_value"].value
            conversation_id_value = slack_action_event.state.values[DRAFT_CONVERSATION_ID_BLOCK_ID][
                "conversation_id_value"
            ].value

            if not to_value:
                raise ValueError("No 'To' value found in Slack action event")
            if not subject_value:
                raise ValueError("No 'Subject' value found in Slack action event")
            if not body_value:
                raise ValueError("No 'Body' value found in Slack action event")

            # Split the "to" field by commas and strip whitespace
            to_recipients = [recipient.strip() for recipient in to_value.split(",") if recipient.strip()]

            # Create and return an EmailDraft object
            return CustomerSuccessHelperChatAgentOutput.EmailDraft(
                to=to_recipients,
                subject=subject_value,
                body=body_value,
                conversation_id=int(conversation_id_value) if conversation_id_value else None,
            )
        except (KeyError, AttributeError):
            # If any of the expected fields are missing
            raise ValueError("Missing required fields in Slack action event")

    @classmethod
    def get_email_activity_slack_message(cls, email: HelpScoutEmail) -> dict[str, Any]:
        """Use Slack Block Kit to return a formatted message displaying email activity details with the email ID for reference."""

        # Initialize blocks list with explicit typing
        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📧 Email from {email.from_email}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"subject: {email.subject}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"conversation id: {email.conversation_id}",
                    },
                ],
            },
        ]

        if email.cc_emails:
            blocks.append(
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"cc:{', '.join(email.cc_emails)}",
                        },
                    ],
                },
            )

        if email.bcc_emails:
            blocks.append(
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"bcc:{', '.join(email.bcc_emails)}",
                        },
                    ],
                },
            )

        blocks.extend(
            [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": email.body[:1000] + ("..." if len(email.body) > 1000 else ""),
                    },
                },
            ],
        )

        return {
            "text": f"Email Activity: {email.subject}",
            "blocks": blocks,
        }

    @classmethod
    def get_slack_message_display_str(cls, message: SlackMessage) -> str:
        display_parts: list[str] = []

        if message.blocks:
            blocks_summary = cls._get_blocks_summary(message.blocks)
            if blocks_summary:
                display_parts.append("\n".join(blocks_summary))
        elif message.text:
            display_parts.append(message.text)

        return "\n".join(display_parts)

    @classmethod
    def _summarize_model_block(cls, block: SlackBlockUnion) -> list[str]:  # noqa: C901
        """Generate a human-readable summary string for a Slack block."""

        result: list[str] = []

        if isinstance(block, SlackHeaderBlock):
            result.append(cls._replace_emoji(block.text.text))

        elif isinstance(block, SlackActionsBlock):
            actions = [cls._replace_emoji(elem.text.text) for elem in block.elements]
            if actions:
                result.append("".join(actions))

        elif isinstance(block, SlackSectionBlock):
            if block.text is not None:
                result.append(cls._replace_emoji(block.text.text))

            for field in block.fields or []:
                result.append(cls._replace_emoji(field.text))  # noqa: PERF401

        elif isinstance(block, SlackRichTextBlock):
            rich_parts: list[str] = []
            for section in block.elements:
                for item in section.elements:
                    if item.type == "text" and item.text:
                        rich_parts.append(item.text)
                    elif item.type == "user" and item.user_id:
                        rich_parts.append(f"@{item.user_id}")
                    elif item.type == "link" and item.text:
                        rich_parts.append(item.text)
            if rich_parts:
                result.append(" ".join(rich_parts))

        else:  # SlackMessageInputBlock
            result.append(f"{block.label.text}: {block.element.initial_value}")

        return result

    @classmethod
    def _replace_emoji(cls, text: str) -> str:
        """Replace emoji codes with corresponding Unicode characters."""
        return text.replace(":white_check_mark:", "✓").replace(":x:", "✗").replace(":e-mail:", "📧")

    @classmethod
    def _get_blocks_summary(cls, blocks: list[Any]) -> list[str]:
        """Extract readable summaries from different block types, prioritizing Pydantic models."""
        summary: list[str] = []

        adapter: TypeAdapter[SlackBlockUnion] = TypeAdapter(SlackBlockUnion)

        for block_data in blocks:
            parsed_block: Optional[SlackBlockUnion] = None

            # If it's already a Pydantic model that belongs to the union, keep it as-is.
            if isinstance(block_data, BaseModel):
                parsed_block = cast(SlackBlockUnion, block_data)
            else:
                # Attempt to parse raw python data into one of the union models.
                try:
                    parsed_block = adapter.validate_python(block_data)
                except ValidationError:
                    # Skip blocks we cannot parse – we do not attempt to inspect dictionaries.
                    parsed_block = None

            if parsed_block is not None:
                summary.extend(cls._summarize_model_block(parsed_block))

        return summary

    @classmethod
    def get_active_runs_report_slack_message(cls, active_runs_report: ActiveRunsReport) -> str:
        """Return a human-readable table of the active runs report.

        The output looks like this::

            Agent | 2024-05-06→2024-05-13 | 2024-04-29→2024-05-06
            ----- + --------------------- + ---------------------
            Bot X | 12 ($3.4)            | 7 ($1.9)
            Bot Y | 0 (0)                | 2 ($0.6)

        The first column lists the agent names.  Each subsequent column
        corresponds to one week (``start_of_week`` → ``end_of_week``).  The
        cell value is the *str()* representation of :class:`AgentStat`, which
        already formats the run count and associated cost.
        """

        if not active_runs_report.weeks:
            return "<empty ActiveRunsReport>"

        # Build header labels for each week.
        header: list[str] = [
            f"Active Agents Runs Summary (last {len(active_runs_report.weeks)} weeks)",
            *[
                f"{w.start_of_week.strftime('%b %-d')} → {w.end_of_week.strftime('%b %-d, %Y')}"
                for w in active_runs_report.weeks
            ],
        ]

        # Convert the stats dictionary into a list of rows for easy processing.
        rows: list[list[str]] = [
            [agent_name, *[str(stat) for stat in agent_stats]]
            for agent_name, agent_stats in active_runs_report.stats.items()
        ]

        return get_markdown_table(header, rows)
