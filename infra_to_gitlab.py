"""Convert infra.yml to GitLab CI, or execute one of its steps."""

import json
import os
import re
import shlex
from pathlib import Path
from typing import Any

import click
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from infra_actions import get_action

EXPRESSION = re.compile(r"\$?\{\{\s*([^{}]*?)\s*\}\}")
OUTPUT_DIR = Path(".infra-outputs")


class Step(BaseModel):
    """Describe an executable step while keeping its inputs unrestricted."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    name: str | None = Field(default=None, min_length=1)
    action: str = Field(min_length=1)
    manual: bool = False
    allow_failure: bool = False
    enabled: bool = True
    inputs: dict[str, Any] = Field(default_factory=dict)

    @field_validator("action")
    @classmethod
    def registered_action(cls, action: str) -> str:
        """Require an action provided by a discovered handler."""
        get_action(action)
        return action


class Manifest(BaseModel):
    """Validate global variables and the ordered list of steps."""

    model_config = ConfigDict(extra="forbid", strict=True)

    global_vars: dict[str, Any] = Field(default_factory=dict, alias="global")
    steps: list[Step] = Field(min_length=1)

    @field_validator("steps")
    @classmethod
    def unique_step_ids(cls, steps: list["Step"]) -> list["Step"]:
        """Reject duplicate IDs used by jobs and output references."""
        ids = [step.id for step in steps]
        if len(ids) != len(set(ids)):
            raise ValueError("Step IDs must be unique")
        return steps


def resolve(value: Any, context: dict[str, Any]) -> Any:
    """Resolve global and environment variables and step outputs in nested inputs."""

    def lookup(expression: str) -> Any:
        if expression.startswith("env."):
            name = expression[4:]
            if name not in os.environ:
                raise ValueError(
                    f"Missing environment variable {name}. Set it before running this step."
                )
            return os.environ[name]
        if expression.startswith("global."):
            return context["global"][expression[7:]]
        match = re.fullmatch(r"steps\.(.+)\.outputs\.([\w_]+)", expression)
        if match:
            step_id, key = match.groups()
            if step_id not in context["steps"]:
                raise ValueError(
                    f"Missing outputs for step '{step_id}'. Run that step successfully first "
                    "from the same working directory "
                    f"(expected {OUTPUT_DIR / (step_id + '.json')})."
                )
            if key not in context["steps"][step_id]:
                raise ValueError(f"Step '{step_id}' has no output named '{key}'")
            return context["steps"][step_id][key]
        raise ValueError(f"Unsupported expression: {expression}")

    if isinstance(value, dict):
        return {key: resolve(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve(item, context) for item in value]
    if isinstance(value, str):
        match = EXPRESSION.fullmatch(value)
        if match:
            return lookup(match.group(1))
        return EXPRESSION.sub(lambda match: str(lookup(match.group(1))), value)
    return value


def run_step(
    document: dict[str, Any], step: dict[str, Any], *, dry_run: bool = False
) -> dict[str, Any]:
    """Resolve inputs, then preview the action or execute it and save outputs."""
    if not step.get("enabled", True):
        raise ValueError(f"Step is disabled: {step['id']}")
    outputs = {}
    for path in OUTPUT_DIR.glob("*.json"):
        outputs[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    inputs = resolve(
        step.get("inputs", {}),
        {
            "global": document.get("global", {}),
            "steps": outputs,
        },
    )
    if dry_run:
        return {
            "id": step["id"],
            "stage": step.get("name") or step["id"],
            "action": step["action"],
            "inputs": inputs,
        }
    output = get_action(step["action"])(inputs)
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / f"{step['id']}.json").write_text(json.dumps(output), encoding="utf-8")
    return output


def convert(document: Any, source: str, *, dry_run: bool = False) -> dict[str, Any]:
    """Validate a manifest and build the corresponding GitLab CI jobs."""
    document = Manifest.model_validate(document).model_dump(by_alias=True)
    steps = document["steps"]
    stage_names = [step["name"] or step["id"] for step in steps]

    pipeline: dict[str, Any] = {
        "stages": list(dict.fromkeys(stage_names)),
        "default": {
            "image": "python:3.12-slim",
            "before_script": ["python -m pip install --disable-pip-version-check ."],
        },
    }
    for step, stage_name in zip(steps, stage_names):
        command = f"infra run {shlex.quote(source)} --step {step['id']}"
        if dry_run:
            command += " --dry-run"
        pipeline[step["id"]] = {
            "stage": stage_name,
            "when": "manual" if step.get("manual", False) else "on_success",
            "allow_failure": step.get("allow_failure", False),
            "script": [command],
            "artifacts": {"paths": [f".infra-outputs/{step['id']}.json"], "expire_in": "1 day"},
        }
        if not step.get("enabled", True):
            pipeline[step["id"]]["rules"] = [{"when": "never"}]
    return pipeline


def load_manifest(source: Path) -> dict[str, Any]:
    """Read and validate a manifest for all CLI commands."""
    try:
        document = yaml.safe_load(source.read_text(encoding="utf-8"))
        return Manifest.model_validate(document).model_dump(by_alias=True)
    except (ValidationError, yaml.YAMLError, OSError) as error:
        raise click.ClickException(f"Invalid manifest:\n{error}") from error


@click.group()
def main() -> None:
    """Validate manifests, generate GitLab CI, and run infrastructure steps."""


@main.command("validate")
@click.argument("source", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def validate_command(source: Path) -> None:
    """Validate SOURCE with Pydantic."""
    load_manifest(source)
    click.echo(f"Valid manifest: {source}")


@main.command("schema")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "yaml", "yml"]),
    default="json",
    show_default=True,
    help="Output format for the manifest schema.",
)
def schema_command(output_format: str) -> None:
    """Print the manifest schema generated by Pydantic."""
    schema = Manifest.model_json_schema(by_alias=True)
    if output_format in {"yaml", "yml"}:
        click.echo(yaml.safe_dump(schema, sort_keys=False, allow_unicode=True), nl=False)
        return
    click.echo(json.dumps(schema, indent=2, ensure_ascii=False))


@main.command("generate")
@click.argument("source", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--output",
    default=".gitlab-ci-generated.yml",
    show_default=True,
    type=click.Path(dir_okay=False, path_type=Path),
)
@click.option("--dry-run", is_flag=True, help="Generate CI jobs that run each step with --dry-run.")
def generate_command(source: Path, output: Path, dry_run: bool) -> None:
    """Generate GitLab CI from SOURCE."""
    pipeline = convert(load_manifest(source), source.as_posix(), dry_run=dry_run)
    generated_yaml = yaml.safe_dump(pipeline, sort_keys=False)
    try:
        output.write_text(generated_yaml, encoding="utf-8")
    except OSError as error:
        raise click.ClickException(f"Cannot write {output}: {error}") from error
    click.echo(f"Generated {output}")


@main.command("run")
@click.argument("source", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--step", "step_id", required=True, help="ID of the step to execute.")
@click.option(
    "--dry-run", is_flag=True, help="Preview resolved inputs without executing or saving outputs."
)
def run_command(source: Path, step_id: str, dry_run: bool) -> None:
    """Run one step from SOURCE.

    Locally, set GITLAB_URL and GITLAB_TOKEN for GitLab actions, or AWX_URL
    and AWX_TOKEN for AWX actions. In CI, CI_API_V4_URL takes precedence.
    Outputs are saved in .infra-outputs/ under the current working directory.
    """
    document = load_manifest(source)
    step = next((step for step in document["steps"] if step["id"] == step_id), None)
    if step is None:
        raise click.ClickException(f"Unknown step: {step_id}")
    try:
        output = run_step(document, step, dry_run=dry_run)
    except (ValueError, RuntimeError, KeyError, OSError) as error:
        raise click.ClickException(f"Step {step_id} failed: {error}") from error
    click.echo(f"Dry run for step {step_id}" if dry_run else f"Step {step_id} completed")
    click.echo(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
