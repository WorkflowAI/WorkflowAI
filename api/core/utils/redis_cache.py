import asyncio
import functools
import hashlib
import logging
import os
import pickle
from collections.abc import AsyncIterator
from typing import Any, Callable, Optional, TypeVar

F = TypeVar("F", bound=Callable[..., Any])
AG = TypeVar("AG", bound=Callable[..., AsyncIterator[Any]])

_logger = logging.getLogger(__name__)


def get_redis_client() -> Any:
    import redis.asyncio as aioredis

    try:
        async_cache: aioredis.Redis | None = aioredis.from_url(os.environ["JOBS_BROKER_URL"])  # pyright: ignore
    except (KeyError, ValueError):
        async_cache = None

    return async_cache


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
    args_bytes: bytes = pickle.dumps((args, kwargs))
    args_hash: str = hashlib.sha256(args_bytes).hexdigest()
    module_name: str = func.__module__
    func_name: str = func.__name__
    return f"{module_name}.{func_name}{suffix}:{args_hash}"


def redis_cached(expiration_seconds: int = 60 * 60 * 24) -> Callable[[F], F]:  # default ttl is 1 day
    async_cache = get_redis_client()
    if not async_cache:
        _logger.warning("Redis cache is not available, skipping redis_cached")

        def decorator(func: F) -> F:
            return func

        return decorator

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                cache_key = _generate_cache_key(func, args, kwargs)

                cached_result: Optional[bytes] = await async_cache.get(cache_key)  # pyright: ignore
                if cached_result:
                    return pickle.loads(cached_result)  # pyright: ignore

                result: Any = (
                    await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                )
                await async_cache.setex(cache_key, expiration_seconds, pickle.dumps(result))  # pyright: ignore
                return result
            except Exception:
                return await func(*args, **kwargs)

        return async_wrapper  # type: ignore

    return decorator


async def _try_retrieve_cached_result(async_cache: Any, cache_key: str) -> Optional[Any]:
    """Helper function to retrieve and deserialize a cached result."""
    try:
        cached_bytes = await async_cache.get(cache_key)  # pyright: ignore
        if cached_bytes:
            return pickle.loads(cached_bytes)  # pyright: ignore
    except Exception as e:
        _logger.exception("Failed to get cache for", exc_info=e, extra={"cache_key": cache_key})
    return None


async def _try_cache_result(async_cache: Any, cache_key: str, result: Any, expiration_seconds: int) -> None:
    """Helper function to cache a result."""
    try:
        await async_cache.setex(cache_key, expiration_seconds, pickle.dumps(result))  # pyright: ignore
    except Exception as e:
        _logger.exception("Failed to cache result for", exc_info=e, extra={"cache_key": cache_key})


async def _safely_close_redis(async_cache: Any) -> None:
    """Helper function to safely close Redis connections."""
    if async_cache and hasattr(async_cache, "close") and callable(async_cache.close):
        try:
            await asyncio.shield(async_cache.close())
        except Exception as e:
            _logger.exception("Error while closing redis", exc_info=e)


def redis_cached_generator_last_chunk(expiration_seconds: int = 60 * 60 * 24) -> Callable[[AG], AG]:
    """
    Decorator to cache the final chunk of an async generator function in Redis.

    Limitations:
        - Only the *final* result (the last yielded item) is cached.
        - It assumes that the last item yielded by the generator represents the complete, cumulative result.
        - It does not cache the intermediate streamed items.
    """
    async_cache = get_redis_client()
    if not async_cache:
        _logger.warning("Redis cache is not available, skipping redis_cached_generator")
        return lambda func: func  # type: ignore

    def decorator(func: AG) -> AG:
        @functools.wraps(func)
        async def async_generator_wrapper(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
            cache_key = _generate_cache_key(func, args, kwargs, suffix=".generator_result")

            try:
                # Check for cached result
                cached_item = await _try_retrieve_cached_result(async_cache, cache_key)
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
                    await _try_cache_result(async_cache, cache_key, last_yielded, expiration_seconds)
                else:
                    _logger.warning(
                        "Generator yielded no items for nothing to cache.",
                        extra={"cache_key": cache_key},
                    )

            except Exception as e:
                _logger.exception("Error in cached generator for", exc_info=e)
                # Fallback to original function on error
                async for item in func(*args, **kwargs):
                    yield item
            finally:
                await _safely_close_redis(async_cache)

        # the type checker can't verify that the wrapped function
        return async_generator_wrapper  # type: ignore

    return decorator
