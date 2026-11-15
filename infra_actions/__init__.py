"""Discover action modules and register their execution handlers."""

from collections.abc import Callable
from importlib import import_module
from pkgutil import iter_modules
from typing import Any

Action = Callable[[dict[str, Any]], dict[str, Any]]
_HANDLERS: dict[str, Action] = {}


def register(name: str) -> Callable[[Action], Action]:
    """Register a handler under its manifest action name."""

    def decorator(handler: Action) -> Action:
        if name in _HANDLERS:
            raise ValueError(f"Action already registered: {name}")
        _HANDLERS[name] = handler
        return handler

    return decorator


def get_action(name: str) -> Action:
    """Discover packaged modules and return the requested action handler."""
    for module in iter_modules(__path__):
        import_module(f"{__name__}.{module.name}")
    try:
        return _HANDLERS[name]
    except KeyError as error:
        raise ValueError(
            f"Unsupported action: {name}. Available: {', '.join(sorted(_HANDLERS))}"
        ) from error
