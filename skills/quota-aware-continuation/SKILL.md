---
name: quota-aware-continuation
description: Keep a long task going across usage-limit windows while the user is away. Use when the user says they are going to sleep / stepping away and wants a long task to keep running, asks to "pause at 95% and resume after the reset", "continue after the 5-hour limit resets", "额度快用完时暂停、重置后自动续跑", or when a session is started by a scheduled task whose prompt names a quota-aware-continuation checkpoint (TICK mode).
---

# Quota-aware continuation

Work on a long task in cycles. Watch the plan usage; before it runs out, write a
checkpoint and stop. A scheduler starts a **brand-new session** later (no memory). It
reads the checkpoint, checks usage, and carries on. Repeat until done, then remove the
schedule.

`scripts/qac.py` (Python 3 stdlib) does the fiddly parts: the pause decision, time math,
schedule expressions, atomic writes, checkpoint validation. Run it with `python` (or
`python3`). `SKILL_DIR` below means the directory containing this file.

## Two scheduling strategies

| Strategy | When | How the next run happens |
|---|---|---|
| **Heartbeat** (default for the Claude desktop app) | The scheduler can only be changed by the live user session | One recurring task, created at START while the user is present, fires every N minutes for the next few days. Each run is a "tick". Pausing is just ending the turn. |
| **One-shot chain** | A shell-level scheduler the agent can drive itself (`schtasks`, `at`, cron with `claude -p` / `codex exec`) | On pause, the run schedules exactly one resume at reset + delay. |

Why heartbeat in the desktop app: an unattended scheduled run **cannot create, change or
delete scheduled tasks** (the app refuses those actions when nobody has opened the run;
observed 2026-10-16). A run therefore cannot schedule its own successor. Everything about
the schedule must be set up while the user is there.

## Modes

- **START**: the user invokes the skill in a live session. Set up checkpoint + schedule, then work.
- **TICK**: the session was started by a scheduled task whose prompt points at a
  checkpoint. Go to "Tick procedure".

## Settings (ask only if the user has not said; otherwise use defaults)

| Setting | Default |
|---|---|
| threshold | 95 (% of the 5-hour window) |
| heartbeat interval | 30 minutes |
| heartbeat lifetime | 2 days (the cron only matches those dates) |
| one-shot resume delay | 5 minutes after `resetsAt` |
| checkpoint path | `<working dir>/.qac/CHECKPOINT.md` |
| lock freshness | 20 minutes (a run whose checkpoint `updated` is newer is presumed active) |

Use a lower threshold (e.g. 90) if single steps are large: usage keeps rising while a
step runs, and you need room to finish it and write the checkpoint.

## START procedure (user present)

1. Confirm the goal and done-criteria in one short message, only if unclear. The user is
   about to leave: do not ask what you can decide.
2. **Make unattended runs possible.** A scheduled run must not stop at a permission
   prompt (see pitfalls). In the Claude desktop app, either this session is in Auto or
   Bypass mode **and** you create the task in a turn the user typed (the task then
   stores the mode; confirm the tool result says so), or the user sets
   `"permissions": {"defaultMode": "auto"}` in `~/.claude/settings.json`. Fix this now,
   while the user is here.
3. Copy `SKILL_DIR/templates/CHECKPOINT.md` to the checkpoint path, fill every
   `<FILL ...>`, split the work into small ordered steps, and run
   `python SKILL_DIR/scripts/qac.py validate <checkpoint>`.
4. **Create the schedule** with the prompt below.
   - Heartbeat: `python SKILL_DIR/scripts/qac.py heartbeat --every 30 --days 2` prints a
     cron expression limited to those dates. Desktop app:
     `mcp__scheduled-tasks__create_scheduled_task` with `cronExpression`, id
     `qac-<task_slug>`.
   - One-shot chain: nothing yet; it is scheduled on the first pause.
   Record platform, task id and schedule under "Scheduled resume".
5. Keep the machine awake if possible (desktop: `mcp__ccd_host__request_keep_awake`).
   Never shut it down.
6. Tell the user in two lines: what will run, how often, until when, and that they
   should delete the task when they are back if it is still listed. Then enter the
   work loop.

### Scheduled-run prompt (must be self-contained)

```
Continue a long task (quota-aware-continuation, TICK mode).
Checkpoint: <ABSOLUTE PATH TO CHECKPOINT.md>
If the quota-aware-continuation skill is installed, follow its "Tick procedure".
If not: read the whole checkpoint. If status is done, reply "done" and stop. If status
is in_progress and `updated` is less than 20 minutes old, another run is active: stop.
Check plan usage if you have a tool for it; at or above <T>% of the 5-hour window,
set status: paused, log it, and stop. Otherwise verify the state with the "Resume entry"
command and continue from "Next action", updating the checkpoint after every step,
until done or usage reaches <T>%. Never shut down the computer. Reply in <language>.
```

## Work loop

For each remaining step:

1. **Check usage.** Desktop: call `mcp__ccd_session_mgmt__get_usage`, save the result to
   a temp file, run `python SKILL_DIR/scripts/qac.py decide --usage-json <file> --threshold <T>`
   (or `decide --percent 87 --resets-at 2026-10-16T02:50:00Z`). Watch the "5-hour" window.
   - `continue` → do the step.
   - `pause` → "Pause procedure".
   - `unknown` (no usage tool, API billing) → keep going, checkpoint after every step,
     pause only on a rate-limit error.
