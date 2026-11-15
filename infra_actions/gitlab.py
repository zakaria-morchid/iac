"""GitLab pipeline actions."""

import os
from typing import Any
from urllib.parse import quote

from infra_actions import register
from infra_actions.http import api, required_env


@register("gitlab:pipeline:trigger")
def trigger_pipeline(inputs: dict[str, Any]) -> dict[str, Any]:
    """Trigger a pipeline and expose the project and pipeline IDs."""
    base = os.environ.get("CI_API_V4_URL")
    if not base:
        base = required_env("GITLAB_URL").rstrip("/") + "/api/v4"
    project = quote(str(inputs["projectId"]), safe="")
    result = api(
        base,
        f"/projects/{project}/pipeline",
        required_env("GITLAB_TOKEN"),
        {
            "ref": inputs.get("branch", "main"),
            "variables": [
                {"key": key, "value": str(value)}
                for key, value in inputs.get("variables", {}).items()
            ],
        },
        gitlab=True,
    )
    return {"project_id": result["project_id"], "pipeline_id": result["id"]}
