"""Action de démonstration."""

from typing import Any

from infra_actions import register


@register("example:echo")
def execute(inputs: dict[str, Any]) -> dict[str, Any]:
    """Retourne le message reçu."""
    return {"message": inputs["message"]}
