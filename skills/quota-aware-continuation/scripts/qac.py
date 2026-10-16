#!/usr/bin/env python3
"""Helpers for the quota-aware-continuation skill (stdlib only, Python 3.8+).

Subcommands
  decide    Decide continue/pause from usage numbers and compute the resume time.
  write     Atomically write stdin to a file (temp file + fsync + rename).
  validate  Check that a checkpoint file has every required field and section.
  heartbeat Print a recurring cron expression limited to the next N days.
  tick      Decide what a scheduled run should do: done / busy / go.
  now       Print the current local time as ISO 8601 with offset.

Exit codes: 0 ok, 1 validation failed / bad input.
"""
import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone

REQUIRED_FIELDS = ["status", "updated", "threshold", "cycle", "task_slug"]
REQUIRED_SECTIONS = [
    "Goal",
    "Resume entry",
    "Done",
    "Remaining steps",
    "Next action",
    "Constraints",
    "Scheduled resume",
    "Pause log",
]
VALID_STATUS = {"in_progress", "paused", "done"}
PLACEHOLDER = re.compile(r"<(?:FILL|TODO)[^>]*>")


def parse_iso(value):
    dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp needs a timezone offset: %s" % value)
    return dt


def local_iso(dt):
    return dt.astimezone().replace(microsecond=0).isoformat()


def pick_window(usage, window):
    """Accept the get_usage result, its `plan`, or a bare windows list."""
    if isinstance(usage, dict) and "plan" in usage:
        usage = usage["plan"]
    if isinstance(usage, dict):
        if usage.get("status") not in (None, "ok"):
            return None, "usage status is %r" % usage.get("status")
        usage = usage.get("windows", [])
    for w in usage or []:
        if window.lower() in str(w.get("label", "")).lower():
            return w, None
    return None, "no usage window matching %r" % window


def cmd_decide(a):
    percent, resets_at, note = a.percent, a.resets_at, None
    if a.usage_json:
        raw = sys.stdin.read() if a.usage_json == "-" else open(a.usage_json, encoding="utf-8").read()
        w, note = pick_window(json.loads(raw), a.window)
        if w:
            percent, resets_at = w.get("percentUsed"), w.get("resetsAt")
    now = datetime.now(timezone.utc)
    out = {"threshold": a.threshold, "now": local_iso(now)}

    if percent is None:
        # Usage unknown: keep working but checkpoint after every step.
        out.update(action="unknown", reason=note or "no usage data",
                   advice="continue; checkpoint after every step; pause only on a rate-limit error")
    elif a.force_pause or float(percent) >= a.threshold:
        out.update(action="pause", percent=percent,
                   reason="forced (test)" if a.force_pause else "usage >= threshold")
    else:
        out.update(action="continue", percent=percent, reason="usage below threshold")

    if a.resume_in_minutes is not None:
        fire = now + timedelta(minutes=a.resume_in_minutes)
    elif resets_at:
        fire = parse_iso(resets_at) + timedelta(minutes=a.delay_minutes)
    else:
        fire = None
    if fire is not None:
        # Schedulers reject past timestamps; keep at least 2 minutes of headroom.
        fire = max(fire, now + timedelta(minutes=2))
        if fire.second or fire.microsecond:  # round up to the whole minute
            fire = fire.replace(second=0, microsecond=0) + timedelta(minutes=1)
        out["fire_at"] = local_iso(fire)
        lf = fire.astimezone()
        # One-shot cron for schedulers without fireAt. It matches again next year: delete it after use.
        out["fire_at_cron_local"] = "%d %d %d %d *" % (lf.minute, lf.hour, lf.day, lf.month)
    if a.hide_percent:
        out.pop("percent", None)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_write(a):
    data = sys.stdin.buffer.read()
    target = os.path.abspath(a.path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".qac-", dir=os.path.dirname(target))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    print("wrote %d bytes -> %s" % (len(data), a.path))
    return 0


def parse_fields(text):
    return dict(re.findall(r"^([a-z_]+):[ \t]*(.*?)\s*$", text, re.M))


