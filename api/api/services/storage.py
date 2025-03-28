import os
from base64 import b64decode

from core.domain.events import EventRouter
from core.storage.backend_storage import SystemBackendStorage
from core.storage.combined.combined_storage import CombinedStorage
from core.storage.mongo.mongo_storage import MongoStorage
from core.utils import no_op
from core.utils.aeshmac import AESHMAC
from core.utils.encryption import Encryption

_base_client, _db_name = MongoStorage.build_client(os.environ["WORKFLOWAI_MONGO_CONNECTION_STRING"])

_default_encryption = AESHMAC(
    hmac_key=b64decode(os.environ["STORAGE_HMAC"]),
    aes_key=b64decode(os.environ["STORAGE_AES"]),
)


def shared_encryption():
    return _default_encryption


def storage_for_tenant(
    tenant: str,
    tenant_uid: int,
    event_router: EventRouter,
    encryption: Encryption | None = None,
):
    return CombinedStorage(
        tenant=tenant,
        tenant_uid=tenant_uid,
        mongo_client=_base_client,
        mongo_db_name=_db_name,
        encryption=encryption or _default_encryption,
        event_router=event_router,
        clickhouse_dsn=os.getenv("CLICKHOUSE_CONNECTION_STRING"),
    )


def system_storage(encryption: Encryption | None = None) -> SystemBackendStorage:
    return storage_for_tenant("__system__", -1, no_op.event_router, encryption)
