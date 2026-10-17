# End-to-end test record

Machine: Windows 11, Claude Code desktop app, Pro plan, 2026-10-16 (UTC+8).
The demo tasks write small files in steps. To trigger pauses without burning quota,
usage is still queried before each step, but `qac.py decide --force-pause` simulates
reaching the threshold at fixed points. Usage numbers are not recorded.

## Run 1: one-shot chain (`run1-oneshot/`, log `evidence/run1-oneshot-log.md`)

Goal: 5 parts + `result.txt`; forced pauses after step 2 and step 4.

| Time | What happened |
|---|---|
| 09:27 | Live session: steps 1-2, forced pause, checkpoint written and validated, one-shot task scheduled for 09:33 |
| 09:33:53 | Task fired on time (~1 min late). The new session loaded the skill, then **waited at its first `Read` on a permission prompt**: the task had been created from a turn started by another session, so no permission mode was stored and the run used default mode |
| 09:52:54 | Re-armed run: same result. Setting Auto in the app's task editor did not end up in the stored task |
| 10:10:54 | New task: same result (the creating turn also contained a background-task notification) |
| 12:31:55 | Task re-created from a turn the user typed, session in Bypass mode → stored as Bypass. The run resumed from the checkpoint, did steps 3-4, hit the forced pause, and tried to re-arm itself: **refused** (unattended runs cannot change scheduled tasks). It logged that, continued, did steps 5-6, set `status: done`; deleting the task was refused too |
| 12:36 | Live session deleted the leftover task |

Result: the checkpoint → scheduled trigger → fresh session → finish chain works, and
`result.txt` has 5 lines in order across 3 sessions. The one-shot chain design itself
does not work in the desktop app, because a run cannot schedule its successor. That led
to the heartbeat design.

## Run 2: heartbeat (`run2-heartbeat/`, log `evidence/run2-heartbeat-log.md`)

Goal: 4 parts + `result.txt`; forced pause after step 1 (live) and after step 2 (tick 1).
Recurring task `*/5 * 16-16 10 *` created from a user-typed turn in a Bypass session.

| Time | What happened |
|---|---|
| 12:37 | Live session: step 1, forced pause, created heartbeat `qac-demo2` |
| 12:44 | Tick 1: read checkpoint (paused), usage below threshold, verified files, step 2, forced pause (ended turn) |
| 12:49 | Tick 2: resumed at step 3, steps 3-4, `result.txt` 4 lines in order, `status: done` |
| 12:50-13:42 | No ticks fired (the app was not dispatching during this gap; the cause was not investigated) |
| 13:42 | Another tick fired against the `done` checkpoint; the live session deleted `qac-demo2` while it was running, so its no-op behaviour was not recorded |

Result: the full loop (pause → later tick resumes → pause again → resume → finish) runs
unattended, with no scheduler changes needed from inside a run.

## Run 3: gate hook, Stop → hold → continue (`run3-gate/`, logs `evidence/run3-gate-log.md`, `evidence/run3-gate-hook.log`)

Current design. Recurring task `*/5 * * * *` (test interval), gate hook installed,
`lock_minutes: 3` so a stopped run is noticed quickly. Step 2 sleeps 4 minutes so there
is time to press Stop during it. 2026-10-17:

| Time | Gate | What happened |
|---|---|---|
| 16:11 | | Live session: step 1, paused with `resume_after` 16:19:32, created `qac-demo3` |
| 16:19:38 | allow | Reset time passed: run recorded its `run_session`, started step 2 |
| 16:20:54 | | Live session pressed Stop on that run (same as the user's Stop button) |
| 16:21:53 | block | "another run is active": lock still fresh. The run shows **0 turns**: no model call |
| 16:29:34 | allow | Lock expired. The run read the previous run's transcript, found `[Request interrupted by user`, set `status: hold` |
| 16:34:34 | block | "held by the user": 0 turns |
| 16:35 | | Live session applied the Continue procedure (`status: paused`) |
| 16:39:34 | allow | Resumed, redid step 2 (4 min), step 3, `result.txt` 3 lines, `status: done` |
| 16:44 | | No run dispatched while the previous run of the same task was still working |
| 16:49:34 | block | "task is done": 0 turns |

Not covered by a live run: blocking until a real `resume_after` after hitting 95% (the
first tick arrived 6 s after the simulated reset time), and a real weekly-limit pause.
Both use the same gate rule, which the unit tests cover.

## Reproduce

```bash
python -m unittest discover -s tests
```

For the live test: install the skill, open a session in Auto or Bypass mode, then ask
the agent to set up a demo like `run2-heartbeat/.qac/CHECKPOINT.md` with a 5-minute
heartbeat. Wait for the ticks, then check the log and delete the task.
