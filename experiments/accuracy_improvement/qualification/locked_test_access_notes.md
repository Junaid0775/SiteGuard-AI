# Locked-test access notes

This file explains entries in `locked_test_access_log.csv` that need context. The ledger itself is append-only and is never edited.

## 2026-11-23 03:09:27 and 03:09:28: two failed attempts, no data read, no results

**What happened:** the first Phase 6 runs of `scripts/accuracy/evaluate.py --split test` failed, one for `E3_m896` and one for `E1_m640_base`. Each exited after about 1 second with return code 1:

```
SyntaxError: .../datasets/v1_original_labels/locked_test.yaml 'train:' key missing ❌.
'train' and 'val' are required in all data YAMLs.
```

**What was and was not read:**
- Before the failure, the evaluator had written the ledger row and read the list of test file names (`splits/test.txt`).
- The failure came in Ultralytics' data-YAML check (`check_det_dataset`), before any dataloader was built.
- No test image or label was read, no prediction was made, and no metric was computed or seen.
- The output folders `evaluation/test_E3_m896/` and `evaluation/test_E1_m640_base/` contained nothing except an empty `ultralytics_val/` folder.
- Logs: `qualification/logs/test_E3_m896.log` and `qualification/logs/test_E1_m640_base.log`.

**Cause:**
- `locked_test.yaml` deliberately has no `train:` key, so that it cannot be used for training.
- Ultralytics 8.4.215 requires the key to exist.
- The evaluator's test path had never been exercised: the locked test had 0 accesses by design, and Phase 2 tested only the refusal guard.

**Fix:**
- `split_yaml()` in `scripts/accuracy/evaluate.py` now writes a derived copy, `<out>/_locked_test_eval.yaml`.
- The copy has an **empty** `train:` key, so it contains no images and cannot be used for training.
- `locked_test.yaml` itself is unchanged.
- Pre-change copy: `manifests/evaluate.py.before_phase6_fix`.

**Consequence for the protocol:**
- Nothing was learned about the locked test, so the pre-registered single qualification session simply runs again with the same frozen checkpoints, purposes and settings.
- In the ledger, each model therefore has one failed entry (no data) and one completed entry.
