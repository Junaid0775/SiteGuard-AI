"""Experiment overrides for the training entry point (accuracy programme, Phase 3/4).

The default behaviour must be unchanged when no override file is given, protected arguments must never be
overridable, and unknown arguments must be rejected instead of being silently ignored.
"""

import sys

import pytest

from src.training import train


def test_no_override_file_means_no_change():
    assert train.load_hyp_overrides(None) == {}


def test_overrides_are_read(tmp_path):
    f = tmp_path / "hyp.yaml"
    f.write_text("scale: 0.25\ncls_pw: 0.5\nmosaic: 1.0\n")
    assert train.load_hyp_overrides(f) == {"scale": 0.25, "cls_pw": 0.5, "mosaic": 1.0}


@pytest.mark.parametrize("key", ["data", "project", "name", "exist_ok", "resume", "model", "pretrained"])
def test_protected_keys_are_rejected(tmp_path, key):
    f = tmp_path / "hyp.yaml"
    f.write_text(f"{key}: x\n")
    with pytest.raises(SystemExit):
        train.load_hyp_overrides(f)


def test_unknown_keys_are_rejected(tmp_path):
    f = tmp_path / "hyp.yaml"
    f.write_text("not_an_ultralytics_arg: 1\n")
    with pytest.raises(SystemExit):
        train.load_hyp_overrides(f)


def test_missing_file_is_rejected(tmp_path):
    with pytest.raises(SystemExit):
        train.load_hyp_overrides(tmp_path / "missing.yaml")


def test_seed_and_hyp_defaults(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["train"])
    args = train.parse_args()
    assert args.seed == 42 and args.hyp is None and args.no_promote is False
