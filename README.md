# giffgaff-keeper-agent

Local-first giffgaff keepalive helper for Agents, Skills, and simple automation.

It does not fetch an official giffgaff expiry date. giffgaff's rule is active use at least once every 6 months, so this tool records a confirmed local keepalive action and estimates:

```text
official_expiry_at = null
estimated_expiry_at = last_activity_at + 180 days
expiry_source = estimated_from_last_activity
remind_at = estimated_expiry_at - 30 days
```

## Quick Start

```bash
python3 giffgaff_keeper.py record --date 2026-06-30 --number-hint "****1234" --evidence-note "payload loaded on giffgaff mobile data" --confirm-valid-action
python3 giffgaff_keeper.py status
python3 giffgaff_keeper.py summary
python3 giffgaff_keeper.py balance-cookie --cookie-file ./cookies.txt
python3 giffgaff_keeper.py balance-adb --draft
python3 giffgaff_keeper.py balance-adb --sent-now
python3 giffgaff_keeper.py balance-adb --read-sms --device <adb-device>
python3 giffgaff_keeper.py lark-create --dry-run
```

To perform a low-data keepalive, deploy `web/` somewhere static, open it on the phone with Wi-Fi off and giffgaff selected as the mobile-data SIM, then record the action:

```bash
python3 giffgaff_keeper.py record --date 2026-06-30 --source mobile_data_payload --evidence-note "payload loaded after I confirmed Wi-Fi was off" --confirm-valid-action
```

Optional evidence file:

```bash
python3 giffgaff_keeper.py record --date 2026-06-30 --source mobile_data_payload --evidence-file screenshot.png --confirm-valid-action
```

The file is not copied into state; only its SHA-256 is stored.

## Safety Boundary

- Cookie upload is not required.
- Phone number upload is not required.
- The web page only downloads its local `payload.bin`.
- A successful payload download is local evidence, not an official giffgaff confirmation.
- `official_expiry_at` is always `null` unless giffgaff exposes an official value in the future.
- Feishu/Lark calendar is only a reminder output.

## Balance Check

Balance is optional and best-effort. Balance does not prove keepalive, and Cookie/ADB cannot fetch an official giffgaff expiry date. Parse failures are stored as `last_balance_error`; old successful balances are not overwritten by failures.

Cookie route:

```bash
export GIFFGAFF_COOKIE='...'
python3 giffgaff_keeper.py balance-cookie
```

or:

```bash
python3 giffgaff_keeper.py balance-cookie --cookie-file ./cookies.txt
```

`balance-cookie` only sends the cookie to `https://*.giffgaff.com/`.
If giffgaff redirects the dashboard request to login, the command records `cookie_login_required`.
For cookie files, use `chmod 600 cookies.txt`.

ADB route:

```bash
python3 giffgaff_keeper.py balance-adb --draft
# send the INFO SMS on the phone, then mark the send time:
python3 giffgaff_keeper.py balance-adb --sent-now
# after the reply arrives:
python3 giffgaff_keeper.py balance-adb --read-sms --device <adb-device>
```

`balance-adb --read-sms` only considers `85075` replies newer than the last `--draft`.
Use `--slot <index>` and `--sub-id <id>` on dual-SIM Android phones when giffgaff is not the default SMS SIM.

Use official channels where possible: giffgaff app/dashboard, call `43430`, or text `INFO` to `85075`.

Do not record `INFO` to `85075`, `43430`, member-services calls, emergency calls, freephone numbers, or other free-rated actions as keepalive activity.

## User Output

```bash
python3 giffgaff_keeper.py summary
```

This prints the balance if available and the estimated keepalive deadline. It still reports `official_expiry_at: null`.

## Files

```text
giffgaff_keeper.py  CLI and date calculation
web/index.html      static mobile-data payload page
web/payload.bin     about 128 KiB random payload
skill/SKILL.md      Agent instructions
state.json          local state, ignored by git
```
