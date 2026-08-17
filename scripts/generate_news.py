#!/usr/bin/env python3
"""
PC HOT - 聚焦 PC 行业 + 成本优先版
重点关注：PC 硬件、价格、内存/显卡成本、供应链、出货量
支持本地 Ollama Qwen 生成推荐理由
"""

import feedparser
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re
import html
from collections import defaultdict

# ==================== 配置 ====================
USE_OLLAMA = True
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:7b"
MAX_ENHANCE = 15

RSS_SOURCES = [
    ("IT之家", "https://www.ithome.com/rss/"),
    ("HotHardware", "https://hothardware.com/rss"),
    ("Tom's Hardware", "https://www.tomshardware.com/feeds/all"),
    ("TechSpot", "https://www.techspot.com/backend.xml"),
    ("PC Perspective", "https://pcper.com/feed/"),
    ("PCWorld", "https://www.pcworld.com/feed"),
    ("PC Gamer", "https://www.pcgamer.com/feeds/tag/hardware"),
    ("Windows Central", "https://www.windowscentral.com/feeds.xml"),
    ("TechPowerUp", "https://www.techpowerup.com/rss/news"),
]

# 成本/价格相关关键词（高权重）
COST_KEYWORDS = [
    "price", "pricing", "cost", "expensive", "cheap", "hike", "increase", "rise", "soar",
    "shortage", "supply", "memory crunch", "dram", "nand", "hbm", "bom",
    "涨价", "降价", "价格", "成本", "短缺", "供应", "内存", "显存", "合约价", "现货",
    "出货", "shipment", "asps", "average selling", "margin"
]

# PC 核心关键词
PC_KEYWORDS = [
    "pc", "laptop", "notebook", "desktop", "cpu", "gpu", "rtx", "rx ", "ryzen", "intel", "amd",
    "nvidia", "memory", "ram", "ddr5", "ddr4", "ssd", "nvme", "motherboard",
    "asus", "msi", "gigabyte", "lenovo", "dell", "hp", "apple", "macbook",
    "windows", "ai pc", "snapdragon", "qualcomm", "computex", "processor", "graphics",
    "mini pc", "nuc", "rog", "legion", "core ultra", "zen ", "blackwell", "rdna",
    "电脑", "笔记本", "显卡", "处理器", "内存", "固态", "主板", "华硕", "微星", "技嘉",
    "联想", "戴尔", "惠普", "锐龙", "酷睿", "骁龙", "装机"
]

CATEGORIES = {
    "成本价格": COST_KEYWORDS + ["price", "cost", "涨价", "降价", "短缺", "供应"],
    "内存存储": ["memory", "ram", "ddr", "ssd", "nvme", "dram", "nand", "hbm", "存储", "内存", "固态", "显存"],
    "显卡": ["gpu", "rtx", "radeon", "rx ", "graphics", "显卡", "blackwell"],
    "处理器": ["cpu", "ryzen", "intel", "core ultra", "snapdragon", "qualcomm", "处理器", "锐龙", "酷睿", "骁龙"],
    "笔记本": ["laptop", "notebook", "ai pc", "macbook", "笔记本", "轻薄本", "游戏本"],
    "市场出货": ["shipment", "market", "出货", "销量", "份额", "idc", "counterpoint", "omdia"],
    "主板机箱": ["motherboard", "chipset", "case", "主板", "机箱"],
}

def is_relevant(title: str, summary: str = "") -> bool:
    text = (title + " " + summary).lower()
    # 必须命中 PC 相关关键词
    if not any(kw.lower() in text for kw in PC_KEYWORDS):
        return False
    return True

def is_cost_related(title: str, summary: str = "") -> bool:
    text = (title + " " + summary).lower()
    return any(kw.lower() in text for kw in COST_KEYWORDS)

def get_category(title: str, summary: str = "") -> str:
    text = (title + " " + summary).lower()
    # 优先判断成本类
    if is_cost_related(title, summary):
        return "成本价格"
    for cat, kws in CATEGORIES.items():
        if cat == "成本价格":
            continue
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

def call_qwen(prompt: str, max_tokens: int = 120) -> str:
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": max_tokens}
            },
            timeout=90
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"    模型调用失败: {e}")
        return ""

def enhance_reason(title: str, summary: str, category: str, cost_flag: bool) -> str:
    cost_hint = "特别关注其对 PC 整机成本、显卡/内存价格或供应链的影响。" if cost_flag else "从 PC 用户和行业角度指出价值。"
    prompt = f"""你是 PC 硬件与成本分析编辑。请为下面新闻写 1-2 句中文推荐理由。

要求：
- 不要复述标题
- {cost_hint}
- 客观、简洁，不超过 55 字
- 直接输出，不要前缀

标题：{title}
摘要：{summary or '无'}
分类：{category}

推荐理由："""
    result = call_qwen(prompt, 90)
    if not result:
        return default_reason(category, cost_flag)
    result = result.replace("推荐理由：", "").replace("推荐理由", "").strip()
    return result[:85] if result else default_reason(category, cost_flag)

def default_reason(category: str, cost_flag: bool = False) -> str:
    if cost_flag or category == "成本价格":
        return "涉及价格或供应链变化，对 PC 整机成本影响较大，建议关注。"
    return {
        "内存存储": "内存/存储动态，直接影响 PC 成本和配置选择。",
        "显卡": "显卡相关，当前价格与供应受 AI 需求挤压明显。",
        "处理器": "处理器动态，影响整机性能与定价策略。",
        "笔记本": "笔记本/AI PC 方向，成本与续航是关键决策因素。",
        "市场出货": "出货与市场数据，反映行业真实需求与价格压力。",
        "主板机箱": "主板/机箱更新。",
        "综合": "PC 行业相关资讯。",
    }.get(category, "PC 行业相关资讯。")

def fetch_entries(max_items: int = 50):
    entries = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; PC-HOT-Bot/1.4)"}

    for source_name, url in RSS_SOURCES:
        try:
            print(f"抓取 {source_name} ...")
            resp = requests.get(url, headers=headers, timeout=18)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            count = 0
            for entry in feed.entries[:20]:
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
                cost_flag = is_cost_related(title, summary)
                cat = get_category(title, summary)
                entries.append({
                    "title": title,
                    "summary": clean_text(summary),
                    "link": link,
                    "source": source_name,
                    "dt": dt or datetime.now(timezone.utc),
                    "category": cat,
                    "cost_flag": cost_flag,
                    "reason": "",
                })
                count += 1
            print(f"  → {count} 条")
        except Exception as e:
            print(f"  失败: {e}")

    # 去重 + 成本优先排序
    seen = set()
    unique = []
    for e in sorted(entries, key=lambda x: (not x["cost_flag"], -x["dt"].timestamp())):
        key = re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', e["title"].lower())[:50]
        if key not in seen:
            seen.add(key)
            unique.append(e)
        if len(unique) >= max_items:
            break
    return unique

def heat_score(rank: int, cost_flag: bool = False) -> int:
    base = [245, 210, 175, 145, 120, 100, 85, 72, 60, 52, 45, 40, 35, 30, 26, 22]
    score = base[rank] if rank < len(base) else max(15, 25 - rank)
    if cost_flag:
        score = min(255, score + 25)  # 成本类加权
    return score

