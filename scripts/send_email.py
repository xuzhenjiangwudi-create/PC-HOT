#!/usr/bin/env python3
"""PC HOT - QQ 邮箱通知"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
import sys

SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
SENDER = "1043643759@qq.com"
PASSWORD = "frkgodfprdlibahj"
RECEIVER = "1043643759@qq.com"


def send_update_email(subject: str, content: str, html_content: str = None) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SENDER
        msg["To"] = RECEIVER
        msg["Subject"] = Header(subject, "utf-8")
        msg.attach(MIMEText(content, "plain", "utf-8"))
        if html_content:
            msg.attach(MIMEText(html_content, "html", "utf-8"))

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            server.login(SENDER, PASSWORD)
            server.sendmail(SENDER, [RECEIVER], msg.as_string())
        print("邮件发送成功 →", RECEIVER)
        return True
    except Exception as e:
        print("邮件发送失败:", e)
        return False


def send_daily_report(entry_count: int = 0, cost_count: int = 0, top_titles: list = None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    site_url = "https://xuzhenjiangwudi-create.github.io/PC-HOT/"
    subject = f"PC HOT 每日更新 · {now[:10]}"

    lines = [
        f"PC HOT 已完成今日更新",
        f"时间：{now}",
        f"",
        f"本次资讯数量：{entry_count} 条",
        f"其中成本/价格相关：{cost_count} 条",
        f"",
        f"网站地址：{site_url}",
        f"",
    ]
    if top_titles:
        lines.append("今日热榜：")
        for i, t in enumerate(top_titles[:6], 1):
            lines.append(f"  {i}. {t}")
        lines.append("")
    lines.append("— PC HOT 自动推送")
    content = "\n".join(lines)

    html = f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto;">
      <h2 style="color:#2563eb;">PC HOT 每日更新</h2>
      <p>时间：{now}</p>
      <p>本次资讯：<b>{entry_count}</b> 条 · 成本相关：<b>{cost_count}</b> 条</p>
      <p><a href="{site_url}">点击查看网站 →</a></p>
    """
    if top_titles:
        html += "<h3>今日热榜</h3><ol>"
        for t in top_titles[:6]:
            html += f"<li>{t}</li>"
        html += "</ol>"
    html += "<p style='color:#888;font-size:12px;'>— PC HOT 自动推送</p></div>"

    return send_update_email(subject, content, html)


if __name__ == "__main__":
    print("正在发送测试/通知邮件...")
    ok = send_daily_report(
        entry_count=0,
        cost_count=0,
        top_titles=["任务已执行，请打开网站查看最新内容"]
    )
    sys.exit(0 if ok else 1)
