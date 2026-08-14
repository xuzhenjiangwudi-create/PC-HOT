#!/usr/bin/env python3
"""
PC HOT - 新闻生成脚本（中文增强版）
支持中英文源、搜索、分类标签，界面全中文
"""

import feedparser
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re
import html
from collections import defaultdict

RSS_SOURCES = [
    # 中文源
    ("IT之家", "https://www.ithome.com/rss/"),
    # 英文源
    ("HotHardware", "https://hothardware.com/rss"),
    ("Tom's Hardware", "https://www.tomshardware.com/feeds/all"),
    ("TechSpot", "https://www.techspot.com/backend.xml"),
    ("PC Perspective", "https://pcper.com/feed/"),
    ("PCWorld", "https://www.pcworld.com/feed"),
    ("PC Gamer", "https://www.pcgamer.com/feeds/tag/hardware"),
    ("Windows Central", "https://www.windowscentral.com/feeds.xml"),
    ("TechPowerUp", "https://www.techpowerup.com/rss/news"),
]

# 分类关键词
CATEGORIES = {
    "处理器": ["cpu", "ryzen", "intel", "core ultra", "snapdragon", "qualcomm", "处理器", "锐龙", "酷睿", "骁龙"],
    "显卡": ["gpu", "rtx", "radeon", "rx ", "graphics", "显卡", "黑井", "blackwell"],
    "内存存储": ["memory", "ram", "ddr", "ssd", "nvme", "存储", "内存", "固态"],
    "笔记本": ["laptop", "notebook", "ai pc", "macbook", "笔记本", "轻薄本", "游戏本"],
    "主板机箱": ["motherboard", "chipset", "case", "主板", "机箱"],
    "市场动态": ["shipment", "market", "price", "shortage", "出货", "涨价", "短缺", "市场"],
}

KEYWORDS = [
    "pc", "laptop", "notebook", "desktop", "cpu", "gpu", "rtx", "rx ", "ryzen", "intel", "amd",
    "nvidia", "memory", "ram", "ddr5", "ddr4", "ssd", "nvme", "motherboard", "chipset",
    "asus", "msi", "gigabyte", "asrock", "lenovo", "dell", "hp", "apple", "macbook",
    "windows", "ai pc", "snapdragon", "qualcomm", "computex", "processor", "graphics",
    "gaming pc", "mini pc", "nuc", "handheld", "steam deck", "rog", "legion",
    "core ultra", "zen ", "blackwell", "rdna", "panther lake", "nova lake",
    "电脑", "笔记本", "显卡", "处理器", "内存", "固态", "主板", "华硕", "微星", "技嘉",
    "联想", "戴尔", "惠普", "苹果", "锐龙", "酷睿", "骁龙"
]

def is_relevant(title: str, summary: str = "") -> bool:
    text = (title + " " + summary).lower()
    return any(kw.lower() in text for kw in KEYWORDS)

def get_category(title: str, summary: str = "") -> str:
    text = (title + " " + summary).lower()
    for cat, kws in CATEGORIES.items():
        if any(kw.lower() in text for kw in kws):
            return cat
    return "综合"

def clean_text(text: str, max_len: int = 200) -> str:
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text).strip()
    text = re.sub(r'\s+', ' ', text)
    if len(text) > max_len:
        text = text[:max_len].rsplit(' ', 1)[0] + "…"
    return text

def fetch_entries(max_items: int = 45):
    entries = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; PC-HOT-Bot/1.2; +https://github.com)"}

    for source_name, url in RSS_SOURCES:
        try:
            print(f"Fetching {source_name} ...")
            resp = requests.get(url, headers=headers, timeout=18)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)

            count = 0
            for entry in feed.entries[:18]:
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

                cat = get_category(title, summary)
                entries.append({
                    "title": title,
                    "summary": clean_text(summary),
                    "link": link,
                    "source": source_name,
                    "dt": dt or datetime.now(timezone.utc),
                    "category": cat,
                })
                count += 1
            print(f"  → {count} relevant items")
        except Exception as e:
            print(f"  Failed {source_name}: {e}")

    # 去重
    seen = set()
    unique = []
    for e in sorted(entries, key=lambda x: x["dt"], reverse=True):
        key = re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', e["title"].lower())[:50]
        if key not in seen:
            seen.add(key)
            unique.append(e)
        if len(unique) >= max_items:
            break
    return unique

def heat_score(rank: int) -> int:
    base = [238, 201, 168, 135, 112, 94, 80, 68, 58, 50, 44, 39, 34, 30, 27, 24]
    if rank < len(base):
        return base[rank]
    return max(16, 28 - rank)

