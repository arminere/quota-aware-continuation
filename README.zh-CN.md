# quota-aware-continuation（额度感知的长任务续跑）

[English](README.md)

给超过一个额度窗口的长任务用的 agent skill。睡前让 agent 调用它，它会一边干活一边盯着 5 小时额度和周额度：任意一个用到 95% 左右，就存好断点停下；额度重置后自动接着做，直到任务完成。

```
你离开 ─ 写断点 + 心跳任务（每 30 分钟）+ 门卫 hook
       ─ 干活 ─ 额度 ≥ 95% ─ 写断点（resume_after = 重置时间），停下
心跳   ─ 门卫在调用模型之前先读断点：
         已完成 / 已暂停 / 未到重置时间 / 另一轮在跑 → 直接拦下，不花额度
         否则 → 新会话读断点、核对文件、接着干
你点了停止 ─ 下一轮心跳发现 ─ 任务暂停，直到你说"继续"
```

## 行为一览

| 情况 | 会怎样 |
|---|---|
| 5 小时额度用到约 95% | 存断点、停下；重置后约 5 分钟恢复（心跳每 30 分钟检查一次，所以最多晚半小时左右） |
| 周额度用到约 95% | 同样停下，直到周额度重置；这期间也不再去查 5 小时额度 |
| 你在某次运行上点了停止 | 任务进入暂停，之后的心跳全部被拦，直到你在任意会话里说"继续 xx 任务" |
| 断电、关了应用、崩溃 | 不算"停止"：应用重新打开后，下一轮心跳会接着做 |
| 任务完成 | 之后的心跳都在调用模型前被拦下；回来后在 Scheduled 里删掉 `qac-<名字>` 任务即可 |

心跳没有截止日期，任务跑两天以上也会一直往下做。

## 为什么这样设计

- Claude 桌面版里，无人值守的定时运行**无权创建、修改或删除定时任务**。所以运行没法给自己排下一轮，也没法在完成后删掉自己。只能在你在场时一次性建好一个循环任务。
- 为了让空闲心跳不花额度，用了一个 `UserPromptSubmit` hook（`qac_gate.py`）。它在模型被调用之前运行，只处理本 skill 的心跳消息，没事可做时直接拦下。被拦下的心跳在运行记录里显示为 "0 turns"。

## 安装

```bash
git clone https://github.com/arminere/quota-aware-continuation
cp -r quota-aware-continuation/skills/quota-aware-continuation ~/.claude/skills/
python ~/.claude/skills/quota-aware-continuation/scripts/qac.py install-hook
```

`install-hook` 会把门卫加进 `~/.claude/settings.json`，并保留备份 `settings.json.qac-backup`；用 `uninstall-hook` 可以移除。你第一次用这个 skill 时，它也会提出帮你安装。

也可以作为 Claude Code 插件安装：先 `/plugin marketplace add arminere/quota-aware-continuation`，再 `/plugin install quota-aware-continuation@quota-aware-continuation`，然后照上面运行 `install-hook`。

Codex 等读取 `SKILL.md` 目录的 agent：把这个目录复制到它的 skills 目录即可。需要 Python 3.8 及以上。

## 离开前确认

- Claude 桌面应用开着，电脑不睡眠、插着电。
- 调用 skill 的那句话要你自己亲手发，会话开 Auto（或 Bypass）模式。心跳任务会继承这个模式；否则每次运行都会卡在第一个权限确认上。另一种办法是在 `~/.claude/settings.json` 里设 `"permissions": {"defaultMode": "auto"}`。
- 回来后如果任务已完成，去 Scheduled 里删掉 `qac-<名字>` 任务。留着不花额度，但每次心跳都会在运行列表里多出一条空记录。

## 平台支持

| 平台 | 状态 |
|---|---|
| Claude Code 桌面版（Windows） | 已端到端实测：暂停恢复、门卫拦截、停止 → 暂停 → 继续 |
| Claude Code 桌面版 `CronCreate` | 到点不触发，未采用 |
| Claude Code CLI + 系统调度（`claude -p`） | 有说明，未实测 |
| Codex CLI 等 | 有说明，未实测 |
| ChatGPT 网页版 | 不支持（无法操作本地文件） |

完整流程和已知坑见 [SKILL.md](skills/quota-aware-continuation/SKILL.md)，测试记录见 [tests/e2e/README.md](tests/e2e/README.md)。

## 许可

MIT
