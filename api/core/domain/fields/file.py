import logging
import mimetypes
from base64 import b64decode
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from core.domain.errors import InternalError
from core.utils.file_utils.file_utils import guess_content_type

_logger = logging.getLogger(__file__)


class FileKind(StrEnum):
    DOCUMENT = "document"  # includes text, pdfs and images
    IMAGE = "image"
    AUDIO = "audio"
    PDF = "pdf"


class File(BaseModel):
    content_type: str | None = Field(
        default=None,
        description="The content type of the file",
        examples=["image/png", "image/jpeg", "audio/wav", "application/pdf"],
    )
    data: str | None = Field(default=None, description="The base64 encoded data of the file")
    url: str | None = Field(default=None, description="The URL of the image")

    def to_url(self, default_content_type: str | None = None) -> str:
        if self.data and (self.content_type or default_content_type):
            return f"data:{self.content_type or default_content_type};base64,{self.data}"
        if self.url:
            return self.url
        raise InternalError("No data or URL provided for image")

    @model_validator(mode="after")
    def validate_image(self):
        if self.data:
            try:
                decoded_data = b64decode(self.data)
            except Exception:
                # We should really throw an error here, but let's log a bit for now
                # python is very strict about padding so might need to be more tolerant
                _logger.warning("Found invalid base64 data in file", exc_info=True)
                return self
            if not self.content_type:
                self.content_type = guess_content_type(decoded_data)
            return self
        if self.url:
            if self.url.startswith("data:"):
                content_type, data = _parse_data_url(self.url[5:])
                self.content_type = content_type
                self.data = data
                return self

            if self.content_type:
                return self
            mime_type = mimetypes.guess_type(self.url, strict=False)[0]
            self.content_type = mime_type
            return self

        raise ValueError("No data or URL provided for image")

    @property
    def is_image(self) -> bool | None:
        if not self.content_type:
            return None
        return self.content_type.startswith("image/")

    @property
    def is_audio(self) -> bool | None:
        if not self.content_type:
            return None
        return self.content_type.startswith("audio/")

    @property
    def is_video(self) -> bool | None:
        if not self.content_type:
            return None
        return self.content_type.startswith("video/")

    @property
    def is_pdf(self) -> bool | None:
        if not self.content_type:
            return None
        return self.content_type == "application/pdf"

    @property
    def is_text(self) -> bool | None:
        if not self.content_type:
            return None
        return self.content_type in ["text/plain", "text/markdown", "text/csv", "text/json", "text/html"]

    def get_extension(self) -> str:
        if self.content_type:
            return mimetypes.guess_extension(self.content_type) or ""
        return ""

    def content_bytes(self) -> bytes | None:
        if self.data:
            return b64decode(self.data)
        return None


def _parse_data_url(data_url: str) -> tuple[str, str]:
    splits = data_url.split(";base64,")
    if len(splits) != 2:
        raise ValueError("Invalid base64 data URL")
    return splits[0], splits[1]
