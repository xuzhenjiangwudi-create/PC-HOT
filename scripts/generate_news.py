#!/usr/bin/env python3
"""
PC HOT - 完整版生成脚本（支持本地 Ollama Qwen 增强）
功能：
1. 从多源 RSS 抓取 PC 相关新闻
2. 可选：调用本地 Ollama (Qwen) 生成高质量中文推荐理由
3. 生成带搜索、分类标签的中文页面
4. 将历史数据按稳定 ID 保存到 data/news_history.jsonl
"""

import feedparser
import requests
import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re
import html
from collections import Counter, defaultdict

# ==================== 配置区 ====================
# Ollama 设置
USE_OLLAMA = True                    # 是否启用本地大模型增强
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:7b"            # 改成你的模型名
MAX_ENHANCE = 12                     # 最多增强多少条（避免太慢）
MAX_ITEMS = 45                       # 页面显示及单次抓取上限

# 路径设置：假定本文件位于 scripts/generate_news.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "index.html"
HISTORY_FILE = PROJECT_ROOT / "data" / "news_history.jsonl"
HISTORY_RETENTION_DAYS = 0           # 0=永久保留；365=只保留最近一年

# RSS 源
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

CATEGORIES = {
    "处理器": ["cpu", "ryzen", "intel", "core ultra", "snapdragon", "qualcomm", "处理器", "锐龙", "酷睿", "骁龙"],
    "显卡": ["gpu", "rtx", "radeon", "rx ", "graphics", "显卡", "blackwell"],
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
# ================================================


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


def call_qwen(prompt: str, max_tokens: int = 150) -> str:
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.35, "num_predict": max_tokens}
            },
            timeout=90
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"    模型调用失败: {e}")
        return ""


def enhance_reason(title: str, summary: str, category: str) -> str:
    prompt = f"""你是一名专业的 PC 硬件媒体编辑。请根据新闻写 1-2 句中文「推荐理由」。

要求：
- 不要复述标题
- 指出为什么值得关注（价格、性能、生态、供应链等）
- 客观专业，不超过 55 字
- 直接输出理由，不要加任何前缀

标题：{title}
摘要：{summary or '无'}
分类：{category}

推荐理由："""
    result = call_qwen(prompt, 100)
    if not result:
        return default_reason(category)
    result = result.replace("推荐理由：", "").replace("推荐理由", "").strip()
    return result[:90] if result else default_reason(category)


def default_reason(category: str) -> str:
    return {
        "处理器": "处理器相关动态，Intel/AMD/Qualcomm/Nvidia 竞争值得关注。",
        "显卡": "显卡动态，受 AI 与内存短缺影响较大，关注价格与供应。",
        "内存存储": "内存与存储新闻，DRAM/NAND 价格是当前市场关键变量。",
        "笔记本": "笔记本/AI PC 方向，本地 AI 能力成为新定义标准。",
        "主板机箱": "主板与机箱相关更新。",
        "市场动态": "市场出货、价格与供应链消息，反映行业走势。",
        "综合": "来自公开源聚合，点击标题可阅读原文。",
    }.get(category, "来自公开源聚合，点击标题可阅读原文。")


def fetch_entries(max_items: int = 45):
    entries = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; PC-HOT-Bot/1.3)"}

    for source_name, url in RSS_SOURCES:
        try:
            print(f"抓取 {source_name} ...")
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
                    "reason": "",
                })
                count += 1
            print(f"  → {count} 条")
        except Exception as e:
            print(f"  失败: {e}")

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


def generate_news_id(entry: dict) -> str:
    """生成稳定新闻 ID：优先使用原文链接，否则使用来源和规范化标题。"""
    link = entry.get("link", "").strip()
    raw_key = link or "|".join([
        entry.get("source", "").strip().lower(),
        re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', entry.get("title", "").lower())[:100],
    ])
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:20]


def entry_to_history_record(entry: dict) -> dict:
    """把当次抓取结果转换为历史记录。"""
    dt = entry.get("dt")
    published_at = dt.isoformat() if isinstance(dt, datetime) else str(dt or "")
    now_text = datetime.now(timezone(timedelta(hours=8))).isoformat()
    return {
        "id": generate_news_id(entry),
        "title": entry.get("title", ""),
        "summary": entry.get("summary", ""),
        "link": entry.get("link", ""),
        "source": entry.get("source", ""),
        "published_at": published_at,
        "first_collected_at": now_text,
        "last_seen_at": now_text,
        "category": entry.get("category", "综合"),
        "reason": entry.get("reason") or default_reason(entry.get("category", "综合")),
        "ai_enhanced": bool(entry.get("reason")),
    }


