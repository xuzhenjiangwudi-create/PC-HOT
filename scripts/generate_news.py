#!/usr/bin/env python3
"""
PC HOT - 简单新闻生成脚本
从几个公开 RSS 源抓取最新 PC/硬件相关新闻，生成 index.html
注意：RSS 源质量和反爬情况会变化，实际使用中可继续完善。
"""

import feedparser
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re
import html

# 可继续添加更多 RSS 源
RSS_SOURCES = [
    ("HotHardware", "https://hothardware.com/rss"),
    ("Tom's Hardware", "https://www.tomshardware.com/feeds/all"),
    ("TechSpot", "https://www.techspot.com/backend.xml"),
    ("AnandTech", "https://www.anandtech.com/rss/"),
]

# 简单关键词过滤，只保留更相关的 PC/硬件内容
KEYWORDS = [
    "pc", "laptop", "notebook", "cpu", "gpu", "rtx", "ryzen", "intel", "amd",
    "nvidia", "memory", "ram", "ddr", "ssd", "motherboard", "chipset",
    "asus", "msi", "gigabyte", "lenovo", "dell", "hp", "apple", "macbook",
    "windows", "ai pc", "snapdragon", "qualcomm", "computex"
]

def is_relevant(title: str, summary: str = "") -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in KEYWORDS)

def clean_text(text: str, max_len: int = 180) -> str:
    if not text:
        return ""
    # 去掉 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text).strip()
    text = re.sub(r'\s+', ' ', text)
    if len(text) > max_len:
        text = text[:max_len].rsplit(' ', 1)[0] + "…"
    return text

def fetch_entries(max_items: int = 25):
    entries = []
    headers = {"User-Agent": "PC-HOT-Bot/1.0 (+https://github.com)"}

    for source_name, url in RSS_SOURCES:
        try:
            print(f"Fetching {source_name} ...")
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)

            for entry in feed.entries[:12]:
                title = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", ""))
                link = entry.get("link", "")
                published = entry.get("published_parsed") or entry.get("updated_parsed")

                if not title or not is_relevant(title, summary):
                    continue

                dt = None
                if published:
                    try:
                        dt = datetime(*published[:6], tzinfo=timezone.utc)
                    except Exception:
                        pass

                entries.append({
                    "title": title,
                    "summary": clean_text(summary),
                    "link": link,
                    "source": source_name,
                    "dt": dt or datetime.now(timezone.utc),
                })
        except Exception as e:
            print(f"  Failed {source_name}: {e}")

    # 去重（按标题相似度简单处理）
    seen = set()
    unique = []
    for e in sorted(entries, key=lambda x: x["dt"], reverse=True):
        key = e["title"].lower()[:60]
        if key not in seen:
            seen.add(key)
            unique.append(e)
        if len(unique) >= max_items:
            break

    return unique

def heat_score(rank: int) -> int:
    # 简单模拟热度
    base = [220, 185, 140, 110, 90, 75, 65, 55, 48, 42]
    if rank < len(base):
        return base[rank]
    return max(30, 40 - rank)

