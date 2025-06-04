import hashlib
import json
from typing import Iterator

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, RootModel

from core.domain.consts import INPUT_KEY_MESSAGES, INPUT_KEY_MESSAGES_DEPRECATED
from core.domain.fields.file import File
from core.domain.message import Message, MessageContent
from core.domain.task_group_properties import TaskGroupProperties


def _hash(data: str) -> str:
    # Using blake2s for speed. We don't need security here
    return hashlib.blake2s(data.encode()).hexdigest()


def _content_sort_key(content: MessageContent) -> int:
    if content.file:
        return 2
    if content.tool_call_request:
        return 3
    if content.tool_call_result:
        return 4
    if content.text:
        return 1
    return 5


_MESSAGE_INCLUDE_FOR_HASH = {
    "role": True,
    "content": {
        "__all__": {
            "text": True,
            "tool_call_request": True,
            "tool_call_result": True,
            "file": {"content_type": True, "data": True, "url": True},
        },
    },
}


class StoredMessage(Message):
    # A hash that depends on the previous messages
    agg_hash: str | None = None
    run_id: str | None = None

    # Any other field will be ignored
    model_config = ConfigDict(extra="ignore")

    def model_hash(self):
        """Compute a hash for this message only"""
        copy = self.model_copy(deep=False)
        # We sort the content before computing the hash
        # Since the OpenAI format and ours are not exactly the same
        # (e-g tools and files are returned in separate fields)
        copy.content.sort(key=_content_sort_key)

        # Be careful of omitting all fields that might be added by us
        return _hash(copy.model_dump_json(exclude_none=True, include=_MESSAGE_INCLUDE_FOR_HASH))


class StoredMessages(BaseModel):
    messages: list[StoredMessage] = Field(
        alias=INPUT_KEY_MESSAGES,
        default_factory=list,
        # TODO: remove this once we have removed the deprecated field
        validation_alias=AliasChoices(INPUT_KEY_MESSAGES, "messages", INPUT_KEY_MESSAGES_DEPRECATED),
    )

    # Any other field will be allowed in stored in extras
    model_config = ConfigDict(extra="allow", serialize_by_alias=True)

    def _extra_hash(self) -> str:
        # Computes the hash from the model extras
        if not self.model_extra:
            return ""
        return _hash(json.dumps(self.model_extra, sort_keys=True))

    def compute_hashes(self, properties: TaskGroupProperties):
        """Compute a hash for each message that depends on the previous messages."""

        computed: list[str] = []
        if properties.model:
            computed.append(properties.model)
        if properties.messages:
            computed.append(_hash(RootModel(properties.messages).model_dump_json()))
        if extra := self._extra_hash():
            computed.append(extra)
        for message in self.messages:
            # Add the current message hash to the computed list
            computed.append(message.model_hash())
            # Compute the aggregated hash
            message.agg_hash = self.aggregate_hashes(computed)
        return computed

    @classmethod
    def aggregate_hashes(cls, hashes: list[str]) -> str:
        """Aggregate the hashes of a list of messages"""
        return _hash(str(hashes))

    def file_iterator(self) -> Iterator[File]:
        for m in self.messages:
            for c in m.content:
                if c.file:
                    yield c.file

    def dump_for_input(self):
        return self.model_dump(
            exclude_unset=True,
            exclude={
                "messages": {
                    "__all__": {
                        # We don't need the agg hash but we want the run id
                        "agg_hash": True,
                        "content": {
                            "__all__": {
                                "file": {
                                    "format": True,
                                },
                            },
                        },
                    },
                },
            },
        )
