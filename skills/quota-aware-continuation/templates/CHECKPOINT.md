# Continuation checkpoint

status: in_progress
updated: <FILL ISO 8601 with offset, e.g. 2026-10-16T23:40:00+08:00>
threshold: 95
cycle: 0
task_slug: <FILL short-kebab-name; the scheduled task id is qac-<slug>>

## Goal

<FILL One paragraph: what "done" means, in words a fresh session with no memory can check.>

## Resume entry

- Working directory: <FILL absolute path>
- Read first: <FILL files to read before acting, e.g. AGENTS.md, plan.md>
- Verify state with: <FILL command that shows where things stand, e.g. `git status && ls out/`>

## Done

<!-- One line per finished item, with the evidence (file, commit, test output). -->
- (nothing yet)

## Remaining steps

<!-- Ordered. Each step small enough to finish well inside one quota window. -->
1. <FILL>

## Next action

<!-- The exact next command or edit. If a step was interrupted, say how to redo it safely. -->
<FILL>

## Constraints

<!-- User preferences, things not to touch, other writers on the same files, language. -->
- Do not shut down or sleep the machine.
- <FILL>

## Scheduled resume

<!-- Filled when pausing; cleared to "none" when done and the task is deleted. -->
- platform: none
- task_id: none
- fire_at: none

## Pause log

<!-- Append one line per pause/resume: time, cycle, reason, step reached. No usage numbers needed. -->
