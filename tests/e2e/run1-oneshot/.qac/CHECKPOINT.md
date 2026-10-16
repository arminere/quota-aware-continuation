# Continuation checkpoint

status: done
updated: 2026-10-16T12:33:04+08:00
threshold: 95
cycle: 2
task_slug: demo

## Goal

Demo task for the quota-aware-continuation end-to-end test. Done when
parts/part1.txt .. parts/part5.txt exist (each one line "part N, cycle C, <time>"),
result.txt is their concatenation in order, and no scheduled task whose id starts
with qac-demo- remains.

## Resume entry

- Working directory: <repo>/tests/e2e/demo-run
- Read first: this file, then ../evidence/log.md
- Verify state with: `ls parts/ && cat result.txt 2>/dev/null` (Git Bash)

## Done

- Step 1: parts/part1.txt (cycle 0)
- Step 2: parts/part2.txt (cycle 0)
- Step 3: parts/part3.txt (cycle 1)
- Step 4: parts/part4.txt (cycle 1)
- Step 5: parts/part5.txt (cycle 2)
- Step 6: result.txt = parts 1-5, 5 lines in order (cycle 2)

## Remaining steps

none

## Next action

none (done). Manual cleanup left: delete disabled one-shot task qac-demo in the app (unattended run may not delete it).

## Constraints

- Do not shut down or sleep the machine.
- TEST MODE: still call get_usage and decide before each step, but after finishing step 2
  and after finishing step 4 run decide with `--force-pause --resume-in-minutes 3 --hide-percent`
  and follow the Pause procedure (each forced pause happens once; check Pause log).
- After every step and every pause/resume, append one line to ../evidence/log.md:
  "<local time> | cycle <n> | <event>". Never write usage percentages anywhere.
- Touch nothing outside <repo>/tests/e2e/.

## Scheduled resume

none (qac-demo fired and is disabled; deletion pending user)

## Pause log

- 2026-10-16T09:27:08+08:00 cycle 0: started by the live session
- 2026-10-16T09:27:40+08:00 cycle 0: forced test pause after step 2; resume qac-demo-c1 at 09:33
- 2026-10-16T09:48:04+08:00 cycle 1: first run blocked on a permission prompt and was stopped; task set to Auto by the user and re-armed for 2026-10-16T09:52:00+08:00
- 2026-10-16T10:00:30+08:00 cycle 1: re-armed run also started in default mode (Auto not saved on task); stopped it, replaced qac-demo-c1 with qac-demo created in a user-typed turn, fire 2026-10-16T10:04:00+08:00
- 2026-10-16T12:27:50+08:00 cycle 1: recreated qac-demo from a user-typed turn of a bypass-mode session, fire 2026-10-16T12:31:00+08:00
- 2026-10-16T12:32:37+08:00 cycle 1: resumed by qac-demo (auto, no prompt); steps 3-4 done
- 2026-10-16T12:32:37+08:00 cycle 2: forced test pause after step 4; re-armed qac-demo for 2026-10-16T12:36:00+08:00
- 2026-10-16T12:33:04+08:00 cycle 2: re-arm refused (needs human approval in unattended run), so did not pause; steps 5-6 done in same session
- 2026-10-16T12:33:04+08:00 cycle 2: done; delete_scheduled_task(qac-demo) also refused, left disabled for user to delete; no qac-demo-* tasks remain
