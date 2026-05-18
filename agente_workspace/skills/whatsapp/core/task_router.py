"""Compatibility layer for legacy imports.

Prefer importing TaskRouter from skills.whatsapp.routing.task_router.
"""

from skills.whatsapp.routing.task_router import TaskRouter, RouteTarget

__all__ = ["TaskRouter", "RouteTarget"]
