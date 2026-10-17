# Continuation checkpoint

status: done
updated: 2026-10-17T16:44:47+08:00
threshold: 95
weekly_threshold: 95
cycle: 1
task_slug: demo3
resume_after: none
run_session: local_6b954d4d-f337-4914-bda6-bb5dcc51d50e
lock_minutes: 3

## Goal

Gate/hold demo for the quota-aware-continuation end-to-end test. Done when
parts/part1.txt .. parts/part3.txt exist and result.txt is their concatenation (3 lines).

## Resume entry

- Working directory: <repo>/tests/e2e/run3-gate
- Read first: this file, then ../evidence/run3-gate-log.md
- Verify state with: `ls parts/ && cat result.txt 2>/dev/null` (Git Bash)

## Done

- Step 1: parts/part1.txt (live session)
- Step 2: parts/part2.txt (tick local_6b954d4d, "part 2, 2026-10-17T16:44:19+08:00"; lock refreshed mid-sleep)
- Step 3: parts/part3.txt + result.txt (3 lines, verified with wc -l)

## Remaining steps

(none)

## Next action

None. Task done; user should delete scheduled task qac-demo3.

## Constraints

- Do not shut down or sleep the machine.
- TEST MODE: lock_minutes is 3 so a stopped run is detected quickly. Use the real usage check.
- Do not try to create, update or delete scheduled tasks.
- After every tick start, step, pause, hold and finish, append one line to
  ../evidence/run3-gate-log.md: "<local time> | <event>". Never write usage numbers.
- Touch nothing outside <repo>/tests/e2e/.

## Scheduled resume

- platform: claude-desktop heartbeat + gate hook
- task_id: qac-demo3
- schedule: */5 * * * * (test interval)

## Pause log

- 2026-10-17T16:11:32+08:00 cycle 0: step 1 done in live session; simulated pause with resume_after 2026-10-17T16:19:32+08:00
- 2026-10-17T16:20:18+08:00 cycle 1: resumed by heartbeat tick (session local_4a0eef4e-df7b-4d1b-b39f-2341ce3fc3ce)
- 2026-10-17T16:30:07+08:00 cycle 1: held: user stopped run local_4a0eef4e-df7b-4d1b-b39f-2341ce3fc3ce (detected by tick session local_0c1c42f7-99fa-48ab-afbc-92aacd207262)
- 2026-10-17T16:35:21+08:00 continued by user (live session): status paused, resume_after none
- 2026-10-17T16:40:09+08:00 cycle 1: resumed by heartbeat tick (session local_6b954d4d-f337-4914-bda6-bb5dcc51d50e)
- 2026-10-17T16:44:47+08:00 cycle 1: done (session local_6b954d4d-f337-4914-bda6-bb5dcc51d50e)
