#!/usr/bin/env python3
"""run_demo.py — one-shot demonstration of the Crawler Power Kit.

Runs the offline-safe parts (doctor + search URL routing + dedup) and the
online parts (paper lookup, quick fetch) with graceful skips when the
network is unavailable. Exit code 0 = demo completed.

  python examples/run_demo.py            # from the extracted skill root
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(os.path.dirname(HERE), "scripts")
PY = sys.executable


def run(label, *args, timeout=90):
    print(f"\n{'=' * 60}\n{label}\n{'=' * 60}")
    try:
        r = subprocess.run([PY, os.path.join(KIT, "cpk.py"), *args],
                           timeout=timeout, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or r.stderr).strip()
        print("\n".join(out.splitlines()[:12]))
        return r.returncode
    except subprocess.TimeoutExpired:
        print("(skipped: timeout — network egress may be restricted)")
        return 0


def main():
    print("Crawler Power Kit demo")
    print(f"interpreter: {PY}")
    run("1/4 doctor — toolchain health check", "doctor")
    run("2/4 search — CN query routing (URL list only)", "search", "高校辅导员队伍建设")
    run("3/4 paper — DOI registry + Crossref verification",
        "paper", "10.1109/TIT.2006.871582")
    run("4/4 quick — ladder fetch a static page", "quick", "https://example.com")
    print("\ndemo complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
