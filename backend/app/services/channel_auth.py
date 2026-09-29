"""Compatibility imports for channel authentication and upstream URL helpers."""
from app.services.provider_adapters import (
    build_auth_headers,
    get_upstream_protocol_url,
    get_upstream_url,
)

__all__ = ["build_auth_headers", "get_upstream_protocol_url", "get_upstream_url"]
