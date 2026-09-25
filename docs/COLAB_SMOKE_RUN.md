# Running the Day 2 smoke training on Google Colab

Status as of 7 August 2026: **Gate 2A passed** through Colab run
`E01S_20260807_001` and the separate resume proof `E01R_20260807_001`. The
accepted run used the full dataset, not the historical subset runner described
below. The actual evidence is in `experiments/E01_20260807_001/smoke_summary.json`,
`resume_summary.json`, and `handoff_receipt.json`; this document itself is not
training evidence.

## Subset workflow prepared in the repository

## Prerequisites

1. Store the two verified official ZIP files in Google Drive:

   ```text
   MyDrive/multi-uav-perception/data/raw/visdrone2019_det/VisDrone2019-DET-train.zip
   MyDrive/multi-uav-perception/data/raw/visdrone2019_det/VisDrone2019-DET-val.zip
   ```

2. In Colab, open **Secrets** and add a `GITHUB_TOKEN` with read/write access to
   the repository (it was private when this run was made, and the notebook
   pushes result artifacts to a branch). Enable secret access for the notebook.
   Never paste the token into a cell or an output.
3. Open the [Day 2 smoke training notebook](https://colab.research.google.com/github/muqsithanif/multi-uav-perception/blob/main/notebooks/day2_visdrone_smoke_colab.ipynb).
4. Select a GPU runtime and use **Run all**. Google still asks for permission to
   mount Drive; that account-security step has to be approved by the account
   owner.

## Checks performed by the notebook

- rejects runtimes without CUDA;
- clones the repository without printing the token;
- verifies the SHA-256 of the train and val ZIP files;
- extracts and validates image/annotation pairs;
- runs the Day 2 test suite;
- builds a deterministic subset of 256 train and 64 val images;
- runs epochs 1–2 and copies the raw checkpoint before the optimizer state is stripped;
- checks the epoch, optimizer, and target epoch stored in the checkpoint;
- loads that checkpoint with `resume=True` and records the epoch it starts from;
- finishes epoch 3 and requires three rows in `results.csv`;
- saves checkpoints and logs to Google Drive;
- saves compact artifacts to `experiments/` and `results/`;
- pushes the artifacts to the branch `colab/day2-S01_20260807_colab_smoke`.

The runner refuses full fine-tuning. The three-epoch metrics are scoped as
`subset_smoke_only` and must not be compared directly with E00, because the
validation subsets differ.

## Pass conditions

Gate 2A can only be marked as passed once the actual artifacts show:

- `status: passed`;
- `resume_proof.status: passed`;
- the epoch 2 checkpoint contains the optimizer state and was actually used to
  start epoch 3;
- `results.csv` contains three epochs;
- `last.pt`, `best.pt`, and the resume checkpoint are stored in Google Drive with
  their actual sizes and SHA-256 digests.
