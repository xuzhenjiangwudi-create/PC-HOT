#!/usr/bin/env python3
"""PC HOT - QQ email (env credentials + Lenovo-styled HTML)"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
import sys

SMTP_SERVER = os.environ.get("PC_HOT_SMTP_SERVER", "smtp.qq.com")
SMTP_PORT = int(os.environ.get("PC_HOT_SMTP_PORT", "465"))
SENDER = os.environ.get("PC_HOT_SMTP_USER", "1043643759@qq.com")
PASSWORD = os.environ.get("PC_HOT_SMTP_PASS", "")

_env_receivers = os.environ.get("PC_HOT_RECEIVERS", "").strip()
if _env_receivers:
    RECEIVERS = [x.strip() for x in _env_receivers.split(",") if x.strip()]
else:
    RECEIVERS = [
        "1043643759@qq.com",
        "markgao@lenovo.com",
        "xuzj12@lenovo.com",
        "tbeaufort@lenovo.com",
        "fanying4@lenovo.com",
        "chrislin@lenovo.com",
        "wanghq15@lenovo.com",
        "bizh2@lenovo.com",
        "kanke1@lenovo.com",
        "niedang1@lenovo.com",
    ]

SITE_URL = "https://xuzhenjiangwudi-create.github.io/PC-HOT/"


def build_html(now: str, entry_count: int, cost_count: int, top_titles: list) -> str:
    items_html = ""
    if top_titles:
        items_html = "<ol style='margin:0;padding-left:20px;color:#374151;font-size:14px;line-height:1.6;'>"
        for t in top_titles[:6]:
            items_html += f"<li style='margin-bottom:8px;'>{t}</li>"
        items_html += "</ol>"
    else:
        items_html = "<p style='color:#9ca3af;font-size:14px;'>See website for full list.</p>"

    return f"""
<div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;">
  <div style="background:#111827;padding:28px 24px;text-align:center;">
    <div style="margin-bottom:16px;">
      <span style="display:inline-block;background:#E2231A;color:#ffffff;
                   font-family:Arial,Helvetica,sans-serif;font-weight:700;
                   font-size:32px;letter-spacing:-0.02em;padding:10px 22px;
                   border-radius:6px;line-height:1.2;">Lenovo</span>
    </div>
    <div style="color:#ffffff;font-size:20px;font-weight:700;">
      PC HOT <span style="color:#9ca3af;font-weight:400;">×</span> TEC
    </div>
    <div style="color:#9ca3af;font-size:13px;margin-top:6px;">Laptop Industry Briefing</div>
  </div>

  <div style="padding:24px;">
    <h2 style="margin:0 0 8px;color:#111827;font-size:20px;">PC HOT Daily Update</h2>
    <p style="margin:0 0 16px;color:#6b7280;font-size:14px;">
      Laptop industry · OEM / ODM · AI PC
    </p>

    <table style="width:100%;border-collapse:collapse;margin-bottom:24px;font-size:14px;">
      <tr>
        <td style="padding:8px 0;color:#6b7280;">Time</td>
        <td style="padding:8px 0;color:#111827;text-align:right;font-weight:600;">{now}</td>
      </tr>
      <tr>
        <td style="padding:8px 0;color:#6b7280;border-top:1px solid #f3f4f6;">Items</td>
        <td style="padding:8px 0;color:#111827;text-align:right;font-weight:600;border-top:1px solid #f3f4f6;">{entry_count}</td>
      </tr>
      <tr>
        <td style="padding:8px 0;color:#6b7280;border-top:1px solid #f3f4f6;">Cost-related</td>
        <td style="padding:8px 0;color:#d97706;text-align:right;font-weight:600;border-top:1px solid #f3f4f6;">{cost_count}</td>
      </tr>
    </table>

    <div style="text-align:center;margin:8px 0 28px;">
      <a href="{SITE_URL}"
         style="display:block;background:#1f2937;color:#ffffff;text-decoration:none;
                padding:16px 24px;border-radius:10px;font-size:17px;font-weight:700;
                letter-spacing:0.02em;border:2px solid #374151;">
        Open PC HOT Website
      </a>
      <p style="margin:10px 0 0;font-size:12px;color:#9ca3af;">{SITE_URL}</p>
    </div>

    <h3 style="margin:0 0 12px;color:#111827;font-size:16px;">Top stories</h3>
    {items_html}
  </div>

  <div style="background:#f9fafb;padding:16px 24px;border-top:1px solid #e5e7eb;text-align:center;">
    <p style="margin:0;color:#9ca3af;font-size:12px;">— PC HOT auto notification · Lenovo TEC</p>
    <p style="margin:6px 0 0;color:#d1d5db;font-size:11px;">This is an internal briefing email.</p>
  </div>
</div>
"""


def send_one(to: str, subject: str, content: str, html_content: str = None) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SENDER
        msg["To"] = to
        msg["Subject"] = Header(subject, "utf-8")
        msg.attach(MIMEText(content, "plain", "utf-8"))
        if html_content:
            msg.attach(MIMEText(html_content, "html", "utf-8"))
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            server.login(SENDER, PASSWORD)
            server.sendmail(SENDER, [to], msg.as_string())
        print(f"  OK → {to}")
        return True
    except Exception as e:
        print(f"  FAIL → {to}: {e}")
        return False


def send_daily_report(entry_count: int = 0, cost_count: int = 0, top_titles: list = None):
    if not PASSWORD:
        print("错误: 未设置环境变量 PC_HOT_SMTP_PASS")
        return False

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    subject = f"PC HOT Daily Update · {now[:10]}"

    lines = [
        "PC HOT — Daily laptop industry briefing",
        f"Time: {now}",
        f"Items: {entry_count}",
        f"Cost-related: {cost_count}",
        f"Website: {SITE_URL}",
        "",
    ]
    if top_titles:
        lines.append("Top stories:")
        for i, t in enumerate(top_titles[:6], 1):
            lines.append(f"  {i}. {t}")
        lines.append("")
    lines.append("— PC HOT auto notification · Lenovo TEC")
    content = "\n".join(lines)
    html = build_html(now, entry_count, cost_count, top_titles or [])

    print(f"Sending to {len(RECEIVERS)} recipients...")
    ok_count = 0
    for to in RECEIVERS:
        if send_one(to, subject, content, html):
            ok_count += 1
    print(f"Done: {ok_count}/{len(RECEIVERS)}")
    return ok_count > 0


if __name__ == "__main__":
    print("Test email...")
    print(f"Password set: {'yes' if PASSWORD else 'NO'}")
    ok = send_daily_report(
        entry_count=55,
        cost_count=19,
        top_titles=[
            "Dell launches affordable 15-inch laptop with Intel Core Series 3",
            "Lenovo LOQ Essential gaming laptop with RTX 5060 goes global",
            "Memory prices and AI PC cost pressure continue to rise",
        ],
    )
    sys.exit(0 if ok else 1)
