"""Turn a coverage.py JSON report into a shields.io endpoint badge.

Usage: python coverage_badge.py coverage.json badge.json

The output follows https://shields.io/badges/endpoint-badge, so the README
can show it via img.shields.io/endpoint?url=<raw URL of badge.json>.
"""

import json
import math
import sys

# (minimum percent, colour), checked in order.
COLORS = [(95, "brightgreen"), (90, "green"), (80, "yellowgreen"), (70, "yellow"), (60, "orange")]


def badge(percent: float) -> dict:
    # Round down so the label never claims a threshold the colour didn't
    # reach (94.9% shows as "94%", not "95%").
    shown = math.floor(percent)
    color = next((c for minimum, c in COLORS if shown >= minimum), "red")
    return {"schemaVersion": 1, "label": "coverage", "message": f"{shown}%", "color": color}


def main(report_path: str, badge_path: str) -> None:
    with open(report_path, encoding="utf-8") as f:
        percent = json.load(f)["totals"]["percent_covered"]
    with open(badge_path, "w", encoding="utf-8") as f:
        json.dump(badge(percent), f)
        f.write("\n")
    print(f"coverage: {percent:.2f}%")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
