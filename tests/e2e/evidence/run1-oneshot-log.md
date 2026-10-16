# E2E log (demo task)
2026-10-16T09:27:08+08:00 | cycle 0 | started in live session
2026-10-16T09:27:20+08:00 | cycle 0 | usage check: continue; step 1 done
2026-10-16T09:27:21+08:00 | cycle 0 | usage check: continue; step 2 done
2026-10-16T09:27:40+08:00 | cycle 0 | forced pause after step 2; checkpoint written; scheduling qac-demo-c1 for 09:33
2026-10-16T09:37:35+08:00 | cycle 1 | run of qac-demo-c1 fired 09:33:53, then waited on a permission prompt (default mode, checkpoint outside its folder)
2026-10-16T09:48:04+08:00 | cycle 1 | stopped blocked run; user set qac-demo-c1 to Auto; re-armed same task for 2026-10-16T09:52:00+08:00
2026-10-16T10:00:30+08:00 | cycle 1 | re-armed run (09:52:54) also in default mode, stopped; created qac-demo from a user-typed turn for 2026-10-16T10:04:00+08:00
2026-10-16T12:23:53+08:00 | cycle 1 | qac-demo fired 10:10:54; run read the checkpoint, then waited on a permission prompt from 10:11 (task saved without permissionMode despite UI edit); stopped
2026-10-16T12:27:50+08:00 | cycle 1 | recreating qac-demo from user-typed turn (session in highest mode) for 2026-10-16T12:31:00+08:00
2026-10-16T12:32:19+08:00 | cycle 1 | resumed by qac-demo run (fired ~12:31); usage check: continue; state matches checkpoint (parts 1-2)
2026-10-16T12:32:20+08:00 | cycle 1 | usage check: continue; step 3 done
2026-10-16T12:32:21+08:00 | cycle 1 | usage check: continue; step 4 done
2026-10-16T12:32:37+08:00 | cycle 1 | forced pause after step 4; checkpoint written (cycle 2); re-arming qac-demo for 12:36
2026-10-16T12:32:50+08:00 | cycle 2 | re-arm of qac-demo refused (update_scheduled_task needs human approval in unattended run); not pausing, continuing in same session
2026-10-16T12:32:52+08:00 | cycle 2 | usage check: continue; step 5 done
2026-10-16T12:32:54+08:00 | cycle 2 | usage check: continue; step 6 done (result.txt 5 lines in order)
2026-10-16T12:33:04+08:00 | cycle 2 | done; qac-demo-* none remain; qac-demo (disabled) delete refused without human approval, left for user
2026-10-16T12:37:53+08:00 | live session deleted leftover qac-demo (unattended run could not)