2. **Do one step completely.** No half-written files: write to a temp file and rename,
   or `qac.py write <path>` (stdin → atomic replace).
3. **Update the checkpoint** (step to Done with evidence, new Next action, `updated:` now,
   `status: in_progress`), atomically. The fresh `updated` is also the lock that stops
   an overlapping tick.

When all steps are done → "Finish procedure".

## Pause procedure

1. Finish or roll back the current step. No half-written files.
2. Checkpoint: `status: paused`, `updated:` now, cycle + 1, Done / Remaining / Next
   action exact enough for a stranger. Write atomically, `qac.py validate`.
3. Heartbeat: nothing to schedule; the next tick resumes. One-shot chain: schedule one
   run at `fire_at` from `qac.py decide` (id `qac-<task_slug>`; cron schedulers get
   `fire_at_cron_local`), record it under "Scheduled resume".
4. Append a line to "Pause log". Say where it stopped and when it should resume. End
   the turn.

## Tick procedure (scheduled run)

1. Read the whole checkpoint.
   - `status: done` → reply "done, nothing to do" and stop (try to delete the task; if
     the app refuses, leave it for the user).
   - `status: in_progress` and `updated` younger than the lock freshness → another run
     is active; stop.
2. Check usage with `decide`. `pause` → if status was `in_progress`, set `paused`; log;
   stop. No work.
3. Run the "Verify state with" command. If files and checkpoint disagree (a step done
   but not recorded), trust the files and fix the checkpoint first.
4. Set `status: in_progress`, append "resumed" to Pause log, enter the work loop.

## Finish procedure

1. Verify the done-criteria with real evidence (tests, files, output).
2. `status: done`, append "done" to Pause log, Scheduled resume: note what is left.
3. Remove the schedule: delete `qac-<task_slug>` (and any `qac-<task_slug>-*`). In the
   desktop app an unattended run is refused; then leave it. The bounded heartbeat stops
   matching after its last date, and remaining ticks only read the checkpoint and stop.
   The next live session, or the user, deletes it. Cron entries must always be deleted:
   date-bound cron lines match again next year.
4. Report: what was done, how many cycles, where the evidence is, and whether the task
   still needs deleting.

## Scheduling by platform

| Platform | Scheduler | Usage query | Status |
|---|---|---|---|
| Claude Code **desktop app** | Recurring scheduled task (`create_scheduled_task` + `cronExpression`), created by the live session: heartbeat | `mcp__ccd_session_mgmt__get_usage` | Tested: triggers, resume from checkpoint, refused self-reschedule |
| Claude Code desktop app | One-shot `fireAt` task | | Fires reliably, but a run cannot re-arm or create the next one, so it covers one pause only |
| Claude Code desktop app | `CronCreate` (session cron, even `durable`) | | **Does not fire**. Do not use |
| Claude Code **CLI** | OS scheduler running `claude -p "<prompt>"`: Windows `schtasks /create /sc once`, macOS/Linux `at`, or a cron line; one-shot chain | none built in → `unknown` | Not tested here |
| Claude Code cloud routines (`/schedule`) | cloud cron | | Runs in the cloud, cannot see local files |
| Codex CLI / other agents | OS scheduler running `codex exec "<prompt>"` or the agent's non-interactive command | none known → `unknown` | Not tested here |
| ChatGPT web | none for local files | | Not supported |

## Known pitfalls

- **`CronCreate` does not fire in the Claude desktop app.** 2026-10-16: a durable one-shot
  job for 02:07 stayed in `.claude/scheduled_tasks.json`; process alive, machine awake,
  nothing ran.
- **Unattended runs cannot touch the scheduler (desktop app).** Creating, updating or
  deleting scheduled tasks is refused when nobody has opened the run. Observed
  2026-10-16: re-arming and deleting both refused. Hence the heartbeat strategy.
- **Scheduled runs and permission prompts.** A run that hits a permission prompt waits
  for a human. Observed three times on 2026-10-16: runs fired on time, then waited at
  their first `Read`. A task stores the creating session's mode only when created in a
  turn the user typed, with no background work or other-session message in that turn;
  the tool result says which mode was saved. Changing the mode in the app's task editor
  did not end up in the stored task in our test. Reliable options: create the task from
  an Auto/Bypass session in a user-typed turn, or set `defaultMode: auto` globally.
- **A scheduled task starts a brand-new session** in the creating session's folder: the
  prompt must be self-contained, use absolute paths, and work outside that folder may
  need approval.
- **The desktop app must be open.** Tasks run only while it runs; a missed run fires on
  next launch. Sleep delays everything: keep the machine awake.
- **Fired one-shot tasks stay listed, disabled**, until deleted.
- **Cron lines repeat.** `7 2 16 10 *` fires every 16 Oct; a date-bound heartbeat fires
  again next year on the same dates. Delete after use.
- **Fire time is approximate.** One-shot: about one minute late. Recurring tasks add a
  deterministic delay of several minutes.
- **`resetsAt` is UTC (`...Z`); schedulers want local time or an offset.** Use `qac.py`.
- **Usage keeps rising during a step.** Check before each step; keep steps small.
- **Overlapping ticks.** A long work session can still be running when the next tick
  fires. The fresh-`updated` lock handles this; keep updating the checkpoint.
- **Never shut down or sleep the machine automatically.** It kills services, can corrupt
  files being written, and prevents the resume.
- **Other writers.** Record them under Constraints and re-verify state on every tick.
