import copy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schema" / "storyboard.schema.json").read_text())
TEMPLATE = json.loads((ROOT / "storyboard.json").read_text())


def test_template_storyboard_is_valid():
    validate(instance=TEMPLATE, schema=SCHEMA)


def test_missing_required_field_fails():
    broken = copy.deepcopy(TEMPLATE)
    del broken["shots"]
    with pytest.raises(ValidationError):
        validate(instance=broken, schema=SCHEMA)


def test_empty_shots_fails():
    broken = copy.deepcopy(TEMPLATE)
    broken["shots"] = []
    with pytest.raises(ValidationError):
        validate(instance=broken, schema=SCHEMA)


def test_shot_missing_prompt_fails():
    broken = copy.deepcopy(TEMPLATE)
    del broken["shots"][0]["prompt"]
    with pytest.raises(ValidationError):
        validate(instance=broken, schema=SCHEMA)


def test_bad_shot_id_fails():
    broken = copy.deepcopy(TEMPLATE)
    broken["shots"][0]["id"] = "bad id!"
    with pytest.raises(ValidationError):
        validate(instance=broken, schema=SCHEMA)


def test_load_storyboard_validates(monkeypatch, tmp_path):
    from pipeline import utils
    bad = copy.deepcopy(TEMPLATE)
    bad["shots"] = []
    target = tmp_path / "storyboard.json"
    target.write_text(json.dumps(bad))
    monkeypatch.setattr(utils, "STORYBOARD_FILE", target)
    with pytest.raises(ValidationError):
        utils.load_storyboard()
