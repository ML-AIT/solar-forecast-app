"""Copy the ML repo files the forecast job uses, or check that the copies are current.

The job's features and models are the ML repo's code, copied unchanged so the job forecasts with what
was evaluated. Run from the repo root after the ML repo changes one of them:

    python -I apps/forecast-job/sync_ml_copies.py --ml-repo <ML repo clone>          # copy
    python -I apps/forecast-job/sync_ml_copies.py --ml-repo <ML repo clone> --check  # exit 1 if stale

Then record the clone's commit in apps/forecast-job/README.md. Files not listed here (forecast_job.py,
run_forecast_job.py, test_forecast_job.py) belong to this repo and are not copies.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

JOB_DIR = Path(__file__).resolve().parent

# Paths are the same in the ML repo and under apps/forecast-job/.
COPIES = [
    "ml/configs/plants.yaml",
    *(
        f"ml/src/solar/{name}.py"
        for name in (
            "__init__",
            "issue_time",
            "nwp",
            "nwp_features",
            "plants",
            "pvlib_baseline",
            "solar_geometry",
            "weather_only",
        )
    ),
    # Tests only: test_issue_time.py checks the job's features against the notebooks' builder.
    "ml/src/S01/__init__.py",
    "ml/src/S01/data_quality.py",
    "ml/tests/conftest.py",
    *(
        f"ml/tests/test_{name}.py"
        for name in ("issue_time", "nwp", "nwp_features", "pvlib_baseline", "weather_only")
    ),
]


def stale(ml_repo: Path) -> list[str]:
    """Copies that are missing or differ from the ML repo."""
    return [
        rel
        for rel in COPIES
        if not (JOB_DIR / rel).exists()
        or (JOB_DIR / rel).read_bytes() != (ml_repo / rel).read_bytes()
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ml-repo", type=Path, required=True, help="local clone of the ML repo")
    parser.add_argument("--check", action="store_true", help="only check that copies are current")
    args = parser.parse_args()
    missing = [rel for rel in COPIES if not (args.ml_repo / rel).is_file()]
    if missing:
        print("not in the ML repo:", *missing, sep="\n  ")
        return 1
    if not args.check:
        for rel in stale(args.ml_repo):
            (JOB_DIR / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(args.ml_repo / rel, JOB_DIR / rel)
            print("copied", rel)
    commit = (
        subprocess.run(
            ["git", "-C", str(args.ml_repo), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        or "unknown"
    )
    left = stale(args.ml_repo)
    for rel in left:
        print("stale:", rel)
    print(f"ML repo commit {commit}: {len(COPIES) - len(left)}/{len(COPIES)} copies current")
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