def render_html(entries):
    now = datetime.now(timezone(timedelta(hours=8)))
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]

    # 热榜
    hot = entries[:8]
    hot_html = ""
    for i, e in enumerate(hot):
        rank_class = "top3" if i < 3 else ""
        hot_html += f"""
      <div class="hot-item" data-cat="{html.escape(e['category'])}">
        <div class="hot-rank {rank_class}">{i+1}</div>
        <div class="hot-content">
          <div class="hot-title">{html.escape(e['title'])}</div>
        </div>
        <div class="hot-heat">{heat_score(i)} 热度</div>
      </div>"""

    # 分类统计
    cat_count = defaultdict(int)
    for e in entries:
        cat_count[e["category"]] += 1
    cat_tags = "".join(
        f'<button class="tag-btn" data-filter="{html.escape(c)}">{html.escape(c)} ({n})</button>'
        for c, n in sorted(cat_count.items(), key=lambda x: -x[1])
    )

    # 分组
    today = now.date()
    yesterday = today - timedelta(days=1)
    groups = defaultdict(list)
    for e in entries:
        d = e["dt"].astimezone(timezone(timedelta(hours=8))).date()
        if d == today:
            groups["今天"].append(e)
        elif d == yesterday:
            groups["昨天"].append(e)
        else:
            groups["更早"].append(e)

    feed_sections = ""
    global_rank = 0
    for label in ["今天", "昨天", "更早"]:
        items = groups[label]
        if not items:
            continue
        if label == "今天":
            day_title = f"今天 {now.strftime('%m月%d日')} {weekday}"
        elif label == "昨天":
            day_title = f"昨天 {(now - timedelta(days=1)).strftime('%m月%d日')}"
        else:
            day_title = "更早内容"

        feed_sections += f'<div class="day-block">\n<div class="day-title">{day_title}</div>\n'
        for e in items:
            time_str = e["dt"].astimezone(timezone(timedelta(hours=8))).strftime("%H:%M")
            heat = heat_score(global_rank)
            global_rank += 1
            cat = e["category"]

            reason_map = {
                "处理器": "处理器相关动态。Intel / AMD / Qualcomm / Nvidia 竞争加剧，值得关注新品与价格。",
                "显卡": "显卡/GPU 动态。当前受 AI 与内存短缺影响较大，价格与供应是关键。",
                "内存存储": "内存与存储新闻。DRAM/NAND 价格是当前 PC 市场最重要的变量之一。",
                "笔记本": "笔记本 / AI PC 方向。本地 AI 能力与续航成为新的产品定义标准。",
                "主板机箱": "主板与机箱相关更新。",
                "市场动态": "市场出货、价格与供应链消息，反映行业整体走势。",
                "综合": "来自公开源聚合，点击标题可阅读原文。",
            }
            reason = reason_map.get(cat, reason_map["综合"])

            feed_sections += f"""
      <article class="feed-item" data-cat="{html.escape(cat)}" data-title="{html.escape(e['title'].lower())}">
        <div class="feed-meta">
          <span class="feed-time">{time_str}</span>
          <span class="feed-source">{html.escape(e['source'])}</span>
          <span class="cat-tag">{html.escape(cat)}</span>
          <span class="feed-heat">{heat} 热度</span>
        </div>
        <div class="feed-title"><a href="{html.escape(e['link'])}" target="_blank" rel="noopener">{html.escape(e['title'])}</a></div>
        <div class="feed-summary">{html.escape(e['summary']) or '（暂无摘要，点击标题查看原文）'}</div>
        <div class="feed-reason"><strong>推荐理由：</strong>{reason}</div>
      </article>"""
        feed_sections += "\n</div>\n"

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PC HOT — PC 行业动态聚合 · 每日精选</title>
  <style>
    :root {{
      --bg: #f7f8fa; --card: #fff; --text: #1a1a1a; --text2: #555; --muted: #888;
      --border: #e8e8e8; --accent: #2563eb; --hot: #ef4444;
    }}
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family: -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background:var(--bg); color:var(--text); line-height:1.6; }}
    a {{ color:inherit; text-decoration:none; }} a:hover {{ color:var(--accent); }}
    header {{ background:var(--card); border-bottom:1px solid var(--border); position:sticky; top:0; z-index:50; }}
    .header-inner {{ max-width:900px; margin:0 auto; padding:14px 20px; display:flex; align-items:center; justify-content:space-between; gap:16px; }}
    .logo {{ display:flex; align-items:center; gap:10px; font-weight:700; font-size:1.2rem; }}
    .logo-badge {{ background:linear-gradient(135deg,#2563eb,#7c3aed); color:#fff; font-size:.7rem; font-weight:700; padding:3px 8px; border-radius:6px; }}
    .search-box {{ flex:1; max-width:280px; }}
    .search-box input {{ width:100%; padding:8px 12px; border:1px solid var(--border); border-radius:8px; font-size:.9rem; outline:none; }}
    .search-box input:focus {{ border-color:var(--accent); }}
    main {{ max-width:900px; margin:0 auto; padding:20px 20px 50px; }}
    .section-header {{ display:flex; align-items:baseline; justify-content:space-between; margin-bottom:14px; }}
    .section-header h2 {{ font-size:1.1rem; font-weight:700; }}
    .section-header .date {{ font-size:.85rem; color:var(--muted); }}
    .tags {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:18px; }}
    .tag-btn {{ background:var(--card); border:1px solid var(--border); padding:5px 12px; border-radius:20px; font-size:.8rem; cursor:pointer; color:var(--text2); transition:.15s; }}
    .tag-btn:hover, .tag-btn.active {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
    .hot-list {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:6px 0; margin-bottom:24px; }}
    .hot-item {{ display:flex; align-items:flex-start; gap:12px; padding:10px 16px; }}
    .hot-item:hover {{ background:#f8fafc; }}
    .hot-rank {{ font-weight:700; font-size:1rem; color:var(--muted); min-width:22px; text-align:center; }}
    .hot-rank.top3 {{ color:var(--hot); }}
    .hot-content {{ flex:1; min-width:0; }}
    .hot-title {{ font-size:.95rem; font-weight:500; }}
    .hot-heat {{ font-size:.8rem; color:var(--hot); font-weight:600; white-space:nowrap; }}
    .stats {{ font-size:.8rem; color:var(--muted); margin-bottom:16px; }}
    .day-block {{ margin-bottom:28px; }}
    .day-title {{ font-size:1.05rem; font-weight:700; margin-bottom:12px; padding-bottom:6px; border-bottom:1px solid var(--border); }}
    .feed-item {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:14px 16px; margin-bottom:10px; }}
    .feed-item:hover {{ border-color:#d0d5dd; box-shadow:0 2px 8px rgba(0,0,0,.04); }}
    .feed-item.hidden {{ display:none; }}
    .feed-meta {{ display:flex; align-items:center; gap:8px; font-size:.78rem; color:var(--muted); margin-bottom:6px; flex-wrap:wrap; }}
    .feed-source {{ color:var(--accent); font-weight:500; }}
    .cat-tag {{ background:#f0f4ff; color:var(--accent); padding:1px 8px; border-radius:4px; font-size:.75rem; }}
    .feed-heat {{ margin-left:auto; color:var(--hot); font-weight:600; }}
    .feed-title {{ font-size:1rem; font-weight:600; margin-bottom:6px; line-height:1.4; }}
    .feed-summary {{ font-size:.88rem; color:var(--text2); margin-bottom:8px; line-height:1.5; }}
    .feed-reason {{ font-size:.82rem; color:var(--muted); background:#f8fafc; border-radius:8px; padding:8px 10px; border-left:3px solid var(--accent); }}
    .feed-reason strong {{ color:var(--text2); }}
    footer {{ max-width:900px; margin:0 auto; padding:20px; border-top:1px solid var(--border); text-align:center; font-size:.8rem; color:var(--muted); }}
    footer p {{ margin-bottom:3px; }}
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <div class="logo">
        <span class="logo-badge">PC</span>
        <span>PC HOT</span>
      </div>
      <div class="search-box">
        <input type="text" id="searchInput" placeholder="搜索标题..." oninput="filterItems()">
      </div>
    </div>
  </header>

  <main>
    <div class="section-header">
      <h2>精选热榜</h2>
      <span class="date">{now.strftime('%m月%d日')} · {weekday}</span>
    </div>

    <div class="hot-list" id="hotList">
{hot_html}
    </div>

    <div class="stats">本次共聚合 <strong>{len(entries)}</strong> 条资讯 · 来自 <strong>{len(set(e['source'] for e in entries))}</strong> 个来源</div>

    <div class="tags" id="tagBar">
      <button class="tag-btn active" data-filter="all">全部</button>
      {cat_tags}
    </div>

    <div class="section-header"><h2>最新精选</h2></div>
{feed_sections}
  </main>

  <footer>
    <p><strong>PC HOT</strong> — PC 行业动态聚合 · 每日精选</p>
    <p>自动更新于 {now.strftime('%Y-%m-%d %H:%M')} (北京时间) · 数据来自公开 RSS</p>
    <p>支持搜索与分类筛选 · 由 GitHub Actions 定时生成</p>
  </footer>

  <script>
    const searchInput = document.getElementById('searchInput');
    const tagBtns = document.querySelectorAll('.tag-btn');
    let currentFilter = 'all';

    tagBtns.forEach(btn => {{
      btn.addEventListener('click', () => {{
        tagBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.dataset.filter;
        filterItems();
      }});
    }});

    function filterItems() {{
      const q = (searchInput.value || '').trim().toLowerCase();
      document.querySelectorAll('.feed-item').forEach(item => {{
        const cat = item.dataset.cat || '';
        const title = item.dataset.title || '';
        const matchCat = currentFilter === 'all' || cat === currentFilter;
        const matchSearch = !q || title.includes(q);
        item.classList.toggle('hidden', !(matchCat && matchSearch));
      }});
    }}
  </script>
</body>
</html>"""
    return html_content

def main():
    print("PC HOT 中文增强版启动...")
    entries = fetch_entries(max_items=45)
    print(f"共获取 {len(entries)} 条相关资讯")
    if not entries:
        print("未获取到内容，保留现有页面")
        return
    html = render_html(entries)
    Path("index.html").write_text(html, encoding="utf-8")
    print("已生成 index.html")

if __name__ == "__main__":
    main()
