import asyncio
import pickle
from collections.abc import AsyncIterator
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from .redis_cache import redis_cached, redis_cached_generator_last_chunk, shared_redis_client, should_run_today


# Define test classes at module level for proper pickling
class TestClassForCache:
    # Class variable to track call count
    class_method_call_count: int = 0

    def __init__(self, instance_id: str):
        self.instance_id = instance_id
        self.call_count = 0

    @redis_cached()
    async def cached_instance_method(self, param: str) -> str:
        self.call_count += 1
        return f"instance_{param}_{self.call_count}"

    @classmethod
    @redis_cached()
    async def cached_class_method(cls, param: str) -> str:
        # Use properly defined class variable
        TestClassForCache.class_method_call_count += 1
        return f"class_{param}_{TestClassForCache.class_method_call_count}"


class SubTestClassForCache(TestClassForCache):
    pass


async def test_redis_cached_hit() -> None:
    # Setup mock cache with existing data
    mock_cache = AsyncMock()
    cached_result = "cached_value"
    mock_cache.get.return_value = pickle.dumps(cached_result)

    mock_inner = AsyncMock(return_value="fresh_value")

    with patch("core.utils.redis_cache.shared_redis_client", mock_cache):

        @redis_cached()
        async def test_func(param: str) -> str:
            return await mock_inner(param)

        result = await test_func("test_param")

    assert result == "cached_value"
    mock_cache.get.assert_called_once()
    mock_cache.setex.assert_not_called()
    mock_inner.assert_not_called()  # Function should not be called on cache hit


async def test_redis_cached_miss() -> None:
    # Setup mock cache with no existing data
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None

    mock_inner = AsyncMock(return_value="fresh_value")

    with patch("core.utils.redis_cache.shared_redis_client", mock_cache):

        @redis_cached()
        async def test_func(param: str) -> str:
            return await mock_inner(param)

        result = await test_func("test_param")

    assert result == "fresh_value"
    mock_cache.get.assert_called_once()
    mock_cache.setex.assert_called_once()
    mock_inner.assert_called_once_with("test_param")  # Function should be called on cache miss


async def test_redis_cached_non_async_function() -> None:
    """
    This test verifies that redis_cached() works with non-async functions.
    The decorator wraps non-async functions to make them awaitable since it needs to
    interact with Redis asynchronously, even though the wrapped function is synchronous.
    """

    mock_cache = AsyncMock()
    mock_cache.get.return_value = None

    mock_inner = Mock(return_value="sync_value")

    with patch("core.utils.redis_cache.shared_redis_client", mock_cache):

        @redis_cached()
        def test_func(param: str) -> str:  # Note: non-async function
            return mock_inner(param)

        # We await because redis_cached() makes the function awaitable to handle Redis I/O
        result = await test_func("test_param")  # pyright: ignore

    assert result == "sync_value"
    mock_cache.setex.assert_called_once()
    mock_inner.assert_called_once_with("test_param")  # Function should be called


async def test_redis_cached_class_methods() -> None:
    """
    Test that redis_cached works with class methods and instance methods,
    properly ignoring self/cls parameters when generating cache keys.
    """
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None

    # Set up class counter for tracking calls
    TestClassForCache.class_method_call_count = 0

    with patch("core.utils.redis_cache.shared_redis_client", mock_cache):
        # Test instance method cache ignores 'self'
        instance1 = TestClassForCache("instance1")
        instance2 = TestClassForCache("instance2")

        # First call from instance1
        result1 = await instance1.cached_instance_method("param")
        assert result1 == "instance_param_1"
        assert instance1.call_count == 1

        # Capture the cache key used for the first call
        instance1_cache_key = mock_cache.get.call_args[0][0]
        # Reset mock between calls to verify separate cache lookups
        mock_cache.get.reset_mock()
        mock_cache.get.return_value = pickle.dumps(result1)

        # Second call from instance2 should use same cache (if self is ignored)
        result2 = await instance2.cached_instance_method("param")

        # Capture the cache key used for the second call
        instance2_cache_key = mock_cache.get.call_args[0][0]
        assert result2 == "instance_param_1"  # Should get cached value from first call
        assert instance2.call_count == 0  # Should not increment if cache hit

        # Test class method cache ignores 'cls'
        mock_cache.get.return_value = None
        result3 = await TestClassForCache.cached_class_method("param")
        assert result3 == "class_param_1"
        assert TestClassForCache.class_method_call_count == 1

        # Capture the cache key used for the parent class
        parent_cache_key = mock_cache.get.call_args[0][0]
        # Create subclass and verify cache is shared when using same parameters
        mock_cache.get.reset_mock()
        mock_cache.get.return_value = pickle.dumps(result3)

        result4 = await SubTestClassForCache.cached_class_method("param")

        # Capture the cache key used for the subclass
        subclass_cache_key = mock_cache.get.call_args[0][0]
        assert instance1_cache_key == instance2_cache_key
        assert parent_cache_key == subclass_cache_key
        assert result4 == "class_param_1"  # Should get cached value
        assert TestClassForCache.class_method_call_count == 1  # Should not increment


