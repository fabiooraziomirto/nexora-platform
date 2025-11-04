"""
Redis client utilities.
"""

from typing import Optional, Any, Union
import json
import redis.asyncio as redis
from redis.asyncio import Redis

from common.config import settings
from common.logging import get_logger

logger = get_logger(__name__)


class Cache:
    """Redis cache client."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        db: Optional[int] = None,
        decode_responses: bool = True,
    ):
        self.host = host or settings.REDIS_HOST
        self.port = port or settings.REDIS_PORT
        self.password = password or settings.REDIS_PASSWORD
        self.db = db or settings.REDIS_DB
        self.decode_responses = decode_responses
        self._client: Optional[Redis] = None

    async def connect(self):
        """Connect to Redis."""
        try:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                decode_responses=self.decode_responses,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
            )
            
            # Test connection
            await self._client.ping()
            
            logger.info(
                "Redis connected",
                host=self.host,
                port=self.port,
                db=self.db,
            )
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise

    async def disconnect(self):
        """Disconnect from Redis."""
        if self._client:
            try:
                await self._client.close()
                logger.info("Redis disconnected")
            except Exception as e:
                logger.error("Error disconnecting Redis", error=str(e))
            finally:
                self._client = None

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self._client:
            raise RuntimeError("Redis client not connected")
        
        try:
            value = await self._client.get(key)
            if value is None:
                return None
            
            # Try to deserialize JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error("Failed to get from cache", key=key, error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ):
        """Set value in cache."""
        if not self._client:
            raise RuntimeError("Redis client not connected")
        
        try:
            # Serialize value
            if isinstance(value, (dict, list)):
                serialized_value = json.dumps(value)
            else:
                serialized_value = str(value)
            
            if ttl:
                await self._client.setex(key, ttl, serialized_value)
            else:
                await self._client.set(key, serialized_value)
        except Exception as e:
            logger.error("Failed to set cache", key=key, error=str(e))
            raise

    async def delete(self, key: str):
        """Delete key from cache."""
        if not self._client:
            raise RuntimeError("Redis client not connected")
        
        try:
            await self._client.delete(key)
        except Exception as e:
            logger.error("Failed to delete from cache", key=key, error=str(e))
            raise

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self._client:
            raise RuntimeError("Redis client not connected")
        
        try:
            result = await self._client.exists(key)
            return result > 0
        except Exception as e:
            logger.error("Failed to check key existence", key=key, error=str(e))
            return False

    async def expire(self, key: str, ttl: int):
        """Set expiration on key."""
        if not self._client:
            raise RuntimeError("Redis client not connected")
        
        try:
            await self._client.expire(key, ttl)
        except Exception as e:
            logger.error("Failed to set expiration", key=key, error=str(e))
            raise

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment key value."""
        if not self._client:
            raise RuntimeError("Redis client not connected")
        
        try:
            return await self._client.incrby(key, amount)
        except Exception as e:
            logger.error("Failed to increment", key=key, error=str(e))
            raise

    async def decrement(self, key: str, amount: int = 1) -> int:
        """Decrement key value."""
        if not self._client:
            raise RuntimeError("Redis client not connected")
        
        try:
            return await self._client.decrby(key, amount)
        except Exception as e:
            logger.error("Failed to decrement", key=key, error=str(e))
            raise

    async def keys(self, pattern: str = "*") -> list:
        """Get keys matching pattern."""
        if not self._client:
            raise RuntimeError("Redis client not connected")
        
        try:
            return await self._client.keys(pattern)
        except Exception as e:
            logger.error("Failed to get keys", pattern=pattern, error=str(e))
            return []

    async def flush(self):
        """Flush all keys."""
        if not self._client:
            raise RuntimeError("Redis client not connected")
        
        try:
            await self._client.flushdb()
            logger.warning("Redis cache flushed")
        except Exception as e:
            logger.error("Failed to flush cache", error=str(e))
            raise

    async def ping(self) -> bool:
        """Ping Redis server."""
        if not self._client:
            return False
        
        try:
            await self._client.ping()
            return True
        except Exception:
            return False


# Global cache instance
_cache: Optional[Cache] = None


def get_cache(
    host: Optional[str] = None,
    port: Optional[int] = None,
    password: Optional[str] = None,
    db: Optional[int] = None,
) -> Cache:
    """Get or create global cache instance."""
    global _cache
    
    if _cache is None:
        _cache = Cache(
            host=host,
            port=port,
            password=password,
            db=db,
        )
    
    return _cache

