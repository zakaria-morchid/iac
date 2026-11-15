"""AWX job template actions."""

import json
from typing import Any
from urllib.parse import urlencode

from infra_actions import register
from infra_actions.http import api, required_env


@register("awx:job-template:launch")
def launch_job_template(inputs: dict[str, Any]) -> dict[str, Any]:
    """Resolve AWX resources, launch a template, and expose its job ID."""
    base = required_env("AWX_URL")
    token = required_env("AWX_TOKEN")

    def resource_id(collection: str, value: Any) -> int:
        if isinstance(value, int) or str(value).isdigit():
            return int(value)
        query = urlencode({"name": value})
        result = api(base, f"/api/v2/{collection}/?{query}", token)
        if result["count"] != 1:
            raise ValueError(f"Expected one {collection} named {value!r}")
        return result["results"][0]["id"]

    template = resource_id("job_templates", inputs["job_template"])
    result = api(
        base,
        f"/api/v2/job_templates/{template}/launch/",
        token,
        {
            "inventory": resource_id("inventories", inputs["inventory"]),
            "extra_vars": json.dumps(inputs.get("extra_vars", {})),
        },
    )
    if result.get("ignored_fields"):
        raise RuntimeError("AWX ignored launch fields. Check Prompt on Launch settings.")
    return {"job_id": result["id"]}
