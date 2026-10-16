# quota-aware-continuation（额度感知的长任务续跑）

[English](README.md)

给超过一个额度窗口的长任务用的 agent skill。睡觉或离开前让 agent 调用它：agent 一边干活一边查 5 小时额度，快用完时先写断点再停下。之后由定时任务启动一个全新会话，读断点、查额度、接着做，循环到任务完成。

```
你离开 ─ agent 写断点 ─ 建一个限定日期的心跳任务（每 30 分钟）
       ─ 干活 ─ 额度 ≥ 95% ─ 写断点、停下
心跳（新会话）─ 读断点 ─ 已完成？退出 │ 有别的轮在跑？退出 │ 额度高？退出
              ─ 核对文件 ─ 干活 ─ 每步更新断点 ─ ……
你回来 ─ 任务已完成 ─ 删除心跳任务
```

## 为什么用心跳，而不是"每次暂停后排下一次"

直觉做法是每次运行结束前，自己在"重置时间 + 5 分钟"排好下一次。我们先按这个方案做了并实测，结论是在 Claude 桌面版里行不通：**无人值守的定时运行无权创建、修改或删除定时任务。** 所以调度只能在你在场时一次性建好：一个只在接下来几天内匹配的循环任务，每次触发时自己判断有没有活要干。

## 内容

| 路径 | 说明 |
|---|---|
| `skills/quota-aware-continuation/SKILL.md` | skill 本体：两种调度方案、各步骤流程、定时运行 prompt、平台对照、已知坑 |
| `skills/quota-aware-continuation/templates/CHECKPOINT.md` | 断点模板，无上下文的新会话也能接上 |
| `skills/quota-aware-continuation/scripts/qac.py` | 纯标准库 Python 辅助脚本：`decide`、`tick`、`heartbeat`、`write`（原子写入）、`validate`、`now` |
| `.claude-plugin/` | Claude Code 插件与 marketplace 清单 |
| `tests/test_qac.py` | 辅助脚本单元测试 |
| `tests/e2e/` | 在 Windows + Claude 桌面版上的两轮真实端到端测试及日志 |

## 安装

**Claude Code 个人 skill：**

```bash
git clone https://github.com/arminere/quota-aware-continuation
cp -r quota-aware-continuation/skills/quota-aware-continuation ~/.claude/skills/
```

**Claude Code 插件：**

```
/plugin marketplace add arminere/quota-aware-continuation
/plugin install quota-aware-continuation@quota-aware-continuation
```

**Codex 等读取 `SKILL.md` 目录的 agent：** 把同一个目录复制到该 agent 的 skills 目录（例如 `~/.agents/skills/` 或 `~/.codex/skills/`），或者直接让 agent 读 `SKILL.md`。辅助脚本需要 Python 3.8 及以上。

## 使用

> 我要去睡了。用 quota-aware-continuation 把 `D:/work/app` 的迁移做完，额度到 95% 暂停，重置后继续。

离开前要确保定时运行不会卡在权限确认上。在 Claude 桌面版里有两种做法，选一种即可：
- 让当前会话处于 Auto 或 Bypass 模式，并由 agent 在你亲手发的那条消息里创建任务；
- 或者在 `~/.claude/settings.json` 里设置 `"permissions": {"defaultMode": "auto"}`。

回来后，如果 `qac-<名字>` 任务还在列表里，把它删掉。

## 平台支持

| 平台 | 调度方式 | 额度查询 | 状态 |
|---|---|---|---|
| Claude Code 桌面版 | 由在场会话创建的循环定时任务（心跳） | `get_usage`（5 小时窗口） | **已端到端实测** |
| Claude Code 桌面版 | 一次性 `fireAt` 任务 | | 能触发，但运行里无法排下一次 |
| Claude Code 桌面版 | `CronCreate` 会话内 cron | | **到点不触发** |
| Claude Code CLI | 系统调度（`schtasks`、`at`、cron）运行 `claude -p` | 无，退化为"遇到限流报错再暂停" | 有说明，未实测 |
| Codex CLI 等 | 系统调度运行该 agent 的非交互命令 | 未知，同样退化 | 有说明，未实测 |
| ChatGPT 网页版 | 无法操作本地文件 | | 不支持 |

## 已知坑（真机实测发现）

- Claude 桌面版里的 `CronCreate` 任务（即使 durable）到点不触发。
- 无人值守的定时运行无权创建、修改或删除定时任务。
- 定时运行使用任务上保存的权限模式。只有在用户亲手发的消息那一轮里创建的任务，才会保存创建会话的模式；否则运行会停在第一个权限确认上（我们实测遇到 3 次）。
- 每次运行都是全新会话，工作目录是创建任务时那个会话的目录，所以 prompt 必须自包含，并使用绝对路径。
- 定时任务只在桌面应用打开时运行，机器要保持唤醒。
- cron 表达式到明年同一日期会再次匹配，用完必须删除任务。
- 不要自动关机：会杀掉正在运行的服务，也可能损坏正在写的文件。

完整说明见 [SKILL.md](skills/quota-aware-continuation/SKILL.md)，测试记录见 [tests/e2e/README.md](tests/e2e/README.md)。

## 许可

MIT