def render_html(entries):
    now = datetime.now(timezone(timedelta(hours=8)))
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]

    # 热榜：成本相关优先展示
    cost_entries = [e for e in entries if e["cost_flag"]]
    other_entries = [e for e in entries if not e["cost_flag"]]
    hot_candidates = (cost_entries + other_entries)[:10]

    hot_html = ""
    for i, e in enumerate(hot_candidates[:8]):
        rank_class = "top3" if i < 3 else ""
        cost_mark = " · 成本" if e["cost_flag"] else ""
        hot_html += f"""
      <div class="hot-item">
        <div class="hot-rank {rank_class}">{i+1}</div>
        <div class="hot-content">
          <div class="hot-title">{html.escape(e['title'])}</div>
        </div>
        <div class="hot-heat">{heat_score(i, e['cost_flag'])} 热度{cost_mark}</div>
      </div>"""

    cat_count = defaultdict(int)
    for e in entries:
        cat_count[e["category"]] += 1
    cat_tags = "".join(
        f'<button class="tag-btn" data-filter="{html.escape(c)}">{html.escape(c)} ({n})</button>'
        for c, n in sorted(cat_count.items(), key=lambda x: -x[1])
    )

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
            heat = heat_score(global_rank, e["cost_flag"])
            global_rank += 1
            reason = e.get("reason") or default_reason(e["category"], e["cost_flag"])
            cost_badge = '<span class="cost-badge">成本相关</span>' if e["cost_flag"] else ""

            feed_sections += f"""
      <article class="feed-item" data-cat="{html.escape(e['category'])}" data-title="{html.escape(e['title'].lower())}" data-cost="{'1' if e['cost_flag'] else '0'}">
        <div class="feed-meta">
          <span class="feed-time">{time_str}</span>
          <span class="feed-source">{html.escape(e['source'])}</span>
          <span class="cat-tag">{html.escape(e['category'])}</span>
          {cost_badge}
          <span class="feed-heat">{heat} 热度</span>
        </div>
        <div class="feed-title"><a href="{html.escape(e['link'])}" target="_blank" rel="noopener">{html.escape(e['title'])}</a></div>
        <div class="feed-summary">{html.escape(e['summary']) or '（暂无摘要）'}</div>
        <div class="feed-reason"><strong>推荐理由：</strong>{html.escape(reason)}</div>
      </article>"""
        feed_sections += "\n</div>\n"

    cost_count = sum(1 for e in entries if e["cost_flag"])

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PC HOT — PC 行业与成本动态</title>
  <style>
    :root {{ --bg:#f7f8fa; --card:#fff; --text:#1a1a1a; --text2:#555; --muted:#888; --border:#e8e8e8; --accent:#2563eb; --hot:#ef4444; --cost:#d97706; }}
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background:var(--bg); color:var(--text); line-height:1.6; }}
    a {{ color:inherit; text-decoration:none; }} a:hover {{ color:var(--accent); }}
    header {{ background:var(--card); border-bottom:1px solid var(--border); position:sticky; top:0; z-index:50; }}
    .header-inner {{ max-width:900px; margin:0 auto; padding:14px 20px; display:flex; align-items:center; justify-content:space-between; gap:16px; }}
    .logo {{ display:flex; align-items:center; gap:10px; font-weight:700; font-size:1.2rem; }}
    .logo-badge {{ background:linear-gradient(135deg,#2563eb,#7c3aed); color:#fff; font-size:.7rem; font-weight:700; padding:3px 8px; border-radius:6px; }}
    .search-box {{ flex:1; max-width:260px; }}
    .search-box input {{ width:100%; padding:8px 12px; border:1px solid var(--border); border-radius:8px; font-size:.9rem; outline:none; }}
    .search-box input:focus {{ border-color:var(--accent); }}
    main {{ max-width:900px; margin:0 auto; padding:20px 20px 50px; }}
    .section-header {{ display:flex; align-items:baseline; justify-content:space-between; margin-bottom:14px; }}
    .section-header h2 {{ font-size:1.1rem; font-weight:700; }}
    .section-header .date {{ font-size:.85rem; color:var(--muted); }}
    .tags {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:18px; }}
    .tag-btn {{ background:var(--card); border:1px solid var(--border); padding:5px 12px; border-radius:20px; font-size:.8rem; cursor:pointer; color:var(--text2); }}
    .tag-btn:hover, .tag-btn.active {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
    .tag-btn.cost-filter {{ border-color:#fbbf24; color:var(--cost); }}
    .tag-btn.cost-filter.active {{ background:var(--cost); color:#fff; border-color:var(--cost); }}
    .hot-list {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:6px 0; margin-bottom:24px; }}
    .hot-item {{ display:flex; align-items:flex-start; gap:12px; padding:10px 16px; }}
    .hot-item:hover {{ background:#f8fafc; }}
    .hot-rank {{ font-weight:700; font-size:1rem; color:var(--muted); min-width:22px; text-align:center; }}
    .hot-rank.top3 {{ color:var(--hot); }}
    .hot-content {{ flex:1; min-width:0; }}
    .hot-title {{ font-size:.95rem; font-weight:500; }}
    .hot-heat {{ font-size:.78rem; color:var(--hot); font-weight:600; white-space:nowrap; }}
    .stats {{ font-size:.8rem; color:var(--muted); margin-bottom:16px; }}
    .day-block {{ margin-bottom:28px; }}
    .day-title {{ font-size:1.05rem; font-weight:700; margin-bottom:12px; padding-bottom:6px; border-bottom:1px solid var(--border); }}
    .feed-item {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:14px 16px; margin-bottom:10px; }}
    .feed-item:hover {{ border-color:#d0d5dd; box-shadow:0 2px 8px rgba(0,0,0,.04); }}
    .feed-item.hidden {{ display:none; }}
    .feed-meta {{ display:flex; align-items:center; gap:8px; font-size:.78rem; color:var(--muted); margin-bottom:6px; flex-wrap:wrap; }}
    .feed-source {{ color:var(--accent); font-weight:500; }}
    .cat-tag {{ background:#f0f4ff; color:var(--accent); padding:1px 8px; border-radius:4px; font-size:.75rem; }}
    .cost-badge {{ background:#fef3c7; color:var(--cost); padding:1px 8px; border-radius:4px; font-size:.75rem; font-weight:600; }}
    .feed-heat {{ margin-left:auto; color:var(--hot); font-weight:600; }}
    .feed-title {{ font-size:1rem; font-weight:600; margin-bottom:6px; line-height:1.4; }}
    .feed-summary {{ font-size:.88rem; color:var(--text2); margin-bottom:8px; line-height:1.5; }}
    .feed-reason {{ font-size:.82rem; color:var(--muted); background:#f8fafc; border-radius:8px; padding:8px 10px; border-left:3px solid var(--accent); }}
    .feed-reason strong {{ color:var(--text2); }}
    footer {{ max-width:900px; margin:0 auto; padding:20px; border-top:1px solid var(--border); text-align:center; font-size:.8rem; color:var(--muted); }}
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <div class="logo"><span class="logo-badge">PC</span><span>PC HOT</span></div>
      <div class="search-box"><input type="text" id="searchInput" placeholder="搜索标题..." oninput="filterItems()"></div>
    </div>
  </header>
  <main>
    <div class="section-header">
      <h2>精选热榜（成本优先）</h2>
      <span class="date">{now.strftime('%m月%d日')} · {weekday}</span>
    </div>
    <div class="hot-list">{hot_html}</div>
    <div class="stats">
      本次聚合 <strong>{len(entries)}</strong> 条 · 其中成本/价格相关 <strong>{cost_count}</strong> 条 · 来自 {len(set(e['source'] for e in entries))} 个来源
      {' · 已用本地 Qwen 增强' if USE_OLLAMA else ''}
    </div>
    <div class="tags" id="tagBar">
      <button class="tag-btn active" data-filter="all">全部</button>
      <button class="tag-btn cost-filter" data-filter="cost">只看成本相关</button>
      {cat_tags}
    </div>
    <div class="section-header"><h2>最新精选</h2></div>
    {feed_sections}
  </main>
  <footer>
    <p><strong>PC HOT</strong> — 聚焦 PC 行业与成本动态</p>
    <p>更新于 {now.strftime('%Y-%m-%d %H:%M')} (北京时间)</p>
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
        const isCost = item.dataset.cost === '1';
        let match = true;
        if (currentFilter === 'cost') match = isCost;
        else if (currentFilter !== 'all') match = cat === currentFilter;
        if (q && !title.includes(q)) match = false;
        item.classList.toggle('hidden', !match);
      }});
    }}
  </script>
</body>
</html>"""


def main():
    print("=" * 50)
    print("PC HOT · 聚焦 PC 行业 + 成本优先")
    print("=" * 50)

    if USE_OLLAMA:
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            print(f"检测到模型: {models}")
        except Exception as e:
            print(f"无法连接 Ollama: {e}，将使用默认推荐理由")
            globals()["USE_OLLAMA"] = False

    entries = fetch_entries(50)
    print(f"\n共获取 {len(entries)} 条 PC 相关资讯")
    cost_n = sum(1 for e in entries if e["cost_flag"])
    print(f"其中成本/价格相关: {cost_n} 条")

    if USE_OLLAMA and entries:
        print(f"\n用 {MODEL_NAME} 增强前 {min(MAX_ENHANCE, len(entries))} 条推荐理由...")
        for i, e in enumerate(entries[:MAX_ENHANCE]):
            print(f"  [{i+1}] {e['title'][:42]}...")
            e["reason"] = enhance_reason(e["title"], e["summary"], e["category"], e["cost_flag"])
            print(f"      → {e['reason']}")

    html = render_html(entries)
    Path("index.html").write_text(html, encoding="utf-8")
    print(f"\n已生成 index.html")

    # 发送邮件通知
    try:
        from send_email import send_daily_report
        top = [e["title"] for e in entries[:6]]
        cost_n = sum(1 for e in entries if e.get("cost_flag"))
        send_daily_report(entry_count=len(entries), cost_count=cost_n, top_titles=top)
    except Exception as e:
        print("邮件通知跳过:", e)

    print("执行: git add index.html && git commit -m \"focus cost\" && git push --force")


if __name__ == "__main__":
    main()
