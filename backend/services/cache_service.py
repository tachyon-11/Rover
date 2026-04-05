import hashlib
import json
import logging
import os
import redis
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
TTL_SECONDS = 30 * 60  # 30 minutes

# ─────────────────────────────────────────
# Singleton — one Redis connection
# reused across all cache calls
# ─────────────────────────────────────────
_redis_client = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            REDIS_URL,
            decode_responses=True
        )
        logger.info("Redis client connected")
    return _redis_client


def make_cache_key(query: str, n_results: int) -> str:
    """
    Creates a unique cache key from query + n_results.
    Uses MD5 hash so key is always a fixed length
    regardless of query length.

    Example:
    "Goldman Sachs resume" + 5
    → "search:a3f2c1d4e5b6..."
    """
    raw = f"{query.strip().lower()}:{n_results}"
    hashed = hashlib.md5(raw.encode()).hexdigest()
    return f"search:{hashed}"


def get_cached_result(query: str, n_results: int) -> dict | None:
    """
    Returns cached search result if it exists.
    Returns None if cache miss.
    """
    try:
        client = get_redis()
        key = make_cache_key(query, n_results)
        cached = client.get(key)

        if cached:
            logger.info(f"Cache HIT: {query[:50]}")
            return json.loads(cached)

        logger.info(f"Cache MISS: {query[:50]}")
        return None

    except Exception as e:
        # Never let cache failure break search
        logger.error(f"Redis get error: {e}")
        return None


def set_cached_result(
    query: str,
    n_results: int,
    result: dict
) -> None:
    """
    Stores search result in Redis with TTL.
    Fails silently — cache errors never break search.
    """
    try:
        client = get_redis()
        key = make_cache_key(query, n_results)
        client.setex(
            name=key,
            time=TTL_SECONDS,
            value=json.dumps(result)
        )
        logger.info(
            f"Cache SET: {query[:50]} "
            f"(TTL: {TTL_SECONDS//60} mins)"
        )
    except Exception as e:
        logger.error(f"Redis set error: {e}")


def invalidate_search_cache() -> int:
    """
    Clears all search cache entries.
    Useful when new files are added.
    Returns number of keys deleted.
    """
    try:
        client = get_redis()
        keys = client.keys("search:*")
        if keys:
            client.delete(*keys)
            logger.info(f"Cache invalidated: {len(keys)} keys deleted")
            return len(keys)
        return 0
    except Exception as e:
        logger.error(f"Redis invalidate error: {e}")
        return 0


def get_cache_stats() -> dict:
    """Returns Redis cache statistics."""
    try:
        client = get_redis()
        keys = client.keys("search:*")
        info = client.info("memory")
        return {
            "cached_queries": len(keys),
            "ttl_minutes": TTL_SECONDS // 60,
            "memory_used": info.get("used_memory_human", "unknown")
        }
    except Exception as e:
        logger.error(f"Redis stats error: {e}")
        return {"error": str(e)}