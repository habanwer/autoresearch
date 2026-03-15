#!/usr/bin/env python3
"""Session automation: run training, parse output, update results.tsv, archive log."""
import csv
import math
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent


def get_current_commit():
    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT)
    return r.stdout.strip()[:8]


def get_commit_description():
    r = subprocess.run(["git", "log", "-1", "--format=%s"], capture_output=True, text=True, cwd=ROOT)
    return r.stdout.strip()


def get_best_val_bpb():
    tsv = ROOT / "results.tsv"
    if not tsv.exists():
        return math.inf
    best = math.inf
    with open(tsv, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            try:
                if row.get("status", "").strip() == "keep":
                    v = float(row.get("val_bpb", "inf"))
                    if v < best:
                        best = v
            except (ValueError, KeyError):
                pass
    return best


def parse_output(log_text):
    """Extract metrics from the '---' summary block in train.py output."""
    metrics = {}
    in_summary = False
    for line in log_text.splitlines():
        if line.strip() == "---":
            in_summary = True
            continue
        if in_summary:
            m = re.match(r"^(\w+):\s+([\d.]+)", line.strip())
            if m:
                metrics[m.group(1)] = float(m.group(2))
    return metrics


def run_training():
    """Run train.py via venv Python, tee output to run.log."""
    python = ROOT / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        python = ROOT / ".venv" / "bin" / "python"

    log_path = ROOT / "run.log"
    print("[session] Starting training... (tail: run.log)")
    sys_flush()
    with open(log_path, "w", encoding="utf-8") as lf:
        proc = subprocess.run(
            [str(python), "train.py"],
            stdout=lf,
            stderr=subprocess.STDOUT,
            cwd=ROOT,
        )
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    return proc.returncode, log_text


def sys_flush():
    import sys
    sys.stdout.flush()


def append_results(commit, val_bpb, memory_gb, status, description):
    tsv = ROOT / "results.tsv"
    val_str = f"{val_bpb:.6f}" if val_bpb > 0 else "N/A"
    mem_str = f"{memory_gb:.1f}" if memory_gb > 0 else "N/A"
    with open(tsv, "a", encoding="utf-8") as f:
        f.write(f"{commit}\t{val_str}\t{mem_str}\t{status}\t{description}\n")


def archive_log(commit):
    sessions_dir = ROOT / "sessions"
    sessions_dir.mkdir(exist_ok=True)
    src = ROOT / "run.log"
    if src.exists():
        shutil.copy(src, sessions_dir / f"{commit}.log")


def main():
    commit = get_current_commit()
    description = get_commit_description()
    best_before = get_best_val_bpb()

    returncode, log_text = run_training()

    crashed = returncode != 0 or "FAIL" in log_text

    if crashed:
        tail = "\n".join(log_text.splitlines()[-25:])
        print(f"\n[session] status=crash | commit={commit}")
        print(f"[session] Exit code: {returncode}")
        print(f"[session] Crash tail:\n{tail}")
        append_results(commit, 0, 0, "crash", description)
        archive_log(commit)
        return

    metrics = parse_output(log_text)
    val_bpb = metrics.get("val_bpb")

    if val_bpb is None:
        tail = "\n".join(log_text.splitlines()[-25:])
        print(f"\n[session] status=crash | Could not parse val_bpb")
        print(f"[session] Log tail:\n{tail}")
        append_results(commit, 0, 0, "crash", description)
        archive_log(commit)
        return

    memory_gb = metrics.get("peak_vram_mb", 0) / 1024
    training_seconds = metrics.get("training_seconds", 0)
    num_steps = int(metrics.get("num_steps", 0))

    delta = best_before - val_bpb
    improved = delta > 0
    status = "keep" if improved else "discard"

    print(f"\n[session] ===== RESULT =====")
    print(f"[session] commit:       {commit}")
    print(f"[session] description:  {description}")
    print(f"[session] val_bpb:      {val_bpb:.6f}")
    print(f"[session] best_prev:    {best_before:.6f}  ({'IMPROVED' if improved else 'no improvement'})")
    print(f"[session] delta:        {delta:+.6f}")
    print(f"[session] vram_gb:      {memory_gb:.2f}")
    print(f"[session] train_sec:    {training_seconds:.0f}")
    print(f"[session] num_steps:    {num_steps}")
    print(f"[session] status:       {status}")

    append_results(commit, val_bpb, memory_gb, status, description)
    archive_log(commit)


if __name__ == "__main__":
    main()
