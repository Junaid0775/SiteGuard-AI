"""Dataset path resolution, class mapping and annotation parsing."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from src.utils.dataset_tools import (
    LabelFormatError,
    build_mirror,
    parse_label_file,
    parse_label_line,
    prepare_default_dataset,
    validate_dataset,
)
from src.utils.paths import PROJECT_ROOT, class_names, mirror_dataset_dir, source_dataset_dir

EXPECTED_CLASSES = {
    0: "helmet", 1: "gloves", 2: "vest", 3: "boots", 4: "goggles", 5: "Person",
    6: "no_helmet", 7: "no_goggle", 8: "no_gloves", 9: "no_boots", 10: "forklift", 11: "no_vest",
}


def test_dataset_path_resolves_from_any_cwd(dataset_root, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # a different working directory must not matter
    root = source_dataset_dir()
    assert root.is_absolute()
    assert root == dataset_root
    assert (root / "images" / "train").is_dir()
    assert (root / "labels" / "val").is_dir()


def test_class_mapping_matches_original_data_yaml(dataset_root):
    original = yaml.safe_load((dataset_root / "data.yaml").read_text())
    original_names = {int(k): v for k, v in original["names"].items()}
    assert original_names == EXPECTED_CLASSES
    assert class_names() == EXPECTED_CLASSES


def test_resolved_yaml_uses_absolute_existing_paths(dataset_root):
    yaml_path = prepare_default_dataset()
    data = yaml.safe_load(yaml_path.read_text())
    root = Path(data["path"])
    assert root.is_absolute() and root.exists()
    assert (root / data["train"]).is_dir()
    assert (root / data["val"]).is_dir()
    assert {int(k): v for k, v in data["names"].items()} == EXPECTED_CLASSES


def test_mirror_links_point_to_original_files(dataset_root):
    mirror = build_mirror()
    assert mirror == mirror_dataset_dir()
    assert str(mirror).startswith(str(PROJECT_ROOT))
    links = list((mirror / "images" / "val").iterdir())
    assert len(links) == 200
    sample = links[0]
    assert sample.is_symlink()
    assert Path(os.readlink(sample)).parent == dataset_root / "images" / "val"


def test_parse_valid_label_line():
    row = parse_label_line("6 0.5 0.25 0.1 0.2")
    assert row.class_id == 6 and row.x_center == 0.5 and row.height == 0.2


@pytest.mark.parametrize(
    "line",
    ["6 0.5 0.25 0.1", "12 0.5 0.5 0.1 0.1", "-1 0.5 0.5 0.1 0.1", "3 1.5 0.5 0.1 0.1", "a 0.5 0.5 0.1 0.1", "2 0.5 0.5 0 0.1"],
)
def test_parse_invalid_label_lines(line):
    with pytest.raises(LabelFormatError):
        parse_label_line(line)


def test_parse_label_file_skips_blank_lines(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("0 0.5 0.5 0.2 0.2\n\n5 0.4 0.4 0.3 0.6\n")
    rows = parse_label_file(f)
    assert [r.class_id for r in rows] == [0, 5]


def test_full_dataset_validation(dataset_root):
    report = validate_dataset(check_images=False)
    assert report.ok, report.to_dict()
    assert report.split_counts == {"train": {"images": 800, "labels": 800}, "val": {"images": 200, "labels": 200}}
    assert report.total_annotations == 14863
    assert report.duplicate_images == []
    present = set(report.class_counts["train"]) | set(report.class_counts["val"])
    assert present == set(range(12))
