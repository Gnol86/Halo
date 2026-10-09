"""Validate a Halo release before allowing GitHub to publish its tag."""

import argparse
import json
import re
import tomllib
from pathlib import Path

RELEASE_TAG = re.compile(
    r"v(?P<version>(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?P<prerelease>(?:a|b|rc)(?:0|[1-9]\d*))?)"
)


def validate_release(root: Path, tag: str) -> dict[str, str]:
    """Require a canonical tag, matching source versions and reviewed notes."""
    match = RELEASE_TAG.fullmatch(tag)
    if not match:
        raise ValueError("Use vX.Y.Z, optionally followed by aN, bN or rcN")
    version = match["version"]
    manifest = json.loads((root / "custom_components/halo/manifest.json").read_text())
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    lock = tomllib.loads((root / "uv.lock").read_text())
    locked_project = next(
        package for package in lock["package"] if package["name"] == project["name"]
    )
    if any(
        source["version"] != version for source in (manifest, project, locked_project)
    ):
        raise ValueError("Tag, manifest.json, pyproject.toml and uv.lock must agree")
    notes = root / "releases" / f"{version}.md"
    if not notes.is_file() or not notes.read_text().strip():
        raise ValueError(f"Missing release notes: releases/{version}.md")
    return {"version": version, "prerelease": str(bool(match["prerelease"])).lower()}


def main() -> None:
    """Emit only validated values for the workflow's publication job."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    result = validate_release(Path(__file__).resolve().parents[1], args.tag)
    output = "".join(f"{key}={value}\n" for key, value in result.items())
    if args.github_output:
        with args.github_output.open("a") as file:
            file.write(output)
    print(output, end="")


if __name__ == "__main__":
    main()
