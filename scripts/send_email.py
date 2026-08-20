#!/usr/bin/env python3
"""PC HOT - QQ email (credentials from environment variables)"""

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
PASSWORD = os.environ.get("PC_HOT_SMTP_PASS", "")  # 必须从环境变量读取

# 收件人：环境变量用英文逗号分隔，否则用下面默认列表
_env_receivers = os.environ.get("PC_HOT_RECEIVERS", "").strip()
if _env_receivers:
    RECEIVERS = [x.strip() for x in _env_receivers.split(",") if x.strip()]
else:
    RECEIVERS = [
        "1043643759@qq.com",
        "markgao@lenovo.com",
        "xuzj12@lenovo.com",
    ]


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
    """Email body prefers English."""
    if not PASSWORD:
        print("错误: 未设置环境变量 PC_HOT_SMTP_PASS（QQ 邮箱授权码）")
        print("请先设置后再发送邮件。")
        return False

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    site_url = "https://xuzhenjiangwudi-create.github.io/PC-HOT/"
    subject = f"PC HOT Daily Update · {now[:10]}"

    lines = [
        "PC HOT — Daily laptop industry briefing",
        f"Time: {now}",
        "",
        f"Items: {entry_count}",
        f"Cost / pricing related: {cost_count}",
        "",
        f"Website: {site_url}",
        "",
    ]
    if top_titles:
        lines.append("Top stories:")
        for i, t in enumerate(top_titles[:6], 1):
            lines.append(f"  {i}. {t}")
        lines.append("")
    lines.append("— PC HOT auto notification")
    content = "\n".join(lines)

    html = f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;max-width:560px;margin:0 auto;color:#111;">
      <h2 style="color:#2563eb;margin-bottom:8px;">PC HOT Daily Update</h2>
      <p style="color:#555;">Laptop industry · OEM / ODM · AI PC</p>
      <p><b>Time:</b> {now}</p>
      <p><b>Items:</b> {entry_count} · <b>Cost-related:</b> {cost_count}</p>
      <p><a href="{site_url}" style="color:#2563eb;">Open website →</a></p>
    """
    if top_titles:
        html += "<h3 style='margin-top:20px;'>Top stories</h3><ol>"
        for t in top_titles[:6]:
            html += f"<li style='margin-bottom:6px;'>{t}</li>"
        html += "</ol>"
    html += "<p style='color:#888;font-size:12px;margin-top:24px;'>— PC HOT auto notification</p></div>"

    print(f"Sending English email to {len(RECEIVERS)} recipients...")
    ok_count = 0
    for to in RECEIVERS:
        if send_one(to, subject, content, html):
            ok_count += 1
    print(f"Done: {ok_count}/{len(RECEIVERS)}")
    return ok_count > 0


if __name__ == "__main__":
    print("Test English email...")
    print(f"SMTP user: {SENDER}")
    print(f"Receivers: {RECEIVERS}")
    print(f"Password set: {'yes' if PASSWORD else 'NO'}")
    ok = send_daily_report(
        entry_count=0,
        cost_count=0,
        top_titles=["Test: laptop industry digest (English body)"],
    )
    sys.exit(0 if ok else 1)
