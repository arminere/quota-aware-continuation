---
name: quota-aware-continuation
description: Keep a long task going across usage-limit windows while the user is away. Use when the user says they are going to sleep / stepping away and wants a long task to keep running, asks to "pause at 95% and resume after the reset", "continue after the 5-hour limit resets", "额度快用完时暂停、重置后自动续跑", asks to continue / resume a held quota-aware task ("继续"), or when a session is started by a scheduled task whose prompt names a quota-aware-continuation checkpoint (TICK mode).
---

# Quota-aware continuation

Work on a long task in cycles. Before each step, check plan usage. When the 5-hour or the
weekly window is nearly used up, write a checkpoint and stop. A heartbeat task starts a
brand-new session every 30 minutes; a local **gate hook** checks the checkpoint first and
blocks the heartbeat (no model call, no usage) whenever there is nothing to do. When the
reset time passes, the next heartbeat gets through, reads the checkpoint and carries on.

| State | What the heartbeat does |
|---|---|
| `in_progress`, recently updated | Blocked by the gate: a run is active |
| `paused` with `resume_after` in the future | Blocked until then (5-hour or weekly reset) |
| `paused`, reset time passed | Allowed: resume work |
| `in_progress`, stale | Allowed: check whether the user pressed Stop; if so → `hold`, else resume |
| `hold` (user stopped it) | Blocked until the user says "continue" |
| `done` | Blocked forever. The task entry remains until the user deletes it |

`scripts/qac.py` (Python 3 stdlib) does the fiddly parts: usage decision, gate rules,
cron expression, atomic writes, checkpoint validation, hook install. `scripts/qac_gate.py`
is the hook. `SKILL_DIR` means the directory containing this file.

## Modes

- **START**: the user invokes the skill in a live session.
- **TICK**: the session was started by the heartbeat; the prompt names a checkpoint.
- **CONTINUE**: the user asks to continue / resume a held task.

## Settings (use defaults unless the user said otherwise)

| Setting | Default |
|---|---|
| 5-hour threshold | 95 (% used) |
| weekly threshold | 95 (% used); pause until the weekly reset, then continue automatically |
| heartbeat | every 30 minutes, no end date (`qac.py heartbeat`) |
| resume delay | 5 minutes after the reset |
| checkpoint | `<working dir>/.qac/CHECKPOINT.md` |
| lock | 20 minutes (`lock_minutes`) |

## START procedure (user present)

1. Confirm the goal and done-criteria in one short message, only if unclear.
2. **Gate hook.** If `~/.claude/settings.json` has no `UserPromptSubmit` entry running
   `qac_gate.py`, run `python SKILL_DIR/scripts/qac.py install-hook` (keeps a backup).
   Tell the user it was added. Without it everything still works, but every idle
   heartbeat costs a model call.
3. **Unattended permissions.** A scheduled run must not stop at a permission prompt. In
   the Claude desktop app: this session is in Auto or Bypass mode **and** the task is
   created in a turn the user typed (the tool result says which mode was saved), or the
   user has `"permissions": {"defaultMode": "auto"}` in `~/.claude/settings.json`.
   Fix this now while the user is here.
4. Copy `SKILL_DIR/templates/CHECKPOINT.md` to the checkpoint path, fill every
   `<FILL ...>`, split the work into small ordered steps, and run
   `python SKILL_DIR/scripts/qac.py validate <checkpoint>`.
5. **Create the heartbeat**: `qac.py heartbeat` prints the cron (`*/30 * * * *`). Desktop
   app: `mcp__scheduled-tasks__create_scheduled_task` with that `cronExpression`, id
   `qac-<task_slug>`, and the prompt below.
6. Keep the machine awake if possible (desktop: `mcp__ccd_host__request_keep_awake`).
   Never shut it down.
7. Tell the user in two lines: it checks every 30 minutes; pressing Stop holds the task
   until they say "continue"; delete the `qac-<slug>` task when they are back after it
   finished. Then enter the work loop.

### Heartbeat prompt (keep the marker line exactly; the gate looks for it)

```
Continue a long task (quota-aware-continuation, TICK mode).
Checkpoint: <ABSOLUTE PATH TO CHECKPOINT.md>
Follow the quota-aware-continuation skill's "Tick procedure". If the skill is not
installed: read the checkpoint and run `python <SKILL_DIR>/scripts/qac.py tick <checkpoint>`;
stop unless it says go. Then continue from "Next action", checking usage before every
step and updating the checkpoint after every step; pause at 95% of the 5-hour or weekly
window. Never shut down the computer. Reply in <language>.
```

## Work loop

At the start of a working run, record it: `status: in_progress`, `run_session:` this
session's id (desktop: `mcp__ccd_session_mgmt__get_session` with `"self"`), `updated:` now.
Then, for each remaining step:

1. **Check usage.** Desktop: `mcp__ccd_session_mgmt__get_usage`, save the JSON to a temp
   file, run `qac.py decide --usage-json <file>` (add `--threshold`, `--weekly-threshold`
   if the user changed them). It looks at the 5-hour window and the weekly windows.
   - `continue` → do the step.
   - `pause` → "Pause procedure" (it also prints `resume_after` and `limited_by`).
   - `unknown` (no usage tool) → keep going; pause only on a rate-limit error.
