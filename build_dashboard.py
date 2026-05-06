"""
Reads the latest JSON report and injects it into dashboard.html.
Run after main.py — or automatically via cron.
"""

import json
import glob
import os
from pathlib import Path

def build():
    reports = sorted(glob.glob("reports/pocketly_social_raw_*.json"))
    if not reports:
        print("No reports found in reports/")
        return

    latest = reports[-1]
    with open(latest, encoding="utf-8") as f:
        data = json.load(f)

    template = Path("dashboard.html").read_text(encoding="utf-8")
    injected = template.replace(
        "INJECT_JSON_HERE",
        json.dumps(data, ensure_ascii=False)
    )
    Path("dashboard.html").write_text(injected, encoding="utf-8")
    print(f"Dashboard updated from {latest}")

if __name__ == "__main__":
    build()
