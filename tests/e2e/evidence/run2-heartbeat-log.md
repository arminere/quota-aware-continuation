# E2E run 2: heartbeat strategy
2026-10-16T12:37:34+08:00 | live session: step 1 done, forced pause; creating heartbeat qac-demo2
2026-10-16T12:44:15+08:00 | tick 1 start (cycle 1): checkpoint paused, usage below threshold, state verified (part1 only); resumed
2026-10-16T12:44:27+08:00 | step 2 done: parts/part2.txt written
2026-10-16T12:44:27+08:00 | forced test pause after step 2 (cycle 1 -> 2); next tick resumes at step 3
2026-10-16T12:49:32+08:00 | tick 2 start (cycle 2): checkpoint paused, usage below threshold, state verified (part1, part2); resumed
2026-10-16T12:49:32+08:00 | step 3 done: parts/part3.txt written
2026-10-16T12:49:51+08:00 | step 4 done: parts/part4.txt + result.txt (4 lines, in order)
2026-10-16T12:49:51+08:00 | finished: status done; task qac-demo2 left for live session to delete
2026-10-16T13:44:05+08:00 | live session: a later tick fired at 13:42 against the done checkpoint; live session deleted qac-demo2
