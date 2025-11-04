"""
Policy Engine implementation using oslo.policy style evaluation.
"""

import json
import os
from typing import List, Optional, Dict, Any
import structlog

logger = structlog.get_logger()


class PolicyEngine:
    """Policy engine for evaluating access control policies."""
    
    def __init__(self):
        self.policies = {}
        self.rules = {}
        self._load_policies()
    
    def _load_policies(self):
        """Load policies from ConfigMap."""
        policy_file = os.getenv("POLICY_FILE", "/etc/policy/policy.json")
        try:
            with open(policy_file, 'r') as f:
                self.policies = json.load(f)
            
            # Extract rules
            for key, value in self.policies.items():
                if key.startswith("rule:"):
                    self.rules[key[5:]] = value
            
            logger.info("Policies loaded", count=len(self.policies))
        except FileNotFoundError:
            logger.warning("Policy file not found, using defaults", file=policy_file)
            self._load_default_policies()
    
    def _load_default_policies(self):
        """Load default policies."""
        self.policies = {
            "default": "rule:admin_or_owner",
            "admin_or_owner": "role:admin or project_id:%(project_id)s",
        }
    
    def authorize(
        self,
        user_id: str,
        user_name: str,
        roles: List[str],
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        project_id: Optional[str] = None,
        target_user_id: Optional[str] = None,
    ) -> bool:
        """Authorize an action."""
        # Build context
        context = {
            "user_id": user_id,
            "user_name": user_name,
            "roles": roles,
            "project_id": project_id,
            "target_user_id": target_user_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
        }
        
        # Get policy rule
        policy_key = f"{resource_type}:{action}"
        if policy_key not in self.policies:
            policy_key = "default"
        
        rule = self.policies.get(policy_key, "rule:default")
        
        # Evaluate rule
        return self._evaluate_rule(rule, context)
    
    def _evaluate_rule(self, rule: str, context: Dict[str, Any]) -> bool:
        """Evaluate a policy rule."""
        # Replace context variables
        rule = rule % context
        
        # Simple rule evaluation
        # Supports: role:admin, project_id:xxx, user_id:xxx, and/or/not
        
        # Check for admin role
        if "role:admin" in rule or "role:admin" in context.get("roles", []):
            return True
        
        # Evaluate role checks
        if "role:" in rule:
            for role_check in rule.split():
                if role_check.startswith("role:"):
                    role_name = role_check.split(":")[1]
                    if role_name in context.get("roles", []):
                        return True
        
        # Check project_id match
        if "project_id:" in rule and context.get("project_id"):
            project_check = f"project_id:{context['project_id']}"
            if project_check in rule:
                return True
        
        # Check user_id match
        if "user_id:" in rule and context.get("user_id"):
            user_check = f"user_id:{context['user_id']}"
            if user_check in rule:
                return True
        
        # Default deny
        return False
    
    def list_roles(self) -> List[Dict[str, Any]]:
        """List all available roles."""
        # Load roles from ConfigMap
        roles = []
        
        # OpenStack roles
        openstack_roles = [
            {"name": "admin", "description": "Full administrative access"},
            {"name": "member", "description": "Standard user access"},
            {"name": "reader", "description": "Read-only access"},
            {"name": "service", "description": "Service account access"},
        ]
        
        # Stack4Things custom roles
        custom_roles = [
            {"name": "device-admin", "description": "Device management administrator"},
            {"name": "fleet-manager", "description": "Fleet management role"},
            {"name": "network-admin", "description": "Network management role"},
            {"name": "plugin-developer", "description": "Plugin development role"},
            {"name": "execution-operator", "description": "Execution management role"},
            {"name": "auditor", "description": "Audit and read-only access"},
        ]
        
        roles.extend(openstack_roles)
        roles.extend(custom_roles)
        
        return roles
    
    def list_policies(self) -> Dict[str, str]:
        """List all policies."""
        return self.policies
    
    def is_ready(self) -> bool:
        """Check if policy engine is ready."""
        return len(self.policies) > 0

