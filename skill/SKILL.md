---
name: giffgaff-keeper-agent
description: Local-first giffgaff SIM keepalive helper. Use when the user asks an Agent to check, record, or schedule giffgaff keepalive reminders.
---

# giffgaff keeper

Use the local CLI from this repository. Do not ask the user to upload cookies or phone numbers.

## Rules

- Treat `estimated_expiry_at` as an estimate, not an official giffgaff value.
- Treat `official_expiry_at: null` as intentional. This Skill does not have an official giffgaff expiry source.
- Only record `last_activity_at` after the user confirms a valid action: mobile-data payload loaded over giffgaff, SMS/MMS sent, call made, or airtime/plan purchased.
- Balance is optional and does not prove keepalive. Cookie/ADB cannot fetch an official giffgaff expiry date. Prefer the ADB/SMS route for balance: `balance-adb --draft`, adding `--slot <index> --sub-id <id>` only when dual-SIM selection is needed; run `balance-adb --sent-now` after the user sends `INFO` to `85075`, then `balance-adb --read-sms` after the reply arrives. Cookie is best-effort only: use `balance-cookie --cookie-file <path>` or local `GIFFGAFF_COOKIE`; it must only contact `https://*.giffgaff.com/`, and `cookie_login_required` means the cookie has expired or is not accepted by giffgaff.
- Do not record balance checks, `INFO` to `85075`, `43430`, member-services calls, emergency calls, freephone numbers, or free-rated actions as keepalive activity.
- For low-data keepalive, tell the user to turn off Wi-Fi and make giffgaff the active mobile-data SIM before opening `web/index.html` from their deployed static site.
- For reminders, use `remind_at`, which is 30 days before the estimated expiry date. The estimate uses `last_activity_at + 180 days` as a conservative local rule.

## Commands

```bash
python3 giffgaff_keeper.py record --date YYYY-MM-DD --source mobile_data_payload --number-hint "****1234" --evidence-note "what was confirmed" --confirm-valid-action
python3 giffgaff_keeper.py status
python3 giffgaff_keeper.py summary
python3 giffgaff_keeper.py balance-cookie --cookie-file ./cookies.txt
python3 giffgaff_keeper.py balance-cookie
python3 giffgaff_keeper.py balance-adb --draft
python3 giffgaff_keeper.py balance-adb --sent-now
python3 giffgaff_keeper.py balance-adb --read-sms --device <adb-device>
python3 giffgaff_keeper.py lark-create --dry-run
python3 giffgaff_keeper.py lark-create
```

## Do Not

- Do not claim giffgaff returned an official keepalive expiry date.
- Do not store or print cookies.
- Do not pass non-giffgaff URLs to `balance-cookie`.
- Do not record a keepalive action without first telling the user what evidence will be written.
- Do not silently create calendar events if the user has not asked for reminders.
