#!/usr/bin/env python3
"""Local-first giffgaff keepalive helper."""

from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
import urllib.parse
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path


STATE_PATH = Path(__file__).with_name("state.json")
VALID_SOURCES = {"mobile_data_payload", "paid_sms", "paid_call", "airtime_purchase", "manual_official_usage"}
ADB = os.environ.get("ADB", "adb")
BALANCE_RE = re.compile(r"(?:£|GBP\s*)(\d+(?:[.,]\d{1,2})?)|(\d+(?:[.,]\d{1,2})?)\s*(?:GBP|pounds?)", re.I)
BALANCE_CONTEXT_PATTERNS = [
    re.compile(r"(?:credit\s+balance|airtime\s+credit|account\s+balance|current\s+balance|your\s+balance|remaining\s+credit)[^£]{0,120}(?:£|GBP\s*)(\d+(?:[.,]\d{1,2})?)", re.I | re.S),
    re.compile(r"(?:£|GBP\s*)(\d+(?:[.,]\d{1,2})?)[^.\n]{0,80}(?:credit\s+balance|airtime\s+credit|account\s+balance|current\s+balance|remaining\s+credit)", re.I | re.S),
]


def add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    return day.replace(day=min(day.day, calendar.monthrange(year, month)[1]), month=month, year=year)


def compute_status(last_activity_at: str) -> dict:
    last = date.fromisoformat(last_activity_at)
    expiry = last + timedelta(days=180)
    remind = expiry - timedelta(days=30)
    return {
        "last_activity_at": last.isoformat(),
        "official_expiry_at": None,
        "estimated_expiry_at": expiry.isoformat(),
        "expiry_source": "estimated_from_last_activity",
        "remind_at": remind.isoformat(),
        "next_action_before": remind.isoformat(),
        "balance": None,
        "balance_source": "not_supported",
        "note": "estimated as last_activity_at + 180 days from giffgaff's 6-month active-use rule, not an official expiry value",
    }


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text())


