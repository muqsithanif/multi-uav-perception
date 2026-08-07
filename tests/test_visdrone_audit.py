from pathlib import Path

import cv2
import numpy as np

from scripts.render_visdrone_audit import (
    render_label_overlay,
    select_audit_pairs,
)


def write_image(path: Path, value: int = 255) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.full((80, 100, 3), value, dtype=np.uint8)
    assert cv2.imwrite(str(path), image)


def test_select_audit_pairs_prioritizes_complete_class_coverage(
    tmp_path: Path,
) -> None:
    images = tmp_path / "images"
    labels = tmp_path / "labels"
    for stem, lines in {
        "a": "0 0.5 0.5 0.2 0.2\n",
        "b": "1 0.5 0.5 0.2 0.2\n",
        "c": "0 0.5 0.5 0.2 0.2\n1 0.4 0.4 0.1 0.1\n",
    }.items():
        write_image(images / f"{stem}.jpg")
        labels.mkdir(parents=True, exist_ok=True)
        (labels / f"{stem}.txt").write_text(lines, encoding="utf-8")

    selected = select_audit_pairs(images, labels, class_count=2, sample_count=1)

    assert [image.stem for image, _ in selected] == ["c"]


def test_render_label_overlay_creates_annotated_artifact(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    label = tmp_path / "source.txt"
    output = tmp_path / "audit.jpg"
    write_image(source)
    label.write_text("0 0.5 0.5 0.4 0.25\n", encoding="utf-8")

    artifact = render_label_overlay(source, label, output, ["pedestrian"])

    rendered = cv2.imread(str(output), cv2.IMREAD_COLOR)
    original = cv2.imread(str(source), cv2.IMREAD_COLOR)
    assert rendered is not None
    assert artifact["object_count"] == 1
    assert artifact["class_names"] == ["pedestrian"]
    assert len(artifact["output_sha256"]) == 64
    assert np.any(rendered != original)
