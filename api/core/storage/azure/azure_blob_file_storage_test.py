import os
from io import FileIO

import pytest

from core.storage.azure.azure_blob_file_storage import AzureBlobFileStorage
from core.storage.file_storage import FileData
from tests.utils import fixture_bytes, fixture_path


@pytest.fixture
async def azure_blob_storage(
    # Using global fixture to make sure the container is created
    test_blob_storage: None,
) -> AzureBlobFileStorage:
    return AzureBlobFileStorage(
        connection_string=os.environ["WORKFLOWAI_STORAGE_CONNECTION_STRING"],
        container_name=os.environ["WORKFLOWAI_STORAGE_TASK_RUNS_CONTAINER"],
    )


async def test_connection_established(azure_blob_storage: AzureBlobFileStorage):
    # Test that we can establish a connection and get container client
    blob_service_client = await azure_blob_storage._get_blob_service_client()  # pyright: ignore[reportPrivateUsage]
    assert blob_service_client is not None

    # Test that we can get a blob client
    blob_client_properties = await blob_service_client.get_service_properties()
    assert blob_client_properties is not None

    container_properties = await blob_service_client.get_container_client(
        azure_blob_storage.container_name,
    ).get_container_properties()
    assert container_properties is not None


async def test_store_file(azure_blob_storage: AzureBlobFileStorage):
    blob_service_client = await azure_blob_storage._get_blob_service_client()  # pyright: ignore[reportPrivateUsage]
    assert blob_service_client is not None
    assert hasattr(blob_service_client, "url")

    file_data = fixture_bytes("files", "test.png")

    folder_path = "test/local"

    blob_name = f"{folder_path}/52bcf683da5693c81ce5d748bd2e158971dc0abbe5f8500440240c64569c0ca4.png"
    url = await azure_blob_storage.store_file(
        FileData(contents=file_data, content_type="image/png"),
        folder_path,
    )

    container_url = f"{blob_service_client.url}{azure_blob_storage.container_name}"  # type: ignore
    assert url == f"{container_url}/{blob_name}"


async def test_store_upload_file(azure_blob_storage: AzureBlobFileStorage):
    blob_service_client = await azure_blob_storage._get_blob_service_client()  # pyright: ignore[reportPrivateUsage]
    assert blob_service_client is not None
    assert hasattr(blob_service_client, "url")

    _file = FileIO(file=fixture_path("files", "test.png"))
    file = FileData(
        filename="test.png",
        contents=_file.read(),
        content_type="image/png",
    )
    folder_path = "test/local"
    blob_name = f"{folder_path}/52bcf683da5693c81ce5d748bd2e158971dc0abbe5f8500440240c64569c0ca4.png"
    url = await azure_blob_storage.store_file(file, folder_path)

    container_url = f"{blob_service_client.url}{azure_blob_storage.container_name}"  # type: ignore
    assert url == f"{container_url}/{blob_name}"
