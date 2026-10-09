"""Publication must fail before a mismatched or incomplete version is released."""

import json

import pytest
from awesomeversion import AwesomeVersion

from scripts.release_metadata import validate_release


def release_tree(root, version="0.1.0"):
    integration = root / "custom_components/halo"
    integration.mkdir(parents=True)
    (integration / "manifest.json").write_text(json.dumps({"version": version}))
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "halo-homeassistant"\nversion = "{version}"\n'
    )
    (root / "uv.lock").write_text(
        f'[[package]]\nname = "halo-homeassistant"\nversion = "{version}"\n'
    )
    notes = root / "releases" / f"{version}.md"
    notes.parent.mkdir()
    notes.write_text("Release notes reviewed for this version.\n")
    return notes


@pytest.mark.parametrize("version", ["0.1.0", "1.0.0a1", "1.0.0b2", "1.0.0rc1"])
def test_valid_release_and_hacs_prerelease_classification(tmp_path, version):
    release_tree(tmp_path, version)
    result = validate_release(tmp_path, f"v{version}")
    assert result["version"] == version
    parsed = AwesomeVersion(version)
    prerelease = parsed.alpha or parsed.beta or parsed.release_candidate
    assert result["prerelease"] == str(prerelease).lower()


@pytest.mark.parametrize(
    "tag", ["main", "0.1.0", "v0.1", "v01.1.0", "v0.1.0.dev0", "v0.1.0\nx=y"]
)
def test_invalid_tag_is_rejected(tmp_path, tag):
    with pytest.raises(ValueError, match="Use vX.Y.Z"):
        validate_release(tmp_path, tag)


@pytest.mark.parametrize(
    "path", ["custom_components/halo/manifest.json", "pyproject.toml", "uv.lock"]
)
def test_version_mismatch_stops_publication(tmp_path, path):
    release_tree(tmp_path)
    source = tmp_path / path
    source.write_text(source.read_text().replace("0.1.0", "0.1.1"))
    with pytest.raises(ValueError, match="must agree"):
        validate_release(tmp_path, "v0.1.0")


@pytest.mark.parametrize("content", [None, " \n"])
def test_missing_or_empty_notes_stop_publication(tmp_path, content):
    notes = release_tree(tmp_path)
    if content is None:
        notes.unlink()
    else:
        notes.write_text(content)
    with pytest.raises(ValueError, match="Missing release notes"):
        validate_release(tmp_path, "v0.1.0")