def validate_text(text):
    errors = []
    fields = parse_fields(text)
    for k in REQUIRED_FIELDS:
        if not fields.get(k):
            errors.append("missing field: %s" % k)
    if fields.get("status") and fields["status"] not in VALID_STATUS:
        errors.append("status must be one of %s" % sorted(VALID_STATUS))
    if fields.get("updated"):
        try:
            parse_iso(fields["updated"])
        except ValueError as e:
            errors.append("updated: %s" % e)
    headings = {h.strip() for h in re.findall(r"^##\s+(.+)$", text, re.M)}
    for s in REQUIRED_SECTIONS:
        if s not in headings:
            errors.append("missing section: ## %s" % s)
    if PLACEHOLDER.search(text):
        errors.append("unfilled placeholder: %s" % PLACEHOLDER.search(text).group(0))
    return errors


def cmd_validate(a):
    errors = validate_text(open(a.path, encoding="utf-8").read())
    for e in errors:
        print("ERROR " + e)
    if not errors:
        print("OK " + a.path)
    return 1 if errors else 0


def cmd_heartbeat(a):
    if a.every < 1 or a.every > 60:
        raise ValueError("--every must be 1..60 minutes")
    start = datetime.now().astimezone()
    end = start + timedelta(days=a.days - 1)
    minute = "*/%d" % a.every if a.every < 60 else str((start.minute + 5) % 60)
    if start.month == end.month:
        days, months = "%d-%d" % (start.day, end.day), str(start.month)
    else:  # crosses a month boundary: tail of this month + head of the next
        days, months = "%d-31,1-%d" % (start.day, end.day), "%d,%d" % (start.month, end.month)
    print(json.dumps({"cron": "%s * %s %s *" % (minute, days, months),
                      "until": end.strftime("%Y-%m-%d"),
                      "note": "matches again on the same dates next year: delete the task when done"},
                     indent=2))
    return 0


def cmd_tick(a):
    text = open(a.path, encoding="utf-8").read()
    fields = parse_fields(text)
    status = fields.get("status")
    out = {"status": status}
    if status == "done":
        out["action"] = "done"
    elif status == "in_progress":
        age = (datetime.now(timezone.utc) - parse_iso(fields["updated"])).total_seconds() / 60
        out["updated_minutes_ago"] = round(age, 1)
        out["action"] = "busy" if age < a.lock_minutes else "go"
    else:
        out["action"] = "go"
    print(json.dumps(out, indent=2))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("decide")
    d.add_argument("--usage-json", help="file with the get_usage result, or - for stdin")
    d.add_argument("--percent", type=float)
    d.add_argument("--resets-at", help="ISO 8601 reset time of the window")
    d.add_argument("--window", default="5-hour", help="label substring of the window to watch")
    d.add_argument("--threshold", type=float, default=95)
    d.add_argument("--delay-minutes", type=int, default=5, help="resume this long after the reset")
    d.add_argument("--resume-in-minutes", type=int, help="override: resume N minutes from now (tests)")
    d.add_argument("--force-pause", action="store_true", help="simulate reaching the threshold (tests)")
    d.add_argument("--hide-percent", action="store_true", help="omit the percentage from output (for logs)")
    d.set_defaults(func=cmd_decide)

    w = sub.add_parser("write")
    w.add_argument("path")
    w.set_defaults(func=cmd_write)

    v = sub.add_parser("validate")
    v.add_argument("path")
    v.set_defaults(func=cmd_validate)

    h = sub.add_parser("heartbeat")
    h.add_argument("--every", type=int, default=30, help="minutes between ticks (1-60)")
    h.add_argument("--days", type=int, default=2, help="how many calendar days it may fire")
    h.set_defaults(func=cmd_heartbeat)

    k = sub.add_parser("tick")
    k.add_argument("path", help="checkpoint file")
    k.add_argument("--lock-minutes", type=float, default=20)
    k.set_defaults(func=cmd_tick)

    n = sub.add_parser("now")
    n.set_defaults(func=lambda a: print(local_iso(datetime.now(timezone.utc))) or 0)

    a = p.parse_args(argv)
    try:
        return a.func(a)
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print("ERROR %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