2. **Do one step completely.** No half-written files: temp file + rename, or
   `qac.py write <path>` (stdin → atomic replace).
3. **Update the checkpoint**: step to Done with evidence, new Next action,
   `updated:` now. A fresh `updated` is the lock that keeps the gate closed for others.

All steps done → "Finish procedure".

## Pause procedure

1. Finish or roll back the current step. No half-written files.
2. Checkpoint: `status: paused`, `resume_after:` from `decide`, `updated:` now, cycle + 1,
   Done / Remaining / Next action exact enough for a stranger. Append to Pause log which
   window hit its limit (no percentages). Write atomically, `qac.py validate`.
3. Nothing to schedule: the heartbeat is already there, and the gate holds it until
   `resume_after`. End the turn with one line: stopped at which step, resumes after when.

## Tick procedure (scheduled run)

If the gate hook is installed, a tick only gets here when there may be work.

1. Run `qac.py tick <checkpoint>`. Anything but `go` → reply in one line and stop.
2. **Was the last run stopped by the user?** If `status` is `in_progress` (stale) and
   `run_session` is set, read that session's last messages (desktop:
   `mcp__ccd_session_mgmt__list_events`, limit 3). If they contain
   `[Request interrupted by user`, set `status: hold`, `resume_after: none`, log
   "held: user stopped run <id>", and stop. No marker (crash, power loss, closed app) →
   resume normally.
3. Check usage with `decide`. `pause` → Pause procedure (sets a fresh `resume_after`).
4. Run the "Verify state with" command. If files and checkpoint disagree, trust the files
   and fix the checkpoint first.
5. Append "resumed" to Pause log and enter the work loop.

## Continue procedure (user asks to resume a held or paused task)

1. Find the checkpoint (ask only if there are several `.qac/CHECKPOINT.md` candidates).
2. Set `status: paused`, `resume_after: none`, `updated:` now, log "continued by user".
3. If the `qac-<slug>` task was deleted, create it again (START step 5).
4. Either keep working in this session (enter the work loop) or let the next heartbeat
   pick it up; ask which only if it is not obvious.

To **stop** on purpose without pressing Stop, set `status: hold` (same effect).

## Finish procedure

1. Verify the done-criteria with real evidence (tests, files, output).
2. `status: done`, `resume_after: none`, log "done". From now on the gate blocks every
   heartbeat, so it costs nothing.
3. Try to delete `qac-<slug>`. An unattended run is refused by the desktop app; then
   leave it and say so.
4. Report: what was done, cycles, evidence, and "delete the qac-<slug> task in Scheduled".

## Scheduling by platform

| Platform | Scheduler | Usage query | Status |
|---|---|---|---|
| Claude Code **desktop app** | Recurring scheduled task created by the live session + gate hook | `mcp__ccd_session_mgmt__get_usage` (5-hour + weekly) | Tested |
| Claude Code desktop app | `CronCreate` (session cron, even `durable`) | | **Does not fire**. Do not use |
| Claude Code **CLI** | OS scheduler (`schtasks`, `at`, cron) running `claude -p "<prompt>"`; the gate hook works there too | none → `unknown` | Not tested here |
| Codex CLI / other agents | OS scheduler running the agent's non-interactive command; gate logic via `qac.py tick` | none known → `unknown` | Not tested here |
| ChatGPT web | none for local files | | Not supported |

## Known pitfalls

- **`CronCreate` does not fire in the Claude desktop app** (2026-10-16: durable one-shot
  job, process alive, machine awake, nothing ran).
- **Unattended runs cannot create, change or delete scheduled tasks** in the desktop app.
  That is why the heartbeat is created once by the live session, and why a finished task
  cannot remove itself; the gate makes the leftover free until the user deletes it.
- **Permission prompts stall scheduled runs.** A task stores the creating session's mode
  only when created in a turn the user typed (no background work or session messages in
  that turn). Editing the mode in the task editor did not take effect in our test.
- **Each run is a new session** in the creating session's folder: self-contained prompt,
  absolute paths.
- **The desktop app must be open and the machine awake.** Missed runs fire on next launch.
- **Weekly limit.** If the weekly window runs out before the 95% check catches it, model
  calls fail; the gate keeps later heartbeats free once `resume_after` is set, but a run
  that dies mid-step leaves `in_progress` (stale) and the next allowed tick re-verifies
  the files.
- **Stop detection depends on the transcript marker** `[Request interrupted by user`. If
  the app changes it, Stop is treated like a crash (the task resumes); use "hold" instead.
- **Fire time is approximate**: recurring tasks add a deterministic delay of minutes.
- **`resetsAt` is UTC (`...Z`).** Let `qac.py` do time math.
- **Never shut down or sleep the machine automatically.** It kills services, can corrupt
  files being written, and prevents the resume.
- **Other writers.** Record them under Constraints and re-verify state on every tick.
