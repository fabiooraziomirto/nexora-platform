# RBAC Service - Policy Evaluator API

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import structlog
import os

from rbac_service.core.policy_engine import PolicyEngine
from rbac_service.core.policy_cache import PolicyCache
from rbac_service.core.audit import AuditLogger

logger = structlog.get_logger()

app = FastAPI(
    title="Stack4Things RBAC Service",
    description="Policy evaluation and RBAC management service",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
policy_engine = PolicyEngine()
policy_cache = PolicyCache()
audit_logger = AuditLogger()


class PolicyRequest(BaseModel):
    user_id: str
    user_name: str
    roles: List[str]
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    project_id: Optional[str] = None
    target_user_id: Optional[str] = None


class PolicyResponse(BaseModel):
    allowed: bool
    reason: Optional[str] = None


@app.post("/api/v2/rbac/authorize", response_model=PolicyResponse)
async def authorize(request: PolicyRequest):
    """Authorize an action based on user roles and policies."""
    try:
        # Check cache first
        cache_key = f"{request.user_id}:{request.action}:{request.resource_type}:{request.resource_id}"
        cached_result = await policy_cache.get(cache_key)
        if cached_result is not None:
            logger.debug("Policy check cached", cache_key=cache_key, result=cached_result)
            return PolicyResponse(**cached_result)
        
        # Evaluate policy
        allowed = policy_engine.authorize(
            user_id=request.user_id,
            user_name=request.user_name,
            roles=request.roles,
            action=request.action,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            project_id=request.project_id,
            target_user_id=request.target_user_id,
        )
        
        result = {
            "allowed": allowed,
            "reason": None if allowed else "Access denied by policy"
        }
        
        # Cache result
        await policy_cache.set(cache_key, result, ttl=3600)
        
        # Audit log
        await audit_logger.log(
            user_id=request.user_id,
            user_name=request.user_name,
            roles=request.roles,
            action=request.action,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            allowed=allowed,
        )
        
        return PolicyResponse(**result)
        
    except Exception as e:
        logger.error("Policy evaluation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v2/rbac/roles")
async def list_roles():
    """List all available roles."""
    roles = policy_engine.list_roles()
    return {"roles": roles}


@app.get("/api/v2/rbac/policies")
async def list_policies():
    """List all policies."""
    policies = policy_engine.list_policies()
    return {"policies": policies}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "rbac-service"}


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    # Check policy engine and cache
    if not policy_engine.is_ready():
        raise HTTPException(status_code=503, detail="Policy engine not ready")
    return {"status": "ready", "service": "rbac-service"}

