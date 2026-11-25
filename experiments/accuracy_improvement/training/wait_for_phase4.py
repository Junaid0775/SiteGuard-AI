"""Exit when the Phase 4 queue has finished, stopped, failed, or its runner is gone (notification helper only)."""
import json, subprocess, time
from pathlib import Path
P = Path("experiments/accuracy_improvement/training/matrix_status.json")
NAMES = ["E1_m640_base", "E3_m896", "E6_m640_tiles", "E4_m640_aug", "E5_m640_clspw", "E2_m640_long"]
BAD = {"training_failed", "evaluation_failed", "stopped_memory_pressure", "paused_low_battery", "stopped_thermal_critical",
       "LOCKED_TEST_VIOLATION", "waiting_for_mains_power"}
time.sleep(120)
while True:
    st = json.loads(P.read_text()) if P.exists() else {}
    states = {n: st.get(n, {}).get("state") for n in NAMES}
    if all(s == "done" for s in states.values()):
        print("ALL_DONE", states); break
    if any(s in BAD for s in states.values()):
        print("STOPPED", states); break
    if subprocess.run(["pgrep", "-f", "run_matrix.py"], capture_output=True).returncode != 0:
        print("RUNNER_EXITED", states); break
    time.sleep(600)
