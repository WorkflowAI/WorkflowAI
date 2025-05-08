import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from core.utils.redis_lock import DedupAcquisitionError, redis_dedup


@pytest.mark.asyncio
async def test_redis_lock_acquire_success():
    """Test successful lock acquisition"""
    mock_redis = AsyncMock()
    mock_redis.set.return_value = True  # Lock acquisition succeeds

    with patch("core.utils.redis_lock.shared_redis_client", mock_redis):
        async with redis_dedup("test:lock:key"):
            # If we get here, lock was acquired successfully
            pass

        # Verify lock was attempted with correct parameters
        mock_redis.set.assert_called_once_with("test:lock:key", "1", nx=True, ex=60)


@pytest.mark.asyncio
async def test_redis_lock_acquire_fail():
    """Test failed lock acquisition"""
    mock_redis = AsyncMock()
    mock_redis.set.return_value = False  # Lock acquisition fails

    with patch("core.utils.redis_lock.shared_redis_client", mock_redis):
        with pytest.raises(DedupAcquisitionError):
            async with redis_dedup("test:lock:key"):
                pytest.fail("Code block should not be executed")


@pytest.mark.asyncio
async def test_redis_lock_no_redis_client():
    """Test behavior when Redis client is not available"""
    with patch("core.utils.redis_lock.shared_redis_client", None):
        # Should proceed without error when Redis is unavailable
        async with redis_dedup("test:lock:key"):
            # Should execute the code block normally
            pass


@pytest.mark.asyncio
async def test_redis_lock_with_custom_expiry():
    """Test lock acquisition with custom expiry time"""
    mock_redis = AsyncMock()
    mock_redis.set.return_value = True

    with patch("core.utils.redis_lock.shared_redis_client", mock_redis):
        async with redis_dedup("test:lock:key", expire_seconds=120):
            pass

        # Verify expiry time was passed correctly
        mock_redis.set.assert_called_once_with("test:lock:key", "1", nx=True, ex=120)


@pytest.mark.asyncio
async def test_redis_lock_concurrent_access():
    """Test concurrent access to the same lock"""
    mock_redis = AsyncMock()
    # First call succeeds, second call fails (simulating concurrent access)
    mock_redis.set.side_effect = [True, False]

    with patch("core.utils.redis_lock.shared_redis_client", mock_redis):
        # First task acquires the lock
        task1_completed = False

        async def task1():
            nonlocal task1_completed
            async with redis_dedup("test:lock:key"):
                # Simulate some work
                await asyncio.sleep(0.1)
                task1_completed = True

        # Second task attempts to acquire the same lock
        async def task2():
            try:
                async with redis_dedup("test:lock:key"):
                    pytest.fail("Second task should not acquire the lock")
            except DedupAcquisitionError:
                # Expected exception
                pass

        # Run both tasks concurrently
        await asyncio.gather(task1(), task2())

        # Verify first task completed its work
        assert task1_completed is True
