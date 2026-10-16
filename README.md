# quota-aware-continuation

[中文说明](README.zh-CN.md)

An agent skill for long tasks that outlast a usage window. Before you go to sleep, tell
your agent to use it. The agent works while it watches the 5-hour usage limit. Before
the limit runs out it writes a checkpoint and stops. A scheduled run then starts a fresh
session, which reads the checkpoint, checks usage and carries on. This repeats until the
task is done.

```
you leave ─ agent writes checkpoint ─ creates a date-bound heartbeat task (every 30 min)
          ─ works ─ usage ≥ 95% ─ checkpoint, stop
tick (new session) ─ read checkpoint ─ done? stop │ busy? stop │ usage high? stop
                   ─ verify files ─ work ─ checkpoint after every step ─ ...
you return ─ task done ─ delete the heartbeat task
```

## Why a heartbeat, not "schedule the next run"

The obvious design is for each run to schedule its own successor at reset + 5 min. We
built and tested that first. In the Claude desktop app it does not work: **an unattended
scheduled run is not allowed to create, change or delete scheduled tasks.** So the
schedule is set up once, while you are present. It is a recurring task limited to the
next few days, and each tick decides for itself whether there is work to do.

## What's inside

| Path | What |
|---|---|
| `skills/quota-aware-continuation/SKILL.md` | The skill: strategies, procedures, scheduled-run prompt, platform table, pitfalls |
| `skills/quota-aware-continuation/templates/CHECKPOINT.md` | Checkpoint template a memory-less session can resume from |
| `skills/quota-aware-continuation/scripts/qac.py` | Stdlib Python helper: `decide`, `tick`, `heartbeat`, `write` (atomic), `validate`, `now` |
| `.claude-plugin/` | Claude Code plugin and marketplace manifests |
| `tests/test_qac.py` | Unit tests for the helper |
| `tests/e2e/` | Two real end-to-end runs on Windows with the Claude desktop app, with logs |

## Install

**Claude Code, as a personal skill:**

```bash
git clone https://github.com/arminere/quota-aware-continuation
cp -r quota-aware-continuation/skills/quota-aware-continuation ~/.claude/skills/
```

**Claude Code, as a plugin:**

```
/plugin marketplace add arminere/quota-aware-continuation
/plugin install quota-aware-continuation@quota-aware-continuation
```

**Codex and other agents that read `SKILL.md` folders:** copy the same folder into the
agent's skills directory (for example `~/.agents/skills/` or `~/.codex/skills/`), or
point the agent at `SKILL.md`. The helper needs Python 3.8+.

## Use

> I'm going to sleep. Use quota-aware-continuation to finish the migration in `D:/work/app`;
> pause at 95% and resume after the reset.

Before you leave, make sure scheduled runs won't stop at permission prompts. In the
Claude desktop app, either run this session in Auto or Bypass mode and let the agent
create the task in a message you typed, or set `"permissions": {"defaultMode": "auto"}`
in `~/.claude/settings.json`. When you're back, delete the `qac-<name>` task if it is
still listed.

## Platform support

| Platform | Scheduler | Usage query | Status |
|---|---|---|---|
| Claude Code desktop app | Recurring scheduled task created by the live session (heartbeat) | `get_usage` (5-hour window) | **Tested end to end** |
| Claude Code desktop app | One-shot `fireAt` task | | Fires, but a run can't schedule the next one |
| Claude Code desktop app | `CronCreate` session cron | | **Does not fire** |
| Claude Code CLI | OS scheduler (`schtasks`, `at`, cron) running `claude -p` | none, falls back to "pause on rate-limit error" | Documented, not tested |
| Codex CLI and similar | OS scheduler running the agent's non-interactive command | none known, same fallback | Documented, not tested |
| ChatGPT web | none for local files | | Not supported |

## Known pitfalls (found on a real machine)

- `CronCreate` jobs in the Claude desktop app did not fire, even when durable.
- Unattended scheduled runs cannot create, change or delete scheduled tasks.
- A scheduled run starts in the permission mode stored on the task. It stores the
  creating session's mode only if the task was created in a message the user typed.
  Otherwise the run waits at its first permission prompt (we hit this three times).
- Each run is a brand-new session in the creating session's folder: the prompt must be
  self-contained with absolute paths.
- Tasks run only while the desktop app is open; keep the machine awake.
- Cron lines match again next year on the same dates; delete the task after use.
- Never shut the machine down automatically: it kills running services and can corrupt
  files being written.

Full details: [SKILL.md](skills/quota-aware-continuation/SKILL.md). Test record:
[tests/e2e/README.md](tests/e2e/README.md).

## License

MIT
