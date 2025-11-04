"""
Policy cache implementation using Redis.
"""

import json
import os
from typing import Optional, Dict, Any
import redis.asyncio as redis
import structlog

logger = structlog.get_logger()


class PolicyCache:
    """Policy cache for caching policy evaluation results."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.enabled = os.getenv("POLICY_CACHE_ENABLED", "true").lower() == "true"
        self.ttl = int(os.getenv("POLICY_CACHE_TTL", "3600"))
        self.key_prefix = os.getenv("POLICY_CACHE_KEY_PREFIX", "policy:")
        
        if self.enabled:
            self._connect()
    
    def _connect(self):
        """Connect to Redis."""
        redis_host = os.getenv("REDIS_HOST", "redis-master.stack4things-infrastructure.svc.cluster.local")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_password = os.getenv("REDIS_PASSWORD", "")
        
        try:
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password if redis_password else None,
                decode_responses=True,
            )
            logger.info("Policy cache connected", host=redis_host, port=redis_port)
        except Exception as e:
            logger.warning("Failed to connect to Redis cache", error=str(e))
            self.enabled = False
    
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached policy result."""
        if not self.enabled or not self.redis_client:
            return None
        
        try:
            cached = await self.redis_client.get(f"{self.key_prefix}{key}")
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
        
        return None
    
    async def set(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None):
        """Set cached policy result."""
        if not self.enabled or not self.redis_client:
            return
        
        try:
            ttl = ttl or self.ttl
            await self.redis_client.setex(
                f"{self.key_prefix}{key}",
                ttl,
                json.dumps(value)
            )
        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))
    
    async def invalidate(self, pattern: str):
        """Invalidate cached policies matching pattern."""
        if not self.enabled or not self.redis_client:
            return
        
        try:
            keys = await self.redis_client.keys(f"{self.key_prefix}{pattern}")
            if keys:
                await self.redis_client.delete(*keys)
                logger.info("Cache invalidated", pattern=pattern, count=len(keys))
        except Exception as e:
            logger.warning("Cache invalidation failed", pattern=pattern, error=str(e))

