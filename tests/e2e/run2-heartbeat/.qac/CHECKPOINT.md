# Continuation checkpoint

status: done
updated: 2026-10-16T12:49:51+08:00
threshold: 95
cycle: 2
task_slug: demo2

## Goal

Heartbeat demo for the quota-aware-continuation end-to-end test. Done when
parts/part1.txt .. parts/part4.txt exist (one line each) and result.txt is their
concatenation in order (4 lines).

## Resume entry

- Working directory: <repo>/tests/e2e/run2-heartbeat
- Read first: this file, then ../evidence/run2-heartbeat-log.md
- Verify state with: `ls parts/ && cat result.txt 2>/dev/null` (Git Bash)

## Done

- Step 1: parts/part1.txt (live session)
- Step 2: parts/part2.txt (tick 1, cycle 1)
- Step 3: parts/part3.txt (tick 2, cycle 2)
- Step 4: parts/part4.txt + result.txt (tick 2, cycle 2); result.txt has 4 lines, byte-identical to cat parts/part1..4

## Remaining steps

None.

## Next action

None. Task done. Live session/user: delete scheduled task qac-demo2.

## Constraints

- Do not shut down or sleep the machine.
- TEST MODE: still check usage before each step, but after finishing step 2 follow the
  Pause procedure once with `decide --force-pause --hide-percent` (check Pause log so it
  happens only once). Heartbeat strategy: pausing means ending the turn, no scheduling.
- Do not try to create, update or delete scheduled tasks; the live session handles that.
- After every tick start, step, pause and finish, append one line to
  ../evidence/run2-heartbeat-log.md: "<local time> | <event>". Never write usage numbers.
- Touch nothing outside <repo>/tests/e2e/.

## Scheduled resume

- platform: claude-desktop scheduled task, heartbeat
- task_id: qac-demo2
- schedule: */5 * 16-16 10 * (every 5 min, 16 Oct only; delete afterwards)
- left over: task qac-demo2 still exists (unattended run cannot delete it); remaining ticks only read status: done and stop

## Pause log

- 2026-10-16T12:37:34+08:00 cycle 0: step 1 done in live session; forced test pause
- 2026-10-16T12:44:15+08:00 cycle 1: resumed (tick 1)
- 2026-10-16T12:44:27+08:00 cycle 1: step 2 done; forced test pause (once, done)
- 2026-10-16T12:49:32+08:00 cycle 2: resumed (tick 2)
- 2026-10-16T12:49:51+08:00 cycle 2: done (tick 2)
