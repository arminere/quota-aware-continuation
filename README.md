# quota-aware-continuation

[中文说明](README.zh-CN.md)

An agent skill for long tasks that outlast a usage window. Before you go to sleep, tell
your agent to use it. It works while watching the 5-hour and weekly limits. When either
is about 95% used it saves a checkpoint and stops. It picks the task up again after the
reset, and keeps going until the task is done.

```
you leave ─ checkpoint + heartbeat task (every 30 min) + gate hook
          ─ work ─ usage ≥ 95% ─ checkpoint (resume_after = reset time), stop
heartbeat ─ gate hook reads the checkpoint before any model call:
            done / held / before reset / another run active → blocked, costs nothing
            otherwise → new session reads checkpoint, verifies files, keeps working
you press Stop on a run ─ next heartbeat sees it ─ task held until you say "continue"
```

## How it behaves

| Situation | What happens |
|---|---|
| 5-hour window ~95% used | Saves the checkpoint and stops; resumes about 5 minutes after the reset (heartbeat every 30 min) |
| Weekly window ~95% used | Same, until the weekly reset; it does not keep checking the 5-hour window meanwhile |
| You press Stop on a run | The task is held. Heartbeats are blocked until you tell any session "continue the xx task" |
| Power loss, app closed, crash | Not treated as Stop: it resumes on the next heartbeat after the app is back |
| Task finished | Every later heartbeat is blocked before the model runs. Delete the `qac-<name>` task in Scheduled when you are back |

The heartbeat has no end date, so a task that takes longer than two days keeps going.

## Why it is built this way

- In the Claude desktop app, an unattended scheduled run **cannot create, change or
  delete scheduled tasks**. A run therefore cannot schedule its successor or remove
  itself when done. One recurring task is created while you are present instead.
- To keep idle heartbeats free, a `UserPromptSubmit` hook (`qac_gate.py`) runs before
  the model is called. It only acts on this skill's heartbeat prompts and blocks them
  when there is nothing to do. A blocked heartbeat shows up as a "0 turns" run.

## Install

```bash
git clone https://github.com/arminere/quota-aware-continuation
cp -r quota-aware-continuation/skills/quota-aware-continuation ~/.claude/skills/
python ~/.claude/skills/quota-aware-continuation/scripts/qac.py install-hook
```

`install-hook` adds the gate to `~/.claude/settings.json` and keeps a backup
(`settings.json.qac-backup`). `uninstall-hook` removes it. The skill also offers to
install it the first time you use it.

As a Claude Code plugin: `/plugin marketplace add arminere/quota-aware-continuation`,
then `/plugin install quota-aware-continuation@quota-aware-continuation`, then run
`install-hook` as above.

Codex and other agents that read `SKILL.md` folders: copy the folder into their skills
directory. Python 3.8+ is required.

## Before you leave

- Keep the Claude desktop app open and the computer awake and plugged in.
- Use the skill from a message you type yourself, with the session in Auto (or Bypass)
  mode. The heartbeat task inherits that mode; otherwise runs stop at the first
  permission prompt. Alternative: `"permissions": {"defaultMode": "auto"}` in
  `~/.claude/settings.json`.
- When you're back and the task is done, delete the `qac-<name>` task in Scheduled.
  Leftover heartbeats cost no usage, but each one adds an empty run to the list.

## Platform support

| Platform | Status |
|---|---|
| Claude Code desktop app (Windows) | Tested end to end: pause/resume, gate blocking, Stop → hold → continue |
| Claude Code desktop app, `CronCreate` | Does not fire; not used |
| Claude Code CLI via OS scheduler (`claude -p`) | Documented, not tested |
| Codex CLI and similar | Documented, not tested |
| ChatGPT web | Not supported (no local files) |

Details and pitfalls: [SKILL.md](skills/quota-aware-continuation/SKILL.md). Test record:
[tests/e2e/README.md](tests/e2e/README.md).

## License

MIT
