from typing import NamedTuple, Protocol


class FileData(NamedTuple):
    contents: bytes
    content_type: str | None = None
    filename: str | None = None


class CouldNotStoreFileError(Exception):
    pass


class FileStorage(Protocol):
    async def store_file(self, file: FileData, folder_path: str) -> str: ...
