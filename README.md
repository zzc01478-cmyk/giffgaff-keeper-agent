# giffgaff-keeper-agent

本地优先的 giffgaff 保号辅助工具，适合给 Agent、Codex Skill 或简单自动化使用。

它不会获取 giffgaff 官方返回的“保号有效期”。giffgaff 的核心规则是 6 个月内至少有一次合格使用，所以本工具只记录你确认过的本地保号动作，并按保守规则估算：

```text
official_expiry_at = null
estimated_expiry_at = last_activity_at + 180 days
expiry_source = estimated_from_last_activity
remind_at = estimated_expiry_at - 30 days
```

## 快速开始

```bash
python3 giffgaff_keeper.py record --date 2026-06-30 --number-hint "****1234" --evidence-note "已用 giffgaff 移动数据加载 payload" --confirm-valid-action
python3 giffgaff_keeper.py status
python3 giffgaff_keeper.py summary
python3 giffgaff_keeper.py balance-cookie --cookie-file ./cookies.txt
python3 giffgaff_keeper.py balance-adb --draft
python3 giffgaff_keeper.py balance-adb --sent-now
python3 giffgaff_keeper.py balance-adb --read-sms --device <adb-device>
python3 giffgaff_keeper.py lark-create --dry-run
```

低流量保号：把 `web/` 部署到任意静态网站，在手机上关闭 Wi-Fi，确认当前移动数据 SIM 是 giffgaff，然后打开页面并加载 payload。确认完成后再记录：

```bash
python3 giffgaff_keeper.py record --date 2026-06-30 --source mobile_data_payload --evidence-note "确认 Wi-Fi 关闭后已加载 payload" --confirm-valid-action
```

可选证据文件：

```bash
python3 giffgaff_keeper.py record --date 2026-06-30 --source mobile_data_payload --evidence-file screenshot.png --confirm-valid-action
```

工具不会复制证据文件，只会把文件的 SHA-256 写入 `state.json`。

## 安全边界

- 不要求上传 Cookie。
- 不要求上传完整手机号。
- 静态网页只下载本地 `payload.bin`。
- payload 下载成功只是本地观察证据，不是 giffgaff 官方确认。
- `official_expiry_at` 固定为 `null`，除非未来 giffgaff 提供官方有效期来源。
- 飞书/Lark 日历只用于提醒，不是保号证明。

## 查询余额

余额查询是可选能力。余额不证明保号，Cookie/ADB 也不能拿到官方保号有效期。解析失败会写入 `last_balance_error`；旧的成功余额不会被失败结果覆盖。

Cookie 路线：

```bash
export GIFFGAFF_COOKIE='...'
python3 giffgaff_keeper.py balance-cookie
```

或：

```bash
chmod 600 cookies.txt
python3 giffgaff_keeper.py balance-cookie --cookie-file ./cookies.txt
```

`balance-cookie` 只会把 Cookie 发给 `https://*.giffgaff.com/`。如果 giffgaff 把 dashboard 请求跳回登录页，命令会记录 `cookie_login_required`。

ADB/SMS 路线：

```bash
python3 giffgaff_keeper.py balance-adb --draft
# 在手机上发送 INFO 短信后记录发送时间：
python3 giffgaff_keeper.py balance-adb --sent-now
# 收到回复后读取 85075 新短信：
python3 giffgaff_keeper.py balance-adb --read-sms --device <adb-device>
```

`balance-adb --read-sms` 只读取上次 `--draft` 或 `--sent-now` 之后来自 `85075` 的短信。双卡 Android 如果 giffgaff 不是默认短信 SIM，可以加 `--slot <index>` 和 `--sub-id <id>`。

也可以使用官方渠道：giffgaff App/dashboard、拨打 `43430`，或发送 `INFO` 到 `85075`。

不要把 `INFO` 到 `85075`、`43430`、客服号码、紧急电话、免费电话或其他 free-rated 行为记录为保号动作。

## 输出摘要

```bash
python3 giffgaff_keeper.py summary
```

它会输出余额（如果可用）和估算保号日期，同时保留 `official_expiry_at: null`。

## 文件

```text
giffgaff_keeper.py  CLI 和日期计算
web/index.html      静态移动数据 payload 页面
web/payload.bin     约 128 KiB 的随机 payload
skill/SKILL.md      Agent 使用说明
state.json          本地状态文件，已被 gitignore
```
