"""Check the forecast job against the proposal's prototype-operation criteria (§1.3).

Two sources, one report:
    replay   runs this folder's Docker image once per past target day with --date, S01 and S02,
             and checks every file: 96 finite values in 15-min order, P10 <= P50 <= P90, issue time,
             model version and mode present. Counts modes and failures and times each run.
    live     reads the scheduled Azure runs since the replay window from the job's log lines in
             Log Analytics (read only; needs `az login`).
    summary  writes README.md in --out from the two CSVs.

A past --date is honest: the job keeps, for each slot, only the weather run available before the
issue cutoff, so it gets the weather it would have had that night. Only `issued_at` differs (it is
the run time), so publication time comes from the live runs.

Usage (from the repo root; stdlib only, so any Python 3.12 works):
    python apps/forecast-job/ml/scripts/replay_forecast_job.py --models <model folder>
    python apps/forecast-job/ml/scripts/replay_forecast_job.py live summary   # add live nights

The replay's forecast files go to a temporary folder and are deleted afterwards: they are model
output and stay out of git. Only the per-day CSVs and README.md (no power values) go in --out.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

JOB_DIR = Path(__file__).resolve().parents[2]  # apps/forecast-job
DEFAULT_OUT = JOB_DIR.parents[1] / "docs" / "operation-replay"
IMAGE = "solar-forecast-job:replay"
PLANTS = ("S01", "S02")
SLOTS = 96
TARGET_SECONDS = 300
MODES = ("primary", "cached_weather", "climatology")
BANGKOK = timezone(timedelta(hours=7))


# ------------------------------------------------------------------ file check ------------------
def check_forecast(payload: dict, plant_id: str, day: date) -> list[str]:
    """Problems with one forecast file against §1.3; empty means complete."""
    problems = [f"missing {key}" for key in ("issued_at", "model_version", "forecast_mode")
                if not payload.get(key)]
    if payload.get("plant_id") != plant_id or payload.get("date") != f"{day:%Y-%m-%d}":
        problems.append("wrong plant or date")
    points = payload.get("points") or []
    if len(points) != SLOTS:
        return problems + [f"{len(points)} slots, not {SLOTS}"]
    start = datetime(day.year, day.month, day.day, tzinfo=BANGKOK)
    for i, point in enumerate(points):
        if datetime.fromisoformat(point["timestamp"]) != start + timedelta(minutes=15 * i):
            problems.append(f"slot {i} out of 15-min order")
            break
    values = [(p.get("p10"), p.get("p50"), p.get("p90")) for p in points]
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for trio in values for v in trio):
        problems.append("non-finite value")
    elif not all(p10 <= p50 <= p90 for p10, p50, p90 in values):
        problems.append("P10 <= P50 <= P90 broken")
    return problems


# ------------------------------------------------------------------ helpers ---------------------
def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def az_json(args: list[str]):
    proc = run(["az", *args, "-o", "json"])
    if proc.returncode:
        sys.exit(f"az {' '.join(args[:4])} failed:\n{proc.stderr}")
    return json.loads(proc.stdout)


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["empty"])
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def days(first: date, last: date):
    while first <= last:
        yield first
        first += timedelta(days=1)


# ------------------------------------------------------------------ replay ----------------------
def replay(args: argparse.Namespace) -> None:
    if not args.models:
        sys.exit("replay needs --models (or SOLAR_MODEL_DIR): the folder with the model files")
    models = Path(args.models).resolve()
    build = run(["docker", "build", "-q", "-t", IMAGE, str(JOB_DIR)])
    if build.returncode:
        sys.exit(f"docker build failed:\n{build.stderr}")
    commit = run(["git", "-C", str(JOB_DIR), "describe", "--always", "--dirty"]).stdout.strip()
    rows = []
    with tempfile.TemporaryDirectory() as tmp:  # forecasts and weather cache; never the live share
        for day in days(args.first, args.last):
            started = time.monotonic()
            # --force: a rerun of the replay redoes the day instead of keeping an earlier file.
            proc = run(["docker", "run", "--rm", "-v", f"{models}:/models:ro",
                        "-v", f"{tmp}:/forecasts", IMAGE,
                        "python", "ml/scripts/run_forecast_job.py", "--date", f"{day}", "--force"])
            wall = round(time.monotonic() - started, 1)
            logged = {}
            for line in proc.stdout.splitlines():
                try:
                    entry = json.loads(line)
                    logged[entry["plant_id"]] = entry
                except (ValueError, KeyError, TypeError):
                    pass
            for plant_id in PLANTS:
                entry = logged.get(plant_id, {})
                try:
                    path = Path(tmp) / plant_id / f"{day}.json"
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    problems = check_forecast(payload, plant_id, day)
                except (OSError, ValueError) as err:
                    payload, problems = {}, [f"no readable file: {type(err).__name__}"]
                stderr_tail = (proc.stderr.strip().splitlines() or [""])[-1]
                rows.append({
                    "date": f"{day}", "plant_id": plant_id, "exit_code": proc.returncode,
                    "action": entry.get("action", ""),
                    "forecast_mode": payload.get("forecast_mode") or entry.get("forecast_mode")
                    or "",
                    "model_version": payload.get("model_version", ""),
                    "complete": not problems, "problems": "; ".join(problems),
                    "reason": entry.get("reason") or stderr_tail,
                    "plant_seconds": entry.get("seconds", ""), "run_seconds": wall,
                    "image_commit": commit})
            done = [(r["forecast_mode"] or "no file", r["complete"]) for r in rows[-len(PLANTS):]]
            print(f"{day}: exit {proc.returncode}, {wall} s, {done}", flush=True)
    write_csv(args.out / "replay_runs.csv", rows)


# ------------------------------------------------------------------ live ------------------------
def live(args: argparse.Namespace) -> None:
    job = az_json(["containerapp", "job", "show", "-n", args.job, "-g", args.resource_group])
    minute, hour = job["properties"]["configuration"]["scheduleTriggerConfig"][
        "cronExpression"].split()[:2]
    cron_start = f"{int(hour):02d}:{int(minute):02d}"  # Azure reads cron in UTC
    # The run on the replay's last day writes the first target day after the replay window.
    live_from = f"{args.last}T{cron_start}"
    executions = az_json(["containerapp", "job", "execution", "list",
                          "-n", args.job, "-g", args.resource_group])
    scheduled = {e["name"]: e["properties"] for e in executions  # other starts are manual runs
                 if e["properties"]["startTime"][:16] >= live_from
                 and e["properties"]["startTime"][11:16] == cron_start}
    env = az_json(["containerapp", "env", "show", "--ids", job["properties"]["environmentId"]])
    workspace = env["properties"]["appLogsConfiguration"]["logAnalyticsConfiguration"][
        "customerId"]
    query = (f"ContainerAppConsoleLogs_CL | where ContainerJobName_s == '{args.job}' "
             f"and TimeGenerated >= datetime({live_from}:00Z) "
             "| project ContainerGroupName_s, Log_s")
    logs = az_json(["monitor", "log-analytics", "query", "-w", workspace,
                    "--analytics-query", query])
    rows = []
    for name, props in sorted(scheduled.items(), key=lambda kv: kv[1]["startTime"]):
        start = datetime.fromisoformat(props["startTime"]).astimezone(BANGKOK)
        end = (datetime.fromisoformat(props["endTime"]).astimezone(BANGKOK)
               if props.get("endTime") else None)
        entries = []
        for log in logs:
            if log["ContainerGroupName_s"].startswith(name + "-"):
                try:
                    entries.append(json.loads(log["Log_s"]))
                except ValueError:
                    pass
        base = {"execution": name, "status": props["status"],
                "started_bangkok": f"{start:%Y-%m-%d %H:%M:%S}",
                "finished_bangkok": f"{end:%Y-%m-%d %H:%M:%S}" if end else "",
                "run_seconds": round((end - start).total_seconds()) if end else ""}
        fields = ("plant_id", "date", "scenario", "action", "forecast_mode", "model_version")
        if not entries:
            rows.append({**base, **dict.fromkeys(fields, ""), "plant_seconds": "",
                         "reason": "no log lines"})
        for e in sorted(entries, key=lambda e: (e.get("date", ""), e.get("plant_id", ""))):
            rows.append({**base, **{k: e.get(k, "") for k in fields},
                         "plant_seconds": e.get("seconds", ""), "reason": e.get("reason", "")})
    write_csv(args.out / "live_runs.csv", rows)
    print(f"{len(scheduled)} scheduled runs since {live_from} UTC, {len(rows)} rows", flush=True)


# ------------------------------------------------------------------ summary ---------------------
def replay_section(rep: list[dict]) -> list[str]:
    days_ = sorted({r["date"] for r in rep})
    ok = [r for r in rep if r["complete"] == "True"]
    modes = Counter(r["forecast_mode"] for r in ok)
    walls = [float(s) for _, s in sorted({(r["date"], r["run_seconds"]) for r in rep})]
    both = sum(all(r["complete"] == "True" for r in rep if r["date"] == d) for d in days_)
    plants = ", ".join(sorted({r["plant_id"] for r in rep}))
    versions = ", ".join(sorted({r["model_version"] for r in rep if r["model_version"]}))
    lines = [
        f"## Replay: {days_[0]} to {days_[-1]} ({len(days_)} target days, {plants})", "",
        "| Criterion | Result | Target |", "| --- | --- | --- |",
        (f"| Complete files (96 finite values in 15-min order, P10 <= P50 <= P90, issue time, "
        f"model version, mode) | {len(ok)} / {len(rep)} ({100 * len(ok) / len(rep):.0f} %) "
        "| 100 % |"),
        f"| Days with every plant complete | {both} / {len(days_)} | all |",
        *[f"| `{m}` | {modes.get(m, 0)} | counted |" for m in MODES],
        f"| Failed (no complete file) | {len(rep) - len(ok)} | counted |",
        (f"| Run time per day, all plants, container start to exit | median "
        f"{statistics.median(walls):.0f} s, max {max(walls):.0f} s | under {TARGET_SECONDS} s |"),
        "",
        (f"Image built from commit `{rep[0]['image_commit']}`; models {versions}. Each day is the "
        "final forecast (`d1_2355`). Per-day rows: `replay_runs.csv`."), ""]
    odd = [r for r in rep if r["complete"] != "True" or r["forecast_mode"] != "primary"]
    if odd:
        lines += ["Not complete or not `primary`:", "",
                  *[f"- {r['date']} {r['plant_id']}: {r['forecast_mode'] or 'no file'}; "
                    f"{r['problems'] or r['reason']}" for r in odd], ""]
    return lines


def live_section(liv: list[dict]) -> list[str]:
    runs: dict[str, list[dict]] = {}
    for r in liv:
        runs.setdefault(r["execution"], []).append(r)
    lines = ["## Live scheduled runs on Azure", "",
             ("| Started (Bangkok) | Finished | Status | Run time | Files | Modes "
             "| Before target day |"), "| --- | --- | --- | --- | --- | --- | --- |"]
    on_time = 0
    for rows in runs.values():
        r0 = rows[0]
        files = [r for r in rows if r["plant_id"]]
        actions = Counter(r["action"] for r in files)
        modes = Counter(r["forecast_mode"] for r in files)
        finals = [r["date"] for r in files if r["scenario"] == "d1_2355"]
        # Published on D-1: the run finished before the final forecast's target day began.
        ok = bool(r0["finished_bangkok"] and finals
                  and all(r0["finished_bangkok"][:10] < d for d in finals))
        on_time += ok
        lines.append(
            f"| {r0['started_bangkok'][:16]} | {r0['finished_bangkok'][11:]} | {r0['status']} "
            f"| {r0['run_seconds']} s "
            f"| {', '.join(f'{n} {a}' for a, n in sorted(actions.items())) or 'none'} "
            f"| {', '.join(f'{n} {m}' for m, n in sorted(modes.items())) or 'none'} "
            f"| {'yes' if ok else 'no'} |")
    seconds = [int(r["run_seconds"]) for r in liv if r["run_seconds"]]
    lines += ["", (f"Scheduled runs: {len(runs)}; succeeded: "
              f"{sum(rows[0]['status'] == 'Succeeded' for rows in runs.values())}; "
              f"published before the target day: {on_time}; longest run: "
              f"{max(seconds, default=0)} s. Each run writes tomorrow's final forecast "
              "(`d1_2355`) and the early version for the day after (`d2_2355`). "
              "Per-file rows: `live_runs.csv`."), ""]
    return lines


def summary(args: argparse.Namespace) -> None:
    rep, liv = read_csv(args.out / "replay_runs.csv"), read_csv(args.out / "live_runs.csv")
    lines = ["# Forecast job: operation check", "",
             ("The Phase 1 proposal's prototype-operation and timeliness criteria (§1.3), "
              "measured on a replay of past days and on the live nightly runs. The proposal "
              "asked for four plants; the final scope is S01 and S02 (ML repo "
              "`docs/decisions/0005-final-scope-s01-s02.md`), so both parts cover those two. "
              "Made by `apps/forecast-job/ml/scripts/replay_forecast_job.py`; see its docstring "
              "for how it works and how to rerun it."), ""]
    if rep:
        lines += replay_section(rep)
    if liv:
        lines += live_section(liv)
    (args.out / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    steps = {"replay": replay, "live": live, "summary": summary}
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("steps", nargs="*", default=list(steps),
                        help=f"any of {list(steps)} (default: all)")
    parser.add_argument("--models", default=os.environ.get("SOLAR_MODEL_DIR"),
                        help="model files folder (default: $SOLAR_MODEL_DIR)")
    parser.add_argument("--first", type=date.fromisoformat, default=date(2026, 10, 10),
                        help="first replay target day")
    parser.add_argument("--last", type=date.fromisoformat, default=date(2026, 11, 8),
                        help="last replay target day; live runs start the night before the next")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--resource-group", default="rg-solar-forecast")
    parser.add_argument("--job", default="solar-forecast-daily")
    args = parser.parse_args()
    if unknown := set(args.steps) - set(steps):
        parser.error(f"unknown steps {sorted(unknown)}; choose from {list(steps)}")
    args.out.mkdir(parents=True, exist_ok=True)
    for name in args.steps:
        steps[name](args)


if __name__ == "__main__":
    main()
