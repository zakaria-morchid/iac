"""Shared authenticated HTTP requests and environment settings."""

import json
import os
from typing import Any
from urllib.request import Request, urlopen


def api(
    base: str,
    path: str,
    token: str,
    payload: dict[str, Any] | None = None,
    gitlab: bool = False,
) -> dict[str, Any]:
    """Send an authenticated JSON request and decode its response."""
    headers = {"Content-Type": "application/json"}
    headers.update({"PRIVATE-TOKEN": token} if gitlab else {"Authorization": f"Bearer {token}"})
    data = None if payload is None else json.dumps(payload).encode()
    request = Request(base.rstrip("/") + path, data=data, headers=headers)
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def required_env(name: str) -> str:
    """Read a required setting and explain how to supply missing values."""
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Missing environment variable {name}. Set it before running this step.")
    return value
