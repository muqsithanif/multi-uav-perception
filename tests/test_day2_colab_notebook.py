import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = REPO_ROOT / "notebooks" / "day2_visdrone_smoke_colab.ipynb"


def test_day2_colab_notebook_is_valid_and_code_cells_compile() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))

    assert notebook["nbformat"] == 4
    assert notebook["metadata"]["accelerator"] == "GPU"
    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert code_cells
    for index, cell in enumerate(code_cells):
        assert cell["execution_count"] is None
        assert cell["outputs"] == []
        compile("".join(cell["source"]), f"{NOTEBOOK}:cell{index}", "exec")

    source = "\n".join("".join(cell["source"]) for cell in code_cells)
    assert "run_visdrone_smoke_training.py" in source
    assert "GITHUB_TOKEN" in source
    assert "resume_proof" in source
    assert "full fine-tuning" in "".join(notebook["cells"][0]["source"]).lower()
