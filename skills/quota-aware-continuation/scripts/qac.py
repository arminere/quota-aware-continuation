#!/usr/bin/env python3
"""Helpers for the quota-aware-continuation skill (stdlib only, Python 3.8+).

Subcommands
  decide          Continue or pause, from the 5-hour and weekly usage windows; when to resume.
  tick            What a scheduled run should do: done / hold / wait / busy / go (same rules as the gate hook).
  heartbeat       Print the recurring cron expression for the heartbeat task.
  write           Atomically write stdin to a file (temp file + fsync + rename).
  validate        Check that a checkpoint file has every required field and section.
  install-hook    Add the gate hook (qac_gate.py) to ~/.claude/settings.json (backup kept).
  uninstall-hook  Remove it again.
  now             Print the current local time as ISO 8601 with offset.

Exit codes: 0 ok, 1 validation failed / bad input.
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qac_gate  # noqa: E402

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
VALID_STATUS = {"in_progress", "paused", "hold", "done"}
PLACEHOLDER = re.compile(r"<(?:FILL|TODO)[^>]*>")
GATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qac_gate.py")
parse_fields = qac_gate.parse_fields


def parse_iso(value):
    dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp needs a timezone offset: %s" % value)
    return dt


def local_iso(dt):
    return dt.astimezone().replace(microsecond=0).isoformat()


def usage_windows(usage):
    """Return (windows, note) from the get_usage result, its `plan`, or a bare list."""
    if isinstance(usage, dict) and "plan" in usage:
        usage = usage["plan"]
    if isinstance(usage, dict):
        if usage.get("status") not in (None, "ok"):
            return [], "usage status is %r" % usage.get("status")
        usage = usage.get("windows", [])
    return list(usage or []), None


def cmd_decide(a):
    windows, note = [], None
    if a.usage_json:
        raw = sys.stdin.read() if a.usage_json == "-" else open(a.usage_json, encoding="utf-8").read()
        windows, note = usage_windows(json.loads(raw))
    if a.percent is not None:
        windows.append({"label": "5-hour limit", "percentUsed": a.percent, "resetsAt": a.resets_at})
    if a.weekly_percent is not None:
        windows.append({"label": "Weekly", "percentUsed": a.weekly_percent, "resetsAt": a.weekly_resets_at})

    now = datetime.now(timezone.utc)
    out = {"now": local_iso(now), "threshold": a.threshold, "weekly_threshold": a.weekly_threshold}
    watched, over = [], []
    for w in windows:
        label = str(w.get("label", ""))
        if "5-hour" in label.lower():
            limit = a.threshold
        elif "weekly" in label.lower():
            limit = a.weekly_threshold
        else:
            continue
        if w.get("percentUsed") is None:
            continue
        watched.append(label)
        if float(w["percentUsed"]) >= limit:
            over.append(w)

    if a.force_pause:
        five = [w for w in windows if "5-hour" in str(w.get("label", "")).lower()]
        over = five or [{"label": "forced", "resetsAt": None}]
    if not watched and not a.force_pause:
        out.update(action="unknown", reason=note or "no usage data",
                   advice="continue; checkpoint after every step; pause only on a rate-limit error")
    elif over:
        out.update(action="pause", limited_by=[str(w.get("label")) for w in over],
                   reason="forced (test)" if a.force_pause else "usage >= threshold")
    else:
        out.update(action="continue", reason="usage below thresholds")
    if not a.hide_percent:
        out["usage"] = {str(w.get("label")): w.get("percentUsed") for w in windows}

    # Resume after the latest reset among the windows that are over their limit.
    resume = None
    if a.resume_in_minutes is not None:
        resume = now + timedelta(minutes=a.resume_in_minutes)
    else:
        resets = [parse_iso(w["resetsAt"]) for w in over if w.get("resetsAt")]
        if resets:
            resume = max(resets) + timedelta(minutes=a.delay_minutes)
    if resume is not None and out["action"] == "pause":
        resume = max(resume, now + timedelta(minutes=2))
        if resume.second or resume.microsecond:  # round up to the whole minute
            resume = resume.replace(second=0, microsecond=0) + timedelta(minutes=1)
        out["resume_after"] = local_iso(resume)
        lr = resume.astimezone()
        # One-shot cron for schedulers without fireAt. It matches again next year: delete it after use.
        out["resume_cron_local"] = "%d %d %d %d *" % (lr.minute, lr.hour, lr.day, lr.month)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_tick(a):
    fields = parse_fields(open(a.path, encoding="utf-8").read())
    if a.lock_minutes is not None:
        fields["lock_minutes"] = str(a.lock_minutes)
    allow, reason = qac_gate.decide(fields, datetime.now(timezone.utc))
    status = fields.get("status")
    if allow:
        action = "go"
    elif status in ("done", "hold"):
        action = status
    elif "waiting" in reason:
        action = "wait"
    else:
        action = "busy"
    print(json.dumps({"status": status, "action": action, "reason": reason,
                      "previous_run": fields.get("run_session", "none")}, indent=2))
    return 0


def cmd_heartbeat(a):
    if a.every < 1 or a.every > 60:
        raise ValueError("--every must be 1..60 minutes")
    minute = "*/%d" % a.every if a.every < 60 else str((datetime.now().minute + 5) % 60)
    if not a.days:
        cron = "%s * * * *" % minute
        until = "until deleted"
    else:
        start = datetime.now().astimezone()
        end = start + timedelta(days=a.days - 1)
        if start.month == end.month:
            cron = "%s * %d-%d %d *" % (minute, start.day, end.day, start.month)
        else:  # tail of this month + head of the next (also matches those days in other listed months)
            cron = "%s * %d-31,1-%d %d,%d *" % (minute, start.day, end.day, start.month, end.month)
        until = end.strftime("%Y-%m-%d")
    print(json.dumps({"cron": cron, "until": until,
                      "note": "the gate hook blocks idle ticks; delete the task when you are back"}, indent=2))
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


def validate_text(text):
    errors = []
    fields = parse_fields(text)
    for k in REQUIRED_FIELDS:
        if not fields.get(k):
            errors.append("missing field: %s" % k)
    if fields.get("status") and fields["status"] not in VALID_STATUS:
        errors.append("status must be one of %s" % sorted(VALID_STATUS))
    for k in ("updated", "resume_after"):
        if fields.get(k) and fields[k] != "none":
            try:
                parse_iso(fields[k])
            except ValueError as e:
                errors.append("%s: %s" % (k, e))
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


def hook_command():
    return '"%s" "%s"' % (sys.executable.replace("\\", "/"), GATE.replace("\\", "/"))


def is_gate_entry(entry):
    return any("qac_gate.py" in str(h.get("command", "")) for h in entry.get("hooks", []))


def load_settings(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_settings(path, data):
    if os.path.exists(path):
        shutil.copy2(path, path + ".qac-backup")
    tmp = path + ".qac-tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def cmd_install_hook(a):
    data = load_settings(a.settings)
    entries = data.setdefault("hooks", {}).setdefault("UserPromptSubmit", [])
    entries[:] = [e for e in entries if not is_gate_entry(e)]
    entries.append({"hooks": [{"type": "command", "command": hook_command(), "timeout": 10}]})
    save_settings(a.settings, data)
    print("installed gate hook in %s (backup: .qac-backup)\n  %s" % (a.settings, hook_command()))
    return 0


def cmd_uninstall_hook(a):
    data = load_settings(a.settings)
    entries = data.get("hooks", {}).get("UserPromptSubmit", [])
    kept = [e for e in entries if not is_gate_entry(e)]
    if len(kept) == len(entries):
        print("gate hook not installed")
        return 0
    if kept:
        data["hooks"]["UserPromptSubmit"] = kept
    else:
        del data["hooks"]["UserPromptSubmit"]
    save_settings(a.settings, data)
    print("removed gate hook from %s" % a.settings)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("decide")
    d.add_argument("--usage-json", help="file with the get_usage result, or - for stdin")
    d.add_argument("--percent", type=float, help="5-hour window percent used")
    d.add_argument("--resets-at", help="ISO 8601 reset time of the 5-hour window")
    d.add_argument("--weekly-percent", type=float, help="weekly window percent used")
    d.add_argument("--weekly-resets-at", help="ISO 8601 reset time of the weekly window")
    d.add_argument("--threshold", type=float, default=95, help="5-hour pause threshold")
    d.add_argument("--weekly-threshold", type=float, default=95, help="weekly pause threshold")
    d.add_argument("--delay-minutes", type=int, default=5, help="resume this long after the reset")
    d.add_argument("--resume-in-minutes", type=int, help="override: resume N minutes from now (tests)")
    d.add_argument("--force-pause", action="store_true", help="simulate reaching the threshold (tests)")
    d.add_argument("--hide-percent", action="store_true", help="omit percentages from the output (for logs)")
    d.set_defaults(func=cmd_decide)

    k = sub.add_parser("tick")
    k.add_argument("path", help="checkpoint file")
    k.add_argument("--lock-minutes", type=float, help="override the checkpoint's lock_minutes")
    k.set_defaults(func=cmd_tick)

    h = sub.add_parser("heartbeat")
    h.add_argument("--every", type=int, default=30, help="minutes between ticks (1-60)")
    h.add_argument("--days", type=int, default=0, help="limit to N calendar days (0 = no limit)")
    h.set_defaults(func=cmd_heartbeat)

    w = sub.add_parser("write")
    w.add_argument("path")
    w.set_defaults(func=cmd_write)

    v = sub.add_parser("validate")
    v.add_argument("path")
    v.set_defaults(func=cmd_validate)

    settings = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
    for name, func in (("install-hook", cmd_install_hook), ("uninstall-hook", cmd_uninstall_hook)):
        s = sub.add_parser(name)
        s.add_argument("--settings", default=settings)
        s.set_defaults(func=func)

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
