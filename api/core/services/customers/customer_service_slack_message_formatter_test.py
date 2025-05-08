from typing import Any
from unittest.mock import MagicMock

import pytest

from core.agents.customer_success_helper_chat import CustomerSuccessHelperChatAgentOutput
from core.services.customers.customer_service_slack_message_formatter import (
    DRAFT_ACCEPTED_VALUE,
    DRAFT_BODY_BLOCK_ID,
    DRAFT_CONVERSATION_ID_BLOCK_ID,
    DRAFT_DISCARDED_VALUE,
    DRAFT_SUBJECT_BLOCK_ID,
    DRAFT_TO_BLOCK_ID,
    SlackMessageFormatter,
)
from core.storage.slack.slack_types import SlackBlockActionWebhookEvent, SlackMessage


class TestSlackMessageFormatter:
    def test_get_email_draft_slack_action_event_accepted(self):
        # Arrange
        mock_slack_event = MagicMock(spec=SlackBlockActionWebhookEvent)

        # Set up action
        mock_action = MagicMock()
        mock_action.value = DRAFT_ACCEPTED_VALUE
        mock_slack_event.actions = [mock_action]

        # Set up message blocks
        mock_block_to = MagicMock()
        mock_block_to.block_id = DRAFT_TO_BLOCK_ID

        mock_block_subject = MagicMock()
        mock_block_subject.block_id = DRAFT_SUBJECT_BLOCK_ID

        mock_block_body = MagicMock()
        mock_block_body.block_id = DRAFT_BODY_BLOCK_ID

        mock_block_conversation_id = MagicMock()
        mock_block_conversation_id.block_id = DRAFT_CONVERSATION_ID_BLOCK_ID

        mock_message = MagicMock()
        mock_message.blocks = [mock_block_to, mock_block_subject, mock_block_body, mock_block_conversation_id]
        mock_slack_event.message = mock_message

        # Set up state values
        mock_state_value_to = MagicMock()
        mock_state_value_to.value = "test@example.com, another@example.com"

        mock_state_value_subject = MagicMock()
        mock_state_value_subject.value = "Test Subject"

        mock_state_value_body = MagicMock()
        mock_state_value_body.value = "This is a test email body."

        mock_state_value_conversation_id = MagicMock()
        mock_state_value_conversation_id.value = "1234567890"

        # Create state structure
        mock_state = MagicMock()
        mock_state.values = {
            DRAFT_TO_BLOCK_ID: {"to_value": mock_state_value_to},
            DRAFT_SUBJECT_BLOCK_ID: {"subject_value": mock_state_value_subject},
            DRAFT_BODY_BLOCK_ID: {"body_value": mock_state_value_body},
            DRAFT_CONVERSATION_ID_BLOCK_ID: {"conversation_id_value": mock_state_value_conversation_id},
        }
        mock_slack_event.state = mock_state

        # Act
        result = SlackMessageFormatter.get_email_draft_slack_action_event(mock_slack_event)

        # Assert
        assert result is not None
        assert isinstance(result, CustomerSuccessHelperChatAgentOutput.EmailDraft)
        assert result.to is not None
        assert len(result.to) == 2
        assert "test@example.com" in result.to
        assert "another@example.com" in result.to
        assert result.subject == "Test Subject"
        assert result.body == "This is a test email body."

    def test_get_email_draft_slack_action_event_discarded(self):
        # Arrange
        mock_slack_event = MagicMock(spec=SlackBlockActionWebhookEvent)
        mock_action = MagicMock()
        mock_action.value = DRAFT_DISCARDED_VALUE
        mock_slack_event.actions = [mock_action]

        # Act
        result = SlackMessageFormatter.get_email_draft_slack_action_event(mock_slack_event)

        # Assert
        assert result is None

    def test_get_email_draft_slack_action_event_missing_state(self):
        # Arrange
        mock_slack_event = MagicMock(spec=SlackBlockActionWebhookEvent)

        # Set up action
        mock_action = MagicMock()
        mock_action.value = DRAFT_ACCEPTED_VALUE
        mock_slack_event.actions = [mock_action]

        # Set up message blocks
        mock_block_to = MagicMock()
        mock_block_to.block_id = DRAFT_TO_BLOCK_ID

        mock_block_subject = MagicMock()
        mock_block_subject.block_id = DRAFT_SUBJECT_BLOCK_ID

        mock_block_body = MagicMock()
        mock_block_body.block_id = DRAFT_BODY_BLOCK_ID

        mock_message = MagicMock()
        mock_message.blocks = [mock_block_to, mock_block_subject, mock_block_body]
        mock_slack_event.message = mock_message

        # Set up empty state (no values)
        mock_state = MagicMock()
        mock_state.values = {}
        mock_slack_event.state = mock_state

        # Act & Assert
        with pytest.raises(ValueError, match=f"Required block '{DRAFT_TO_BLOCK_ID}' not found in Slack state"):
            SlackMessageFormatter.get_email_draft_slack_action_event(mock_slack_event)

    def test_get_email_draft_slack_action_event_missing_blocks(self):
        # Arrange
        mock_slack_event = MagicMock(spec=SlackBlockActionWebhookEvent)

        # Set up action
        mock_action = MagicMock()
        mock_action.value = DRAFT_ACCEPTED_VALUE
        mock_slack_event.actions = [mock_action]

        # Set up message blocks with a missing required block
        mock_block_to = MagicMock()
        mock_block_to.block_id = DRAFT_TO_BLOCK_ID

        # Missing subject block

        mock_block_body = MagicMock()
        mock_block_body.block_id = DRAFT_BODY_BLOCK_ID

        mock_message = MagicMock()
        mock_message.blocks = [mock_block_to, mock_block_body]  # Subject block missing
        mock_slack_event.message = mock_message

        # Set up state with all required blocks to test the message blocks validation
        mock_state = MagicMock()
        mock_state.values = {
            DRAFT_TO_BLOCK_ID: {"to_value": MagicMock()},
            DRAFT_SUBJECT_BLOCK_ID: {"subject_value": MagicMock()},
            DRAFT_BODY_BLOCK_ID: {"body_value": MagicMock()},
        }
        mock_slack_event.state = mock_state

        # Act & Assert
        with pytest.raises(ValueError, match=f"Required block '{DRAFT_SUBJECT_BLOCK_ID}' not found in Slack message"):
            SlackMessageFormatter.get_email_draft_slack_action_event(mock_slack_event)

    def test_get_slack_message_display_str(self) -> None:
        """Test the display function with different message types."""
        # Normal text message
        message_data: dict[str, Any] = {
            "user": "U072G5S75FB",
            "type": "message",
            "ts": "1745441561.194819",
            "client_msg_id": "C88A3222-7A49-4CB3-9664-7366B104AB18",
            "text": "<@U08P9P2Q5J8> current time please",
            "team": "T05T83AFFT3",
            "blocks": [
                {
                    "type": "rich_text",
                    "block_id": "+mXsi",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [
                                {
                                    "type": "user",
                                    "user_id": "U08P9P2Q5J8",
                                },
                                {
                                    "type": "text",
                                    "text": " current time please",
                                },
                            ],
                        },
                    ],
                },
            ],
        }
        message = SlackMessage(**message_data)
        display = SlackMessageFormatter.get_slack_message_display_str(message)
        assert "@U08P9P2Q5J8  current time please" in display