def save_state(state: dict) -> None:
    tmp = STATE_PATH.with_name(f"{STATE_PATH.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        file.write(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(STATE_PATH)
    STATE_PATH.chmod(0o600)


def parse_balance(text: str, *, require_context: bool = False) -> dict:
    if require_context:
        amounts = [match.group(1).replace(",", ".") for pattern in BALANCE_CONTEXT_PATTERNS for match in pattern.finditer(text)]
    else:
        amounts = [(left or right).replace(",", ".") for left, right in BALANCE_RE.findall(text)]
    if len(amounts) != 1:
        return {"balance": None, "balance_currency": None, "balance_source": "parse_failed"}
    return {"balance": f"{float(amounts[0]):.2f}", "balance_currency": "GBP"}


def looks_like_login_page(text: str, final_url: str) -> bool:
    return "/auth/login" in final_url or bool(re.search(r"<title[^>]*>\s*log\s+in\s*\|\s*giffgaff", text, re.I))


def is_giffgaff_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or ""
    return parsed.scheme == "https" and (host == "giffgaff.com" or host.endswith(".giffgaff.com"))


def save_balance(result: dict, source: str) -> dict:
    state = load_state()
    if result.get("balance"):
        state.update(result)
        state["balance_source"] = source
        state["balance_checked_at"] = datetime.now(timezone.utc).isoformat()
    else:
        state["last_balance_error"] = result.get("balance_source", "parse_failed")
        state["last_balance_error_at"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    return state


def record(args: argparse.Namespace) -> dict:
    if not args.confirm_valid_action:
        raise SystemExit("Refusing to record without --confirm-valid-action.")
    if not args.evidence_note.strip():
        raise SystemExit("Refusing to record without --evidence-note.")
    if args.source not in VALID_SOURCES:
        raise SystemExit(f"Invalid --source. Use one of: {', '.join(sorted(VALID_SOURCES))}")
    if args.number_hint and len(re.findall(r"\d", args.number_hint)) >= 7:
        raise SystemExit("Refusing full-looking phone number. Use a masked hint like ****1234.")
    activity_date = date.fromisoformat(args.date)
    if activity_date > date.today():
        raise SystemExit("Refusing future last_activity_at date.")
    state = load_state()
    balance = {k: state.get(k) for k in ("balance", "balance_currency", "balance_source", "balance_checked_at") if k in state}
    status = compute_status(activity_date.isoformat())
    state.update(status)
    state.update(balance)
    evidence_hash = None
    if args.evidence_file:
        evidence_hash = hashlib.sha256(Path(args.evidence_file).read_bytes()).hexdigest()
    state.update(
        {
            "carrier": "giffgaff",
            "number_hint": args.number_hint,
            "activity_source": args.source,
            "confidence": args.confidence,
            "evidence": args.evidence,
            "evidence_note": args.evidence_note,
            "evidence_sha256": evidence_hash,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    save_state(state)
    return state


def status(_: argparse.Namespace) -> dict:
    state = load_state()
    balance = {k: state.get(k) for k in ("balance", "balance_currency", "balance_source", "balance_checked_at") if k in state}
    if not state.get("last_activity_at"):
        state.update({"last_activity_at": None, "official_expiry_at": None, "estimated_expiry_at": None, "expiry_source": "unknown", "remind_at": None, "next_action_before": None})
        state.update(balance or {"balance": None, "balance_source": "not_supported"})
        state["note"] = "No keepalive activity recorded yet. Run record after a confirmed valid action."
        return state
    state.update(compute_status(state["last_activity_at"]))
    state.update(balance)
    save_state(state)
    return state


def summary(args: argparse.Namespace) -> dict:
    state = status(args)
    return {
        "carrier": "giffgaff",
        "number_hint": state.get("number_hint"),
        "balance": state.get("balance"),
        "balance_currency": state.get("balance_currency"),
        "balance_source": state.get("balance_source"),
        "last_balance_error": state.get("last_balance_error"),
        "last_balance_error_at": state.get("last_balance_error_at"),
        "official_expiry_at": state.get("official_expiry_at"),
        "estimated_expiry_at": state.get("estimated_expiry_at"),
        "remind_at": state.get("remind_at"),
        "expiry_source": state.get("expiry_source"),
        "note": state.get("note"),
    }


def balance_cookie(args: argparse.Namespace) -> dict:
    if args.cookie_file:
        cookie_path = Path(args.cookie_file)
        if os.name == "posix" and cookie_path.stat().st_mode & 0o077:
            raise SystemExit("Refusing cookie file readable by group/others. Run: chmod 600 <cookie-file>")
        cookie = cookie_path.read_text().strip()
    else:
        cookie = os.environ.get(args.cookie_env)
    if not cookie:
        return save_balance({"balance": None, "balance_currency": None, "balance_source": "cookie_missing"}, "cookie_missing")
    if not is_giffgaff_url(args.url):
        return save_balance({"balance": None, "balance_currency": None, "balance_source": "cookie_url_blocked"}, "cookie_url_blocked")
    req = urllib.request.Request(args.url, headers={"User-Agent": "giffgaff-keeper-agent/0.1"})
    req.add_unredirected_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as response:
            text = response.read().decode("utf-8", "replace")
            final_url = response.geturl()
    except urllib.error.URLError as exc:
        return save_balance({"balance": None, "balance_currency": None, "balance_source": "cookie_fetch_failed"}, "cookie_fetch_failed")
    if looks_like_login_page(text, final_url):
        return save_balance({"balance": None, "balance_currency": None, "balance_source": "cookie_login_required"}, "cookie_login_required")
    result = parse_balance(text, require_context=True)
    return save_balance(result, "cookie" if result.get("balance") else "cookie_parse_failed")


def selected_device(device: str | None) -> str | None:
    if device:
        return device
    out = subprocess.run([ADB, "devices"], text=True, capture_output=True, check=False).stdout
    devices = [line.split()[0] for line in out.splitlines() if line.endswith("\tdevice")]
    if len(devices) != 1:
        raise SystemExit(f"Need exactly one adb device, found {len(devices)}. Pass --device if needed.")
    return devices[0]


def adb_sim_extras(args: argparse.Namespace) -> list[str]:
    extras = []
    if args.sub_id is not None:
        sub_id = str(args.sub_id)
        extras += ["--ei", "subscription", sub_id, "--ei", "android.telephony.extra.SUBSCRIPTION_INDEX", sub_id]
    if args.slot is not None:
        slot = str(args.slot)
        extras += ["--ei", "slot", slot, "--ei", "simSlot", slot, "--ei", "simSlotIndex", slot, "--ei", "com.android.phone.extra.slot", slot]
    return extras


def balance_adb(args: argparse.Namespace) -> dict:
    if args.sent_now:
        state = load_state()
        state["pending_balance_query_at"] = int(datetime.now(timezone.utc).timestamp() * 1000)
        state["pending_balance_query_source"] = "adb_info_85075"
        save_state(state)
        return {"pending_balance_query_at": state["pending_balance_query_at"], "to": "85075", "body": "INFO"}
    device = selected_device(args.device)
    adb_prefix = [ADB] + (["-s", device] if device else [])
    if args.draft:
        state = load_state()
        state["pending_balance_query_at"] = int(datetime.now(timezone.utc).timestamp() * 1000)
        save_state(state)
        cmd = adb_prefix + [
            "shell",
            "am",
            "start",
            "-a",
            "android.intent.action.SENDTO",
            "-d",
            "sms:85075",
            "--es",
            "sms_body",
            "INFO",
        ] + adb_sim_extras(args)
        subprocess.run(cmd, check=True)
        return {"opened_sms_draft": True, "to": "85075", "body": "INFO", "sent": False}
    if args.read_sms:
        pending = int(load_state().get("pending_balance_query_at") or 0)
        if not pending:
            raise SystemExit("Run --draft or --sent-now before --read-sms.")
        cmd = adb_prefix + [
            "shell",
            "content",
            "query",
            "--uri",
            "content://sms/inbox",
            "--projection",
            "address,body,date",
            "--where",
            f"address='85075' AND date>{pending}",
        ]
        try:
            out = subprocess.run(cmd, text=True, capture_output=True, check=True).stdout
        except subprocess.CalledProcessError as exc:
            return save_balance({"balance": None, "balance_currency": None, "balance_source": "adb_sms_read_failed"}, "adb_sms_read_failed")
        result = parse_balance(out, require_context=True)
        return save_balance(result, "adb_sms" if result.get("balance") else "adb_sms_parse_failed")
    raise SystemExit("Use --draft to open the INFO SMS draft, or --read-sms to parse the inbox reply.")


def lark_create(args: argparse.Namespace) -> dict:
    state = status(args)
    start_dt = datetime.combine(date.fromisoformat(state["remind_at"]), time(9, 0), timezone(timedelta(hours=8)))
    end_dt = start_dt + timedelta(minutes=30)
    summary = f"giffgaff 保号提醒 {state.get('number_hint') or ''}".strip()
    description = "\n".join(
        [
            f"预计失效日：{state['estimated_expiry_at']}",
            f"最近记录动作：{state['last_activity_at']} ({state.get('activity_source', 'unknown')})",
            "依据：giffgaff 6 个月内至少一次合格使用规则。",
            "注意：这是本地估算，不是 giffgaff 官方返回的有效期。",
            "建议：关闭 Wi-Fi，用 giffgaff 移动数据打开 payload，或发送一条普通 SMS。",
        ]
    )
    data = {
        "summary": summary,
        "description": description,
        "start_time": {"timestamp": str(int(start_dt.timestamp()))},
        "end_time": {"timestamp": str(int(end_dt.timestamp()))},
        "vchat": {"vc_type": "no_meeting"},
        "reminders": [{"minutes": 5}],
        "free_busy_status": "free",
    }
    idempotency_key = str(uuid.UUID(hashlib.md5(f"giffgaff:{state['remind_at']}:{state.get('number_hint', '')}".encode()).hexdigest()))
    cmd = [
        "lark-cli",
        "calendar",
        "events",
        "create",
        "--params",
        json.dumps({"calendar_id": args.calendar_id, "idempotency_key": idempotency_key}, ensure_ascii=False),
        "--data",
        json.dumps(data, ensure_ascii=False),
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    subprocess.run(cmd, check=True)
    return {"created": not args.dry_run, "start": start_dt.isoformat(), "summary": summary}


def demo() -> None:
    assert compute_status("2025-01-01")["estimated_expiry_at"] == "2025-06-30"
    assert parse_balance("Your balance is £9.10")["balance"] == "9.10"
    assert parse_balance("no money here")["balance_source"] == "parse_failed"
    assert parse_balance("balance £9.10 plan £10")["balance_source"] == "parse_failed"
    assert parse_balance("Your credit balance is now £9.10.", require_context=True)["balance"] == "9.10"
    assert parse_balance("Your balance is £9.10. Plans from £10.", require_context=True)["balance"] == "9.10"
    assert looks_like_login_page("<title>Log in | giffgaff</title>", "https://www.giffgaff.com/auth/login?redirect=%2Fdashboard")
    assert is_giffgaff_url("https://www.giffgaff.com/dashboard")
    assert not is_giffgaff_url("https://giffgaff.com.evil.test/dashboard")
    assert adb_sim_extras(argparse.Namespace(slot=1, sub_id=1)) == ["--ei", "subscription", "1", "--ei", "android.telephony.extra.SUBSCRIPTION_INDEX", "1", "--ei", "slot", "1", "--ei", "simSlot", "1", "--ei", "simSlotIndex", "1", "--ei", "com.android.phone.extra.slot", "1"]
    print("ok")


def main() -> None:
    parser = argparse.ArgumentParser(description="Local giffgaff keepalive helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("record", help="record a confirmed keepalive activity")
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--source", default="mobile_data_payload")
    p.add_argument("--confidence", default="local_observed")
    p.add_argument("--number-hint", default="")
    p.add_argument("--evidence", default="user_confirmed")
    p.add_argument("--evidence-note", default="")
    p.add_argument("--evidence-file", help="optional screenshot/export file to hash into state")
    p.add_argument("--confirm-valid-action", action="store_true")
    p.set_defaults(fn=record)

    p = sub.add_parser("status", help="print current estimated status")
    p.set_defaults(fn=status)

    p = sub.add_parser("summary", help="print user-facing balance and keepalive estimate")
    p.set_defaults(fn=summary)

    p = sub.add_parser("balance-cookie", help="try to parse balance from a logged-in giffgaff page")
    p.add_argument("--cookie-env", default="GIFFGAFF_COOKIE")
    p.add_argument("--cookie-file", help="local file containing the giffgaff Cookie header value")
    p.add_argument("--url", default="https://www.giffgaff.com/dashboard")
    p.add_argument("--timeout", type=int, default=20)
    p.set_defaults(fn=balance_cookie)

    p = sub.add_parser("balance-adb", help="open INFO SMS draft or parse 85075 inbox reply")
    p.add_argument("--device")
    p.add_argument("--slot", type=int, help="optional Android SIM slot index, 0-based")
    p.add_argument("--sub-id", type=int, help="optional Android subscription id")
    p.add_argument("--draft", action="store_true")
    p.add_argument("--sent-now", action="store_true", help="record that the user has just sent INFO to 85075")
    p.add_argument("--read-sms", action="store_true")
    p.set_defaults(fn=balance_adb)

    p = sub.add_parser("lark-create", help="create a Feishu/Lark calendar reminder")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--calendar-id", default="primary")
    p.set_defaults(fn=lark_create)

    p = sub.add_parser("demo", help="run tiny self-check")
    p.set_defaults(fn=lambda _args: demo())

    args = parser.parse_args()
    result = args.fn(args)
    if result is not None:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
