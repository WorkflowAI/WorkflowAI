from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel


class SlackTextBlock(BaseModel):
    type: Literal["mrkdwn"]
    text: str


class SlackPlainTextBlock(BaseModel):
    type: Literal["plain_text"]
    text: str
    emoji: Optional[bool] = None


class SlackPlainTextInput(BaseModel):
    type: Literal["plain_text_input"]
    action_id: str
    initial_value: Optional[str] = None
    multiline: bool = False
    dispatch_action_config: Optional[dict[str, list[str]]] = None


class SlackImageAccessory(BaseModel):
    type: Literal["image"]
    image_url: str
    alt_text: Optional[str] = None


class SlackHeaderBlock(BaseModel):
    type: Literal["header"]
    text: SlackPlainTextBlock


class SlackButtonElement(BaseModel):
    type: Literal["button"]
    text: SlackPlainTextBlock
    style: Optional[Literal["primary", "danger"]] = None
    value: str
    url: Optional[str] = None


class SlackActionsBlock(BaseModel):
    type: Literal["actions"]
    elements: list[SlackButtonElement]


class SlackSectionBlock(BaseModel):
    type: Literal["section"]
    text: Optional[SlackTextBlock] = None
    block_id: Optional[str] = None
    accessory: Optional[SlackImageAccessory] = None
    fields: Optional[list[SlackTextBlock]] = None


class SlackRichTextElementContent(BaseModel):
    type: str
    text: Optional[str] = None
    user_id: Optional[str] = None
    url: Optional[str] = None


class SlackRichTextSection(BaseModel):
    type: Literal["rich_text_section", "rich_text_preformatted"]
    elements: list[SlackRichTextElementContent]


class SlackRichTextBlock(BaseModel):
    type: Literal["rich_text"]
    block_id: str
    elements: list[SlackRichTextSection]


# ----------------------------
# Blocks used in interactive messages (need to be defined before we declare SlackBlockUnion for correct typing).


class SlackMessageInputBlock(BaseModel):
    type: Literal["input"]
    block_id: str
    label: SlackPlainTextBlock
    optional: bool = False
    dispatch_action: bool = False
    element: SlackPlainTextInput


SlackBlockUnion = Union[
    SlackSectionBlock,
    SlackHeaderBlock,
    SlackActionsBlock,
    SlackRichTextBlock,
    SlackMessageInputBlock,
]


class OutboundSlackMessage(BaseModel):
    text: Optional[str] = None
    blocks: Optional[list[SlackBlockUnion]] = None


class SlackMessage(OutboundSlackMessage):
    type: str
    user: str
    ts: str
    bot_id: Optional[str] = None


class SlackBotProfile(BaseModel):
    id: str
    deleted: bool
    name: str
    updated: int
    app_id: str
    user_id: str
    icons: dict[str, str]
    team_id: str


class SlackEventData(BaseModel):
    type: str
    ts: str
    channel: str
    event_ts: str
    user: Optional[str] = None
    team: Optional[str] = None
    channel_type: Optional[str] = None
    bot_id: Optional[str] = None
    app_id: Optional[str] = None
    text: Optional[str] = None
    client_msg_id: Optional[str] = None
    bot_profile: Optional[SlackBotProfile] = None
    blocks: Optional[list[dict[str, Any]]] = None


class SlackAuthorization(BaseModel):
    team_id: str
    user_id: str
    is_bot: bool
    is_enterprise_install: bool
    enterprise_id: Optional[str] = None


class SlackWebhookEvent(BaseModel):
    token: str
    team_id: str
    api_app_id: str
    event: SlackEventData
    type: str
    event_id: str
    event_time: int
    authorizations: list[SlackAuthorization]
    is_ext_shared_channel: bool
    event_context: str
    context_team_id: Optional[str] = None
    context_enterprise_id: Optional[str] = None

    def is_bot_triggered(self) -> bool:
        return self.event.bot_profile is not None


class SlackUser(BaseModel):
    id: str
    username: str
    name: str
    team_id: str


class SlackContainer(BaseModel):
    type: str
    message_ts: str
    channel_id: str
    is_ephemeral: bool


class SlackTeam(BaseModel):
    id: str
    domain: str


class SlackChannel(BaseModel):
    id: str
    name: str


class SlackAction(BaseModel):
    action_id: str
    block_id: str
    text: dict[str, Union[str, bool]]
    value: str
    style: Optional[str] = None
    type: str
    action_ts: Optional[str] = None


class SlackBlockActionStateValue(BaseModel):
    type: str
    value: str | None = None


class SlackBlockActionState(BaseModel):
    values: dict[str, dict[str, SlackBlockActionStateValue]]


class SlackMessageHeaderBlock(BaseModel):
    type: Literal["header"]
    block_id: str
    text: SlackPlainTextBlock


class SlackMessageButtonElement(BaseModel):
    type: Literal["button"]
    action_id: str
    text: SlackPlainTextBlock
    value: str
    style: Optional[str] = None


class SlackMessageActionsBlock(BaseModel):
    type: Literal["actions"]
    block_id: str
    elements: list[SlackMessageButtonElement]


SlackBlockType = Union[SlackMessageHeaderBlock, SlackMessageInputBlock, SlackMessageActionsBlock]


class SlackBlockActionMessage(BaseModel):
    user: str
    type: str
    ts: str
    bot_id: Optional[str] = None
    app_id: Optional[str] = None
    text: str
    team: str
    blocks: list[SlackBlockType]


class SlackBlockActionWebhookEvent(BaseModel):
    """
    Represents a Slack Block Action webhook event that is sent when a user
    interacts with an interactive component in a Slack message, such as
    buttons, select menus, or date pickers.

    This model captures the structure of the payload sent by Slack when
    a block action is triggered, including information about the user,
    the action taken, the message context, and other relevant metadata.
    """

    type: str
    user: SlackUser
    api_app_id: str
    token: str
    container: SlackContainer
    trigger_id: str
    team: SlackTeam
    enterprise: None = None
    is_enterprise_install: bool
    channel: SlackChannel
    message: SlackBlockActionMessage
    state: SlackBlockActionState
    response_url: str
    actions: list[SlackAction]