async def test_redis_cached_cache_error() -> None:
    mock_cache = AsyncMock()
    mock_cache.get.side_effect = Exception("Redis connection error")

    mock_inner = AsyncMock(return_value="fallback_value")

    with patch("core.utils.redis_cache.shared_redis_client", mock_cache):

        @redis_cached()
        def test_func(param: str) -> str:  # Note: non-async function
            return mock_inner(param)

        # We await because redis_cached() makes the function awaitable to handle Redis I/O
        result = await test_func("test_param")  # pyright: ignore

    assert result == "fallback_value"
    mock_cache.get.assert_called_once()
    mock_cache.setex.assert_not_called()
    mock_inner.assert_called_once_with("test_param")  # Function should be called on error


async def test_redis_cached_with_complex_args() -> None:
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None

    mock_inner = AsyncMock(return_value={"result": 30})

    with patch("core.utils.redis_cache.shared_redis_client", mock_cache):

        @redis_cached()
        async def test_func(a: int, b: dict[str, int], c: str = "default") -> dict[str, int]:
            return await mock_inner(a, b, c)

        complex_args = {"value": 20}
        result = await test_func(10, complex_args, c="custom")

    assert result == {"result": 30}
    mock_cache.get.assert_called_once()
    mock_cache.setex.assert_called_once()
    mock_inner.assert_called_once_with(10, complex_args, "custom")  # Function should be called with correct args


@pytest.mark.skip(reason="This test requires a real Redis instance")
async def test_redis_cached_expiration_real() -> None:
    """
    Test cache expiration using the real Redis instance.
    We only track function calls to verify cache behavior.
    """
    call_count: int = 0

    @redis_cached(expiration_seconds=1)
    async def test_func(param: str) -> str:
        nonlocal call_count
        call_count += 1
        return f"fresh_value_{call_count}"

    # First call: cache miss; function should be called
    result1: str = await test_func("test_param")
    assert result1 == "fresh_value_1"
    first_call_count: int = call_count

    # Second call immediately: cache hit; function should not be called again
    result2: str = await test_func("test_param")
    assert result2 == "fresh_value_1"
    assert call_count == first_call_count  # Should not have increased

    # Wait for the cache to expire
    await asyncio.sleep(2)

    # Third call after expiration: cache miss; function should be called again
    result3: str = await test_func("test_param")
    assert result3 == "fresh_value_2"
    assert call_count == first_call_count + 1  # Should have increased by 1


# Tests for redis_cache_async_generator_result


async def test_async_generator_cache_hit() -> None:
    """Test that redis_cache_async_generator_result returns cached final result on cache hit."""
    mock_cache = AsyncMock()
    cached_result = "final_cached_chunk"
    mock_cache.get.return_value = pickle.dumps(cached_result)

    # Define a properly typed async generator
    async def mock_generator(param: str) -> AsyncIterator[str]:
        for item in ["chunk1", "chunk2", "final_chunk"]:
            yield item

    # Create mock for tracking calls without actually calling
    call_tracker = Mock()

    with patch("core.utils.redis_cache.shared_redis_client", mock_cache):

        @redis_cached_generator_last_chunk()
        async def test_func(param: str) -> AsyncIterator[str]:
            call_tracker(param)  # Track that this function was called
            async for item in mock_generator(param):
                yield item

        # Collect all yielded items
        result = [item async for item in test_func("test_param")]

    # Should yield only the cached final result
    assert result == ["final_cached_chunk"]
    mock_cache.get.assert_called_once()
    mock_cache.setex.assert_not_called()
    # The original function should not be called on cache hit
    call_tracker.assert_not_called()


