import asyncio
import functools
import hashlib
import inspect
import logging
import os
import pickle
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta
from typing import Any, Callable, Optional, TypeVar

import redis.asyncio as aioredis

F = TypeVar("F", bound=Callable[..., Any])
AG = TypeVar("AG", bound=Callable[..., AsyncIterator[Any]])

_logger = logging.getLogger(__name__)


def get_redis_client() -> Any:
    try:
        async_cache: aioredis.Redis | None = aioredis.from_url(os.environ["JOBS_BROKER_URL"])  # pyright: ignore
    except (KeyError, ValueError):
        async_cache = None

    return async_cache


shared_redis_client: aioredis.Redis | None = get_redis_client()


def _generate_cache_key(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    suffix: str = "",
) -> str:
    """
    Generate a cache key based on function and arguments.

    Args:
        func: The function being decorated
        args: Positional arguments to the function
        kwargs: Keyword arguments to the function
        suffix: Optional suffix to differentiate different types of caches

    Returns:
        str: Cache key string
    """
    # Use the original function, not the wrapper
    if hasattr(func, "__wrapped__"):
        orig_func = func.__wrapped__  # pyright: ignore
    else:
        orig_func = func

    # Get the function's qualified name to detect if it's a method
    is_method = False
    if hasattr(orig_func, "__qualname__") and "." in orig_func.__qualname__:
        is_method = True

    # Skip the first argument (self/cls) for methods
    args_to_hash = args[1:] if is_method and args else args

    # Generate hash from the args (excluding self/cls) and kwargs
    try:
        args_bytes: bytes = pickle.dumps((args_to_hash, kwargs))
        args_hash: str = hashlib.sha256(args_bytes).hexdigest()
    except Exception:
        # Fallback to string representation if pickling fails
        args_str = str(args_to_hash) + str(kwargs)
        args_hash: str = hashlib.sha256(args_str.encode()).hexdigest()

    module_name: str = func.__module__
    func_name: str = func.__name__
    return f"{module_name}.{func_name}{suffix}:{args_hash}"


def redis_cached(expiration_seconds: int = 60 * 60 * 24) -> Callable[[F], F]:  # noqa: C901
    def decorator(func: F) -> F:  # noqa: C901
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            if not shared_redis_client:
                _logger.warning(
                    "Redis cache is not available, skipping redis_cached",
                    extra={"func": f"{func.__module__}.{func.__name__}"},
                )
                # Fallback to direct execution
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                result = func(*args, **kwargs)
                if inspect.isawaitable(result):
                    result = await result
                return result
            try:
                cache_key = _generate_cache_key(func, args, kwargs)

                cached_result: Optional[bytes] = await shared_redis_client.get(cache_key)  # pyright: ignore
                if cached_result:
                    return pickle.loads(cached_result)  # pyright: ignore

                # Call the function and await if it returns a coroutine
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                    # Handle the case where a non-async function returns an awaitable
                    if inspect.isawaitable(result):
                        result = await result

                await shared_redis_client.setex(cache_key, expiration_seconds, pickle.dumps(result))  # pyright: ignore
                return result
            except Exception as e:
                _logger.exception("Exception in redis_cached", extra={"error": str(e)})
                # Fallback execution
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                result = func(*args, **kwargs)
                if inspect.isawaitable(result):
                    return await result
                return result

        return async_wrapper  # type: ignore

    return decorator


async def _try_retrieve_cached_result(redis_cache: aioredis.Redis, cache_key: str) -> Optional[Any]:
    """Helper function to retrieve and deserialize a cached result."""
    try:
        cached_bytes = await redis_cache.get(cache_key)  # pyright: ignore
        if cached_bytes:
            return pickle.loads(cached_bytes)  # pyright: ignore
    except Exception as e:
        _logger.exception("Failed to get cache for", extra={"cache_key": cache_key, "error": str(e)})
    return None


async def _try_cache_result(redis_cache: aioredis.Redis, cache_key: str, result: Any, expiration_seconds: int) -> None:
    """Helper function to cache a result."""
    try:
        await redis_cache.setex(cache_key, expiration_seconds, pickle.dumps(result))  # pyright: ignore
    except Exception as e:
        _logger.exception("Failed to cache result for", extra={"cache_key": cache_key, "error": str(e)})


def redis_cached_generator_last_chunk(expiration_seconds: int = 60 * 60 * 24) -> Callable[[AG], AG]:  # noqa: C901
    """
    Decorator to cache the final chunk of an async generator function in Redis.

    Limitations:
        - Only the *final* result (the last yielded item) is cached.
        - It assumes that the last item yielded by the generator represents the complete, cumulative result.
        - It does not cache the intermediate streamed items.
    """

    def decorator(func: AG) -> AG:
        @functools.wraps(func)
        async def async_generator_wrapper(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
            if not shared_redis_client:
                _logger.warning(
                    "Redis cache is not available, skipping redis_cached_generator",
                    extra={"func": f"{func.__module__}.{func.__name__}"},
                )
                async for item in func(*args, **kwargs):
                    yield item
                return

            cache_key = _generate_cache_key(func, args, kwargs, suffix=".generator_result")

            try:
                # Check for cached result
                cached_item = await _try_retrieve_cached_result(shared_redis_client, cache_key)
                if cached_item is not None:
                    # Cache hit - yield the cached item
                    yield cached_item
                    return

                # Cache miss - run the generator
                last_yielded = None

                async for item in func(*args, **kwargs):
                    last_yielded = item
                    yield item

                # Cache the last yielded item if there is one
                if last_yielded is not None:
                    await _try_cache_result(shared_redis_client, cache_key, last_yielded, expiration_seconds)
                else:
                    _logger.warning(
                        "Generator yielded no items for nothing to cache.",
                        extra={"cache_key": cache_key},
                    )
            except Exception as e:
                _logger.exception("Error in cached generator for", extra={"cache_key": cache_key, "error": str(e)})
                # Fallback to original function on error
                async for item in func(*args, **kwargs):
                    yield item

        # the type checker can't verify that the wrapped function
        return async_generator_wrapper  # type: ignore

    return decorator


async def should_run_today(key: str, today: date) -> bool:
    """Returns True exactly once per calendar day (00:00–23:59)."""
    if not shared_redis_client:
        raise RuntimeError("Redis cache is not available")

    tomorrow = datetime(year=today.year, month=today.month, day=today.day) + timedelta(days=1)
    secs = int((tomorrow - datetime.now()).total_seconds())

    # Try to set the key with NX; expire it at the end of the day
    # If this call returns True, key did not exist → first run today
    value = await shared_redis_client.set(key, "1", nx=True, ex=secs)
    return value is not None