def render_html(entries):
    now = datetime.now(timezone(timedelta(hours=8)))  # 北京时间大概
    today_str = now.strftime("%Y年%m月%d日")
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]

    # 热榜取前 5
    hot = entries[:5]

    hot_html = ""
    for i, e in enumerate(hot):
        rank_class = "top3" if i < 3 else ""
        hot_html += f"""
      <div class="hot-item">
        <div class="hot-rank {rank_class}">{i+1}</div>
        <div class="hot-content">
          <div class="hot-title">{html.escape(e['title'])}</div>
        </div>
        <div class="hot-heat">{heat_score(i)} 热度</div>
      </div>"""

    # 按日期分组（简化：全部放在“今天”）
    feed_html = ""
    for i, e in enumerate(entries[:12]):
        time_str = e["dt"].astimezone(timezone(timedelta(hours=8))).strftime("%H:%M") if e["dt"] else "--:--"
        heat = heat_score(i)
        reason = "来自公开 RSS 聚合，自动生成。实际热度与重要性请结合原文判断。"
        feed_html += f"""
      <article class="feed-item">
        <div class="feed-meta">
          <span class="feed-time">{time_str}</span>
          <span class="feed-source">{html.escape(e['source'])}</span>
          <span class="feed-heat">{heat} 热度</span>
        </div>
        <div class="feed-title"><a href="{html.escape(e['link'])}" target="_blank" rel="noopener">{html.escape(e['title'])}</a></div>
        <div class="feed-summary">{html.escape(e['summary']) or '（无摘要）'}</div>
        <div class="feed-reason">
          <strong>推荐理由：</strong>{reason}
        </div>
      </article>"""

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PC HOT — PC 行业动态聚合 · 每日精选与硬件日报</title>
  <style>
    :root {{
      --bg: #fafafa;
      --card: #ffffff;
      --text: #1a1a1a;
      --text-secondary: #666;
      --text-muted: #999;
      --border: #eee;
      --accent: #2563eb;
      --hot: #ef4444;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
      min-height: 100vh;
    }}
    a {{ color: inherit; text-decoration: none; }}
    a:hover {{ color: var(--accent); }}
    header {{
      background: var(--card);
      border-bottom: 1px solid var(--border);
      position: sticky; top: 0; z-index: 50;
    }}
    .header-inner {{
      max-width: 860px; margin: 0 auto; padding: 16px 20px;
      display: flex; align-items: center; justify-content: space-between;
    }}
    .logo {{
      display: flex; align-items: center; gap: 10px;
      font-weight: 700; font-size: 1.25rem; letter-spacing: -0.02em;
    }}
    .logo-badge {{
      background: linear-gradient(135deg, #2563eb, #7c3aed);
      color: white; font-size: 0.7rem; font-weight: 700;
      padding: 3px 8px; border-radius: 6px; letter-spacing: 0.05em;
    }}
    .header-right {{ font-size: 0.8rem; color: var(--text-muted); }}
    main {{ max-width: 860px; margin: 0 auto; padding: 24px 20px 60px; }}
    .section-header {{
      display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 16px;
    }}
    .section-header h2 {{ font-size: 1.15rem; font-weight: 700; }}
    .section-header .date {{ font-size: 0.85rem; color: var(--text-muted); }}
    .hot-list {{
      background: var(--card); border: 1px solid var(--border);
      border-radius: 12px; padding: 8px 0; margin-bottom: 32px;
    }}
    .hot-item {{
      display: flex; align-items: flex-start; gap: 12px; padding: 12px 18px;
      transition: background 0.15s;
    }}
    .hot-item:hover {{ background: #f8fafc; }}
    .hot-rank {{ font-weight: 700; font-size: 1rem; color: var(--text-muted); min-width: 22px; text-align: center; }}
    .hot-rank.top3 {{ color: var(--hot); }}
    .hot-content {{ flex: 1; min-width: 0; }}
    .hot-title {{ font-size: 0.95rem; font-weight: 500; }}
    .hot-heat {{ font-size: 0.8rem; color: var(--hot); font-weight: 600; white-space: nowrap; }}
    .day-block {{ margin-bottom: 36px; }}
    .day-title {{
      font-size: 1.05rem; font-weight: 700; margin-bottom: 16px;
      padding-bottom: 8px; border-bottom: 1px solid var(--border);
    }}
    .feed-item {{
      background: var(--card); border: 1px solid var(--border);
      border-radius: 12px; padding: 16px 18px; margin-bottom: 12px;
      transition: border-color 0.15s, box-shadow 0.15s;
    }}
    .feed-item:hover {{ border-color: #d1d5db; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }}
    .feed-meta {{
      display: flex; align-items: center; gap: 10px; font-size: 0.8rem;
      color: var(--text-muted); margin-bottom: 8px; flex-wrap: wrap;
    }}
    .feed-source {{ color: var(--accent); font-weight: 500; }}
    .feed-heat {{ margin-left: auto; color: var(--hot); font-weight: 600; }}
    .feed-title {{ font-size: 1.02rem; font-weight: 600; margin-bottom: 8px; line-height: 1.4; }}
    .feed-summary {{ font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 10px; line-height: 1.55; }}
    .feed-reason {{
      font-size: 0.85rem; color: var(--text-muted); background: #f8fafc;
      border-radius: 8px; padding: 10px 12px; border-left: 3px solid var(--accent);
    }}
    .feed-reason strong {{ color: var(--text-secondary); font-weight: 600; }}
    footer {{
      max-width: 860px; margin: 0 auto; padding: 24px 20px;
      border-top: 1px solid var(--border); text-align: center;
      font-size: 0.8rem; color: var(--text-muted);
    }}
    footer p {{ margin-bottom: 4px; }}
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <div class="logo">
        <span class="logo-badge">PC</span>
        <span>PC HOT</span>
      </div>
      <div class="header-right">PC 行业动态聚合 · 每日精选</div>
    </div>
  </header>

  <main>
    <div class="section-header">
      <h2>精选</h2>
      <span class="date">{now.strftime('%m月%d日')} · {weekday}</span>
    </div>

    <div class="hot-list">
{hot_html}
    </div>

    <div class="section-header">
      <h2>最新精选</h2>
    </div>

    <div class="day-block">
      <div class="day-title">今天 {now.strftime('%m月%d日')} {weekday}</div>
{feed_html}
    </div>
  </main>

  <footer>
    <p><strong>PC HOT</strong> — PC 行业动态聚合 · 每日精选与硬件日报</p>
    <p>自动更新于 {now.strftime('%Y-%m-%d %H:%M')} (CST) · 数据来自公开 RSS</p>
    <p>本页面由 GitHub Actions 定时生成</p>
  </footer>
</body>
</html>"""
    return html_content

def main():
    print("PC HOT news generator starting...")
    entries = fetch_entries()
    print(f"Got {len(entries)} relevant entries")

    if not entries:
        print("No entries found, keeping existing index.html")
        return

    html = render_html(entries)
    out = Path("index.html")
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out.resolve()}")

if __name__ == "__main__":
    main()
