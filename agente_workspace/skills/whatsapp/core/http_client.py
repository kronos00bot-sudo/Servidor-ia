"""Compatibility layer for legacy imports.

Prefer importing HttpClient from skills.whatsapp.utils.http_client.
"""

from skills.whatsapp.utils.http_client import HttpClient

__all__ = ["HttpClient"]
