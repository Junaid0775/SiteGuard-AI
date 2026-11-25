#!/bin/zsh
# Waits (without keeping the Mac awake) until mains power is connected, then runs the Phase 4 matrix under caffeinate.
cd "/Users/junaidahmad/Desktop/471 Project/SiteGuard-AI" || exit 1
LOG=experiments/accuracy_improvement/training/logs/runner_phase4.log
echo "[$(date '+%Y-%m-%dT%H:%M:%S')] watcher started; waiting for AC power" >> $LOG
until pmset -g batt | grep -q "AC Power"; do sleep 60; done
echo "[$(date '+%Y-%m-%dT%H:%M:%S')] AC power detected; starting matrix" >> $LOG
caffeinate -dims .venv/bin/python scripts/accuracy/run_matrix.py experiments/accuracy_improvement/training/matrix_phase4.yaml >> $LOG 2>&1
echo "[$(date '+%Y-%m-%dT%H:%M:%S')] runner exited with $?" >> $LOG
