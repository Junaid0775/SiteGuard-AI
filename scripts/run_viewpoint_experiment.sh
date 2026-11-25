#!/bin/zsh
# Runs the full viewpoint generalisation experiment (see docs/EVALUATION.md).
# Usage (from SiteGuard-AI/):  zsh scripts/run_viewpoint_experiment.sh
#   SKIP_TRAINING=1 zsh scripts/run_viewpoint_experiment.sh   # reuse an existing frontal-only model
set -e
cd "$(dirname "$0")/.."
PY=.venv/bin/python
$PY -m src.evaluation.viewpoint_evaluation prepare
if [ -z "$SKIP_TRAINING" ]; then
  $PY -m src.training.train --data data/generated/viewpoint/frontal_train.yaml --name viewpoint_frontal_only --no-promote
fi
RUN=$(ls -dt experiments/viewpoint_frontal_only* | head -1)
# 1) Frontal-only model: every held-out group (side/overhead/low-angle images were never trained on).
$PY -m src.evaluation.viewpoint_evaluation evaluate --weights "$RUN/weights/best.pt" --name viewpoint_frontal_only \
    --description "Frontal-only model (527 frontal train images). Side/overhead/low-angle images never seen in training."
# 2) Main app model (trained on all 800 train images, all viewpoints): official val-split groups only.
$PY -m src.evaluation.viewpoint_evaluation evaluate --weights models/trained/best.pt --name main_model_all_views --val-only \
    --description "Main application model (all 800 train images, mixed viewpoints). Evaluated on val-split groups only."