def load_history() -> list[dict]:
    """读取 JSONL 历史文件。单行损坏只跳过该行。"""
    if not HISTORY_FILE.exists():
        return []
    records = []
    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if isinstance(record, dict) and record.get("id"):
                        records.append(record)
                    else:
                        print(f"历史文件第 {line_number} 行缺少有效 ID，已跳过")
                except json.JSONDecodeError as exc:
                    print(f"历史文件第 {line_number} 行解析失败，已跳过: {exc}")
    except OSError as exc:
        print(f"读取历史文件失败: {exc}")
    return records


def parse_iso_datetime(value: str):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def prune_history(records: list[dict]) -> list[dict]:
    """根据 HISTORY_RETENTION_DAYS 清理旧数据；0 表示永久保留。"""
    if HISTORY_RETENTION_DAYS <= 0:
        return records
    cutoff = datetime.now(timezone.utc) - timedelta(days=HISTORY_RETENTION_DAYS)
    retained = []
    for record in records:
        published = parse_iso_datetime(record.get("published_at", ""))
        if published is None or published.astimezone(timezone.utc) >= cutoff:
            retained.append(record)
    return retained


def save_history(entries: list[dict]) -> dict:
    """按稳定 ID 合并新闻，并通过临时文件原子写入 JSONL。"""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing = load_history()
    records_by_id = {r["id"]: r for r in existing if r.get("id")}
    added = updated = unchanged = 0

    for entry in entries:
        new_record = entry_to_history_record(entry)
        record_id = new_record["id"]
        old_record = records_by_id.get(record_id)
        if old_record is None:
            records_by_id[record_id] = new_record
            added += 1
            continue

        new_record["first_collected_at"] = old_record.get(
            "first_collected_at", old_record.get("collected_at", new_record["first_collected_at"])
        )
        # 旧记录已经由 AI 增强，而本次没有增强时，保留旧的 AI 推荐理由。
        if old_record.get("ai_enhanced") and not new_record.get("ai_enhanced"):
            new_record["reason"] = old_record.get("reason", new_record["reason"])
            new_record["ai_enhanced"] = True

        compare_fields = ["title", "summary", "link", "source", "published_at", "category", "reason", "ai_enhanced"]
        changed = any(old_record.get(k) != new_record.get(k) for k in compare_fields)
        records_by_id[record_id] = {**old_record, **new_record}
        if changed:
            updated += 1
        else:
            unchanged += 1

    records = prune_history(list(records_by_id.values()))
    records.sort(key=lambda r: r.get("published_at", ""), reverse=True)

    temp_path = HISTORY_FILE.with_suffix(".jsonl.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as file:
            for record in records:
                file.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, HISTORY_FILE)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)

    return {"total": len(records), "added": added, "updated": updated, "unchanged": unchanged}


