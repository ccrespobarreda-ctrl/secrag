#!/usr/bin/env python3
"""
Run the sequence this README documents, from a clean clone, and record it.

    python first_run.py                 # stop at the first failure
    python first_run.py --keep-going    # run everything, record every failure

WHAT THIS IS FOR

Continuous integration checks the tests, the gold labels and the release
artifacts. It does not build the corpus: the filings are not in the repository
and fetching nineteen 10-Ks is not something to do on every push. So the
instructions under "Reproducing it" -- fetch, parse, chunk, embed, load, verify,
evaluate -- have never been executed anywhere except the machine they were
written on, and nothing checks them.

That is the same shape as the fourteen findings: text that reads as true, that
no gate exercises. It is also the one with the worst consequence, because it
fails on a reader's machine rather than on mine.

WHAT IT DELIBERATELY DOES NOT DO

It does not fix anything, install anything it was not told to, or work around a
failure. A workaround applied while measuring is a measurement of the
workaround. Every step records its command, its exit code, its duration and the
tail of its output into docs/first-run-log.md, and that log is the deliverable.

It also records preconditions the README does not mention -- an unset variable,
a missing tool, a port that disagrees with the workflow file -- because those
are findings, not obstacles to get past quietly.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "docs" / "first-run-log.md"

# Exactly the sequence the README documents, in order. Anything this list needs
# that the README does not state is itself a finding.
STEPS: list[tuple[str, list[str]]] = [
    ("install dependencies",      [sys.executable, "-m", "pip", "install", "-r",
                                   "requirements.txt"]),
    ("fetch filings from EDGAR",  [sys.executable, "src/edgar.py"]),
    ("parse HTML to sections",    [sys.executable, "src/parse.py"]),
    ("verify section boundaries", [sys.executable, "src/verify_parse.py"]),
    ("chunk",                     [sys.executable, "src/chunk.py"]),
    ("embed locally on CPU",      [sys.executable, "src/embed.py"]),
    ("load into Postgres",        [sys.executable, "src/load.py"]),
    ("reconcile the warehouse",   [sys.executable, "src/load.py", "--dry-run"]),
    ("gold labels resolve",       [sys.executable, "src/verify_labels.py",
                                   "--questions", "eval/questions_vnext.yaml",
                                   "--max-anchor-matches", "8",
                                   "--max-exceptions", "4"]),
    ("retrieval, with sabotage",  [sys.executable, "src/evaluate_retrieval.py",
                                   "--sabotage", "--save",
                                   "eval/results/retrieval.json"]),
    ("release artifacts",         [sys.executable, "verify_release.py"]),
]


def preconditions() -> list[tuple[str, str]]:
    """Facts about this machine, and gaps in the instructions."""
    notes = []
    for tool in ("git", "docker", "psql"):
        where = shutil.which(tool)
        notes.append((tool, where or "NOT FOUND on PATH"))

    url = os.environ.get("DATABASE_URL")
    notes.append(("DATABASE_URL", url or "NOT SET -- the README sets it by hand"))
    if url and ":5433" in url:
        notes.append(("port", "5433, from the README. .github/workflows/ci.yml "
                              "uses 5432. One of the two is wrong, or the "
                              "difference is undeclared."))
    elif url:
        notes.append(("port", "not 5433; the README's PowerShell block sets 5433"))

    for var in ("SEC_USER_AGENT", "EDGAR_USER_AGENT", "USER_AGENT"):
        if os.environ.get(var):
            notes.append((var, "set"))
            break
    else:
        notes.append(("SEC user agent", "no such variable set. EDGAR requires a "
                                        "declared user agent; if src/edgar.py "
                                        "hardcodes one, say so in the README."))

    notes.append(("LLM_PROVIDER", os.environ.get("LLM_PROVIDER",
                  "unset -- retrieval needs no model, so this run does not "
                  "either")))
    return notes


KEY_LIBS = ("torch", "sentence-transformers", "transformers", "numpy",
            "psycopg2-binary", "beautifulsoup4", "lxml", "anthropic", "pyyaml",
            "scikit-learn", "scipy")


def libraries() -> list[tuple[str, str]]:
    """The versions this run measured under.

    requirements.txt states floors and no ceilings -- `torch>=2.2`,
    `sentence-transformers>=3.0` -- and nothing in the repository records the
    versions the published figures were measured with. So a clone today
    installs a stack the release never saw, and whether Recall@16 still comes
    out at 0.735 is a question, not an assumption. Recording this is what makes
    the answer mean something either way.
    """
    out = subprocess.run([sys.executable, "-m", "pip", "freeze"],
                         capture_output=True, text=True)
    installed = {}
    for line in out.stdout.splitlines():
        if "==" in line:
            name, _, version = line.partition("==")
            installed[name.strip().lower()] = version.strip()
    rows = [(lib, installed.get(lib, "NOT INSTALLED")) for lib in KEY_LIBS]
    rows.insert(0, ("python", platform.python_version()))
    return rows


def run(name: str, cmd: list[str], keep_going: bool) -> dict:
    print(f"\n== {name}\n   {' '.join(cmd)}")
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                              errors="replace")
        code, out = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError as exc:
        code, out = 127, f"{exc}"
    took = time.monotonic() - started

    tail = [l for l in out.splitlines() if l.strip()][-12:]
    print(f"   exit {code} in {took:.1f}s")
    for line in tail[-4:]:
        print(f"   | {line[:100]}")
    return {"name": name, "cmd": " ".join(cmd), "code": code,
            "seconds": round(took, 1), "tail": tail}


def write_log(notes, libs, results, stopped_at) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
    ok = sum(1 for r in results if r["code"] == 0)
    lines = [
        "# First run from a clean clone",
        "",
        "Produced by `python first_run.py`. Nothing here was fixed while it ran:",
        "a workaround applied during a measurement measures the workaround.",
        "",
        f"- **When:** {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
        f"- **Commit:** `{commit or 'unknown'}`",
        f"- **Platform:** {platform.platform()}, Python {platform.python_version()}",
        f"- **Result:** {ok} of {len(results)} steps succeeded"
        + (f", stopped at *{stopped_at}*" if stopped_at else ", all of them"),
        "",
        "## The machine, and what the instructions leave out",
        "",
        "| | |",
        "|---|---|",
    ]
    lines += [f"| `{k}` | {v} |" for k, v in notes]
    lines += [
        "",
        "## The versions this run measured under",
        "",
        "`requirements.txt` states floors and no ceilings, and nothing in this",
        "repository records the versions the published figures were measured",
        "with. Whether the numbers reproduce across this gap is the question the",
        "run answers.",
        "",
        "| | |",
        "|---|---|",
    ]
    lines += [f"| `{k}` | {v} |" for k, v in libs]
    lines += ["", "## Each step", "", "| Step | Exit | Seconds |",
              "|---|---:|---:|"]
    lines += [f"| {r['name']} | {'ok' if r['code'] == 0 else f'**{r['code']}**'}"
              f" | {r['seconds']} |" for r in results]

    for r in results:
        if r["code"] != 0:
            lines += ["", f"### Failed: {r['name']}", "",
                      f"`{r['cmd']}` exited {r['code']} after {r['seconds']}s.",
                      "", "```text"] + r["tail"] + ["```"]

    lines += ["", "## What to do with this", "",
              "Each failure above is a defect in the instructions, in the code, or",
              "in an assumption about the environment that was never written down.",
              "Fix them one at a time and re-run this script; the log is",
              "regenerated, so the diff shows what the fix moved.", ""]
    LOG.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {LOG.relative_to(ROOT).as_posix()}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep-going", action="store_true",
                    help="do not stop at the first failure")
    args = ap.parse_args()

    notes = preconditions()
    libs = libraries()
    print("Versions:")
    for key, value in libs:
        print(f"  {key:<22} {value}")
    print("\nPreconditions:")
    for key, value in notes:
        print(f"  {key:<18} {value}")
    print("\nThis script does not start Postgres. The README's `docker compose "
          "up -d`\nand `psql -f sql/schema.sql` come first, by hand, because "
          "how they fail\nis part of what is being measured.")

    results, stopped_at = [], None
    for name, cmd in STEPS:
        result = run(name, cmd, args.keep_going)
        results.append(result)
        if result["code"] != 0 and not args.keep_going:
            stopped_at = name
            print(f"\nStopped at: {name}. Nothing was worked around.")
            break

    write_log(notes, libs, results, stopped_at)
    return 0 if all(r["code"] == 0 for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