async def test_async_generator_cache_miss() -> None:
    """Test that redis_cache_async_generator_result caches the last yielded item."""
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None

    # Create a real async generator that yields multiple items
    async def real_generator(param: str) -> AsyncIterator[str]:
        for item in ["chunk1", "chunk2", "final_chunk"]:
            yield item

    with patch("core.utils.redis_cache.shared_redis_client", mock_cache):

        @redis_cached_generator_last_chunk()
        async def test_func(param: str) -> AsyncIterator[str]:
            async for item in real_generator(param):
                yield item

        # Collect all yielded items
        result = [item async for item in test_func("test_param")]

    # Should yield all items from the original generator
    assert result == ["chunk1", "chunk2", "final_chunk"]
    mock_cache.get.assert_called_once()
    # Should cache the last yielded item
    mock_cache.setex.assert_called_once()
    # The cached value should be the last yielded item
    cached_value = pickle.loads(mock_cache.setex.call_args[0][2])
    assert cached_value == "final_chunk"


async def test_async_generator_cache_error() -> None:
    """Test that redis_cache_async_generator_result handles Redis errors gracefully."""
    mock_cache = AsyncMock()
    mock_cache.get.side_effect = Exception("Redis connection error")

    # Create an async generator that yields multiple items
    async def real_generator(param: str) -> AsyncIterator[str]:
        for item in ["chunk1", "chunk2", "final_chunk"]:
            yield item

    with patch("core.utils.redis_cache.shared_redis_client", mock_cache):

        @redis_cached_generator_last_chunk()
        async def test_func(param: str) -> AsyncIterator[str]:
            async for item in real_generator(param):
                yield item

        # Collect all yielded items
        result = [item async for item in test_func("test_param")]

    # Should yield all items from the original generator despite Redis error
    assert result == ["chunk1", "chunk2", "final_chunk"]
    mock_cache.get.assert_called_once()
    # Should attempt to cache the last item despite earlier error
    mock_cache.setex.assert_called_once()


async def test_async_generator_empty() -> None:
    """Test behavior when the generator yields no items."""
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None

    # Create an empty async generator
    async def empty_generator(param: str) -> AsyncIterator[str]:
        if False:  # Never yield anything
            yield "this will never be yielded"

    with patch("core.utils.redis_cache.shared_redis_client", mock_cache):

        @redis_cached_generator_last_chunk()
        async def test_func(param: str) -> AsyncIterator[str]:
            async for item in empty_generator(param):
                yield item

        # Collect all yielded items (should be empty)
        result = [item async for item in test_func("test_param")]

    # Should yield nothing
    assert result == []
    mock_cache.get.assert_called_once()
    # Should not try to cache anything since there's no last item
    mock_cache.setex.assert_not_called()


@pytest.mark.parametrize(
    "input_chunks,expected_result",
    [
        (["chunk1", "chunk2", "final"], ["final"]),  # Normal case
        (["single_chunk"], ["single_chunk"]),  # Single item
        ([], []),  # Empty generator
    ],
)
async def test_async_generator_cached_different_scenarios(input_chunks: list[str], expected_result: list[str]) -> None:
    """Test redis_cache_async_generator_result with different generator scenarios using parametrize."""
    # Setup for cache hit (reuse cached result)
    mock_cache = AsyncMock()

    # Only set up the cache if we expect a cached result
    if expected_result:
        cached_result = expected_result[0]
        mock_cache.get.return_value = pickle.dumps(cached_result)
    else:
        mock_cache.get.return_value = None

    async def mock_generator(param: str) -> AsyncIterator[str]:
        for item in input_chunks:
            yield item

    with patch("core.utils.redis_cache.shared_redis_client", mock_cache):

        @redis_cached_generator_last_chunk()
        async def test_func(param: str) -> AsyncIterator[str]:
            async for item in mock_generator(param):
                yield item

        # Collect all yielded items
        result = [item async for item in test_func("test_param")]

    if expected_result:
        assert result == expected_result
        mock_cache.get.assert_called_once()
    else:
        assert result == []
        mock_cache.get.assert_called_once()


class TestShouldRunToday:
    # TODO: This is pretty hard to test since
    # the function relies on expiration time in the redis server
    @pytest.mark.skip(reason="This test requires a real Redis instance")
    async def test_should_run_today(self):
        if shared_redis_client:
            await shared_redis_client.delete("test_key")

        today = datetime.now().date()
        assert await should_run_today("test_key", today)
        assert not await should_run_today("test_key", today)