def get_history_stats(days: int = 30) -> dict:
    """提供最近 N 天统计，供未来趋势图或简报调用。"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent = []
    for record in load_history():
        published = parse_iso_datetime(record.get("published_at", ""))
        if published and published.astimezone(timezone.utc) >= cutoff:
            recent.append(record)
    return {
        "days": days,
        "total": len(recent),
        "categories": Counter(r.get("category", "综合") for r in recent).most_common(),
        "sources": Counter(r.get("source", "") for r in recent if r.get("source")).most_common(),
    }


def heat_score(rank: int) -> int:
    base = [238, 201, 168, 135, 112, 94, 80, 68, 58, 50, 44, 39, 34, 30, 27, 24]
    return base[rank] if rank < len(base) else max(16, 28 - rank)


def render_html(entries):
    now = datetime.now(timezone(timedelta(hours=8)))
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]

    hot = entries[:8]
    hot_html = ""
    for i, e in enumerate(hot):
        rank_class = "top3" if i < 3 else ""
        hot_html += f"""
      <div class="hot-item">
        <div class="hot-rank {rank_class}">{i+1}</div>
        <div class="hot-content"><div class="hot-title">{html.escape(e['title'])}</div></div>
        <div class="hot-heat">{heat_score(i)} 热度</div>
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
            heat = heat_score(global_rank)
            global_rank += 1
            reason = e.get("reason") or default_reason(e["category"])

            feed_sections += f"""
      <article class="feed-item" data-cat="{html.escape(e['category'])}" data-title="{html.escape(e['title'].lower())}">
        <div class="feed-meta">
          <span class="feed-time">{time_str}</span>
          <span class="feed-source">{html.escape(e['source'])}</span>
          <span class="cat-tag">{html.escape(e['category'])}</span>
          <span class="feed-heat">{heat} 热度</span>
        </div>
        <div class="feed-title"><a href="{html.escape(e['link'])}" target="_blank" rel="noopener">{html.escape(e['title'])}</a></div>
        <div class="feed-summary">{html.escape(e['summary']) or '（暂无摘要）'}</div>
        <div class="feed-reason"><strong>推荐理由：</strong>{html.escape(reason)}</div>
      </article>"""
        feed_sections += "\n</div>\n"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PC HOT — PC 行业动态聚合 · 每日精选</title>
  <style>
    :root {{ --bg:#f7f8fa; --card:#fff; --text:#1a1a1a; --text2:#555; --muted:#888; --border:#e8e8e8; --accent:#2563eb; --hot:#ef4444; }}
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background:var(--bg); color:var(--text); line-height:1.6; }}
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
    .tag-btn {{ background:var(--card); border:1px solid var(--border); padding:5px 12px; border-radius:20px; font-size:.8rem; cursor:pointer; color:var(--text2); }}
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
    <div class="section-header"><h2>精选热榜</h2><span class="date">{now.strftime('%m月%d日')} · {weekday}</span></div>
    <div class="hot-list">{hot_html}</div>
    <div class="stats">本次共聚合 <strong>{len(entries)}</strong> 条资讯 · 来自 <strong>{len(set(e['source'] for e in entries))}</strong> 个来源{' · 已用本地 Qwen 增强' if USE_OLLAMA else ''}</div>
    <div class="tags" id="tagBar">
      <button class="tag-btn active" data-filter="all">全部</button>
      {cat_tags}
    </div>
    <div class="section-header"><h2>最新精选</h2></div>
    {feed_sections}
  </main>
  <footer>
    <p><strong>PC HOT</strong> — PC 行业动态聚合 · 每日精选</p>
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
        item.classList.toggle('hidden', !((currentFilter === 'all' || cat === currentFilter) && (!q || title.includes(q))));
      }});
    }}
  </script>
</body>
</html>"""


def main():
    print("=" * 50)
    print("PC HOT 完整版生成（支持本地 Qwen）")
    print("=" * 50)

    if USE_OLLAMA:
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            print(f"检测到模型: {models}")
        except Exception as e:
            print(f"无法连接 Ollama: {e}")
            print("将使用默认推荐理由继续生成")
            globals()["USE_OLLAMA"] = False

    entries = fetch_entries(MAX_ITEMS)
    print(f"\n共获取 {len(entries)} 条相关资讯")

    if USE_OLLAMA and entries:
        print(f"\n开始用 {MODEL_NAME} 增强前 {min(MAX_ENHANCE, len(entries))} 条推荐理由...")
        for i, e in enumerate(entries[:MAX_ENHANCE]):
            print(f"  [{i+1}/{min(MAX_ENHANCE, len(entries))}] {e['title'][:40]}...")
            e["reason"] = enhance_reason(e["title"], e["summary"], e["category"])
            print(f"      → {e['reason']}")

    history_result = save_history(entries)
    print(
        "\n历史数据保存完成："
        f"新增 {history_result['added']} 条，"
        f"更新 {history_result['updated']} 条，"
        f"未变化 {history_result['unchanged']} 条，"
        f"累计 {history_result['total']} 条"
    )
    print(f"历史文件：{HISTORY_FILE}")

    output_html = render_html(entries)
    OUTPUT_PATH.write_text(output_html, encoding="utf-8")
    print(f"\n已生成 {OUTPUT_PATH}（本次展示 {len(entries)} 条）")
    print('接下来执行: git add index.html data/news_history.jsonl && git commit -m "update PC HOT history" && git push')


if __name__ == "__main__":
    main()
