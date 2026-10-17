#!/usr/bin/env python3
"""UserPromptSubmit hook for quota-aware-continuation (stdlib only).

Runs before a prompt reaches the model. It only looks at scheduled heartbeat
prompts that carry the TICK marker; everything else passes through untouched.
For a tick it reads the checkpoint and blocks the prompt when there is nothing
to do, so idle heartbeats cost no model usage:

  status: done                    -> block (task finished)
  status: hold                    -> block (user stopped it; waits for "continue")
  resume_after in the future      -> block (waiting for a 5-hour or weekly reset)
  in_progress, updated < lock     -> block (another run is active)
  anything else                   -> allow

Every decision is appended to <checkpoint dir>/gate.log.
Install with: python qac.py install-hook
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

MARKER = "quota-aware-continuation, TICK mode"
DEFAULT_LOCK_MINUTES = 20


def parse_fields(text):
    return dict(re.findall(r"^([a-z_]+):[ \t]*(.*?)\s*$", text, re.M))


def parse_time(value):
    dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.astimezone()


def decide(fields, now):
    """Return (allow, reason)."""
    status = fields.get("status", "")
    if status == "done":
        return False, "task is done"
    if status == "hold":
        return False, "held by the user; say 'continue' in a session to resume"
    resume_after = fields.get("resume_after", "").strip()
    if resume_after and resume_after != "none":
        try:
            if parse_time(resume_after) > now:
                return False, "waiting for usage reset until %s" % resume_after
        except ValueError:
            pass
    if status == "in_progress" and fields.get("updated"):
        try:
            lock = float(fields.get("lock_minutes") or DEFAULT_LOCK_MINUTES)
            age = (now - parse_time(fields["updated"])).total_seconds() / 60
            if age < lock:
                return False, "another run is active (updated %.0f min ago)" % age
        except ValueError:
            pass
    return True, "go"


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    prompt = event.get("prompt") or ""
    if MARKER not in prompt:
        return 0
    m = re.search(r"Checkpoint:\s*(\S+)", prompt)
    if not m or not os.path.isfile(m.group(1)):
        return 0  # let the model report the missing checkpoint
    path = m.group(1)
    now = datetime.now(timezone.utc)
    allow, reason = decide(parse_fields(open(path, encoding="utf-8").read()), now)
    try:
        with open(os.path.join(os.path.dirname(path), "gate.log"), "a", encoding="utf-8") as f:
            f.write("%s | %s | %s\n" % (now.astimezone().replace(microsecond=0).isoformat(),
                                        "allow" if allow else "block", reason))
    except OSError:
        pass
    if not allow:
        print(json.dumps({"decision": "block", "reason": "quota-aware-continuation: " + reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
