#!/usr/bin/env python3
"""Record one public aggregate Discord invite snapshot per Berlin calendar day.

No Discord bot token, members list, or personal identifiers are accessed.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

GUILD_ID = "1429171120715862038"
INVITE_CODE = "yb5Cg7HjBg"
BASELINE_MEMBERS = 407  # 2026-11-11 20:57 CET, direct Discord API response
CSV_PATH = Path("data/member-counts.csv")
FIELDS = ["date_berlin", "checked_at_utc", "members", "online", "net_from_baseline"]


def get_counts() -> tuple[int, int]:
    url = f"https://discord.com/api/v10/invites/{INVITE_CODE}?with_counts=true"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Joel271997CommunityGrowthTracker/1.0 (public aggregate counts)",
        },
    )
    with urlopen(request, timeout=20) as response:
        payload = json.load(response)
    if str(payload.get("guild", {}).get("id")) != GUILD_ID:
        raise RuntimeError("Discord invite returned the wrong server, refusing to record data")
    members = payload.get("approximate_member_count")
    online = payload.get("approximate_presence_count")
    if type(members) is not int or members < 0:
        raise RuntimeError("Discord member count missing or invalid")
    if type(online) is not int or online < 0:
        raise RuntimeError("Discord online count missing or invalid")
    return members, online


def main() -> int:
    now = datetime.now(timezone.utc)
    today = now.astimezone(ZoneInfo("Europe/Berlin")).date().isoformat()
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    if CSV_PATH.exists():
        with CSV_PATH.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames != FIELDS:
                raise RuntimeError("Unexpected CSV columns; not modifying existing data")
            rows = list(reader)

    # Keep the very first validated baseline immutable and do not double-count
    # GitHub schedule retries or manual reruns on the same calendar day.
    if any(row["date_berlin"] == today for row in rows):
        print(f"Snapshot for {today} already recorded; leaving existing data unchanged.")
        return 0

    try:
        members, online = get_counts()
    except (HTTPError, URLError, ValueError, KeyError, RuntimeError) as exc:
        print(f"Discord API unavailable or returned invalid data: {exc}", file=sys.stderr)
        return 1

    rows.append({
        "date_berlin": today,
        "checked_at_utc": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "members": str(members),
        "online": str(online),
        "net_from_baseline": str(members - BASELINE_MEMBERS),
    })
    with CSV_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"{today}: {members} members, {online} online; net from 407: {members-BASELINE_MEMBERS:+d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
