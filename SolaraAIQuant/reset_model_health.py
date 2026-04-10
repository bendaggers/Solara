"""
Reset auto-disabled model health records so SAQ will run them again.

Usage:
    python reset_model_health.py                 # shows current health
    python reset_model_health.py --reset-all     # resets all auto-disabled
    python reset_model_health.py "Pull Back Entry Long"
    python reset_model_health.py "TI V2 Long" "TI V2 Short"
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from state.database import db_manager
from engine.model_health import model_health_tracker


def show_health():
    reports = model_health_tracker.get_all_health_reports()
    if not reports:
        print("No model health records found.")
        return
    print(f"\n{'Model':<30} {'Status':<12} {'Runs':>5} {'Fails':>6} {'Consec':>7}")
    print("-" * 65)
    for name, r in sorted(reports.items()):
        status = "AUTO-DISABLED" if r.status.value == "DISABLED" else r.status.value
        print(f"{name:<30} {status:<12} {r.total_runs:>5} {r.total_failures:>6} {r.consecutive_failures:>7}")


def reset(name: str):
    model_health_tracker.reset_model_health(name)
    print(f"  ✔  Reset: {name}")


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        show_health()
        sys.exit(0)

    if "--reset-all" in args:
        reports = model_health_tracker.get_all_health_reports()
        disabled = [n for n, r in reports.items() if r.status.value == "DISABLED"]
        if not disabled:
            print("No auto-disabled models found.")
        else:
            for name in disabled:
                reset(name)
        sys.exit(0)

    for name in args:
        reset(name)
