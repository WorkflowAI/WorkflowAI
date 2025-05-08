import logging
from contextlib import asynccontextmanager

from core.utils.redis_cache import shared_redis_client

_logger = logging.getLogger(__name__)


class DedupAcquisitionError(Exception):
    """Exception raised when a deduplication cannot be acquired."""

    pass


@asynccontextmanager
async def redis_dedup(dedup_key: str, expire_seconds: int = 60):
    """
    Simple Redis deduplication context manager.

    Args:
        dedup_key: Unique key to use for the deduplication
        expire_seconds: Deduplication expiration time in seconds

    Raises:
        DedupAcquisitionError: If the deduplication cannot be acquired
    """
    if shared_redis_client is None:
        _logger.warning("Redis client not available, proceeding without deduplication", extra={"dedup_key": dedup_key})
        yield
        return

    # Try to acquire the deduplication - simply set a key if it doesn't exist
    acquired = await shared_redis_client.set(dedup_key, "1", nx=True, ex=expire_seconds)

    if not acquired:
        _logger.info("Failed to acquire deduplication, resource already locked", extra={"dedup_key": dedup_key})
        raise DedupAcquisitionError(f"Could not acquire deduplication: {dedup_key}")

    try:
        yield
    finally:
        pass
