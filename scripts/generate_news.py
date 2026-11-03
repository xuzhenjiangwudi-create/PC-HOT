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
import json
import hashlib
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
    ("Notebookcheck", "https://www.notebookcheck.net/RSS-Feed-All-Articles-EN.165552.0.html"),
    ("Laptop Mag", "https://www.laptopmag.com/feeds/all"),
]

# 成本/价格相关关键词（高权重）
COST_KEYWORDS = [
    "price", "pricing", "cost", "expensive", "hike", "shortage", "涨价", "降价",
    "价格", "成本", "短缺", "合约价", "asp", "bom", "supply"
]

# PC 核心关键词
PC_KEYWORDS = [
    # 笔记本核心
    "laptop", "notebook", "ultrabook", "chromebook", "macbook", "ai pc", "copilot+ pc",
    "notebooks", "laptops", "portable", "thin and light", "gaming laptop", "workstation",
    "笔记本", "轻薄本", "游戏本", "商务本", "二合一",
    # OEM
    "lenovo", "thinkpad", "yoga", "legion", "dell", "xps", "latitude", "alienware",
    "hp", "hewlett", "elitebook", "probook", "spectre", "omen", "asus", "zenbook",
    "vivobook", "rog", "tuf", "acer", "swift", "predator", "msi", "razer", "blade",
    "samsung galaxy book", "huawei matebook", "honor magicbook", "xiaomi notebook",
    "联想", "戴尔", "惠普", "华硕", "宏碁", "机械革命", "神舟", "荣耀", "华为",
    # ODM
    "quanta", "compal", "wistron", "pegatron", "inventec", "huaqin", "luxshare",
    "广达", "仁宝", "纬创", "和硕", "英业达", "华勤", "立讯", "翼辉",
    # AI / AI PC / 芯片
    "ai pc", "npu", "copilot", "snapdragon x", "qualcomm", "lunar lake", "arrow lake",
    "meteor lake", "strix point", "hawk point", "ryzen ai", "core ultra", "intel vpu",
    "hexagon npu", "40 tops", "45 tops", "npu tops", "on-device ai", "local ai",
    "骁龙", "锐龙 ai", "酷睿 ultra", "端侧 ai", "本地 ai",
    # 相关硬件但仍偏本本
    "battery", "oled laptop", "laptop gpu", "mobile rtx", "mxm",
]

CATEGORIES = {
    "AI与芯片": [
        "ai pc", "npu", "copilot", "snapdragon", "qualcomm", "lunar lake", "ryzen ai",
        "core ultra", "tops", "on-device", "端侧", "本地 ai", "骁龙", "npu"
    ],
    "OEM品牌": [
        "lenovo", "dell", "hp", "asus", "acer", "msi", "razer", "samsung", "huawei",
        "联想", "戴尔", "惠普", "华硕", "宏碁", "thinkpad", "xps", "zenbook", "legion"
    ],
    "ODM代工": [
        "quanta", "compal", "wistron", "pegatron", "inventec", "huaqin", "luxshare",
        "广达", "仁宝", "纬创", "和硕", "英业达", "华勤", "立讯", "odm"
    ],
    "成本价格": [
        "price", "cost", "涨价", "降价", "价格", "成本", "短缺", "shortage", "asp", "bom"
    ],
    "市场出货": [
        "shipment", "market", "出货", "销量", "份额", "idc", "canalys", "counterpoint"
    ],
    "产品发布": [
        "launch", "unveil", "announce", "发布", "上市", "首发", "新款", "refresh"
    ],
}

def is_relevant(title: str, summary: str = "") -> bool:
    text = (title + " " + summary).lower()
    # 硬排除明显无关
    exclude = [
        "ferrari", "electric car", "expressvpn", "vpn deal",
        "microsoft project professional", "word, excel, powerpoint",
        "instagram", "facebook", "儿童沉迷", "起诉 meta",
        "mortal shell", "sinking city", "viper v4 pro", "zalman cnps",
        "iphone", "smartphone only", "carrier pidge",
        "马自达", "享界", "鸿蒙智行", "电动汽车", "充电桩",
        "google maps", "spaceflight", "spacex",
        "股票代码", "持股比例", "市值",
    ]
    if any(ex in text for ex in exclude):
        return False

    # 强信号：直接关于笔记本/PC，单条命中即通过
    strong_keys = [
        "laptop", "notebook", "macbook", "ultrabook", "chromebook", "ai pc",
        "gaming laptop", "thinkpad", "yoga", "xps", "latitude", "elitebook",
        "zenbook", "vivobook", "spectre", "omen", "legion", "framework laptop",
        "笔记本", "轻薄本", "游戏本", "商务本", "二合一",
        "mini pc", "gaming pc", "prebuilt", "desktop pc",
        "snapdragon x", "ryzen ai", "core ultra", "lunar lake", "panther lake",
        "strix point", "copilot+", "npu", "端侧",
        "quanta", "compal", "wistron", "pegatron", "inventec", "huaqin",
        "广达", "仁宝", "纬创", "和硕", "英业达", "华勤", "立讯", "odm",
        "ddr5", "dram", "hbm", "ssd", "laptop gpu", "laptop cpu",
        "mobile rtx", "rtx 50", "rtx 40", "rtx 30",
        "pc market", "notebook shipment",
        "windows on arm", "windows 11", "windows 12",
    ]
    if any(k in text for k in strong_keys):
        return True

    # 弱信号：芯片公司/OEM/通用词，需至少 2 个不同信号同时命中
    weak_keys = [
        "lenovo", "dell", "hp ", "asus", "acer", "msi", "razer",
        "联想", "戴尔", "惠普", "华硕",
        "intel", "amd", "nvidia", "qualcomm", "snapdragon",
        "cpu", "gpu", "processor", "desktop", "motherboard",
        "rtx", "radeon", "geforce",
        "涨价", "短缺", "出货", "shipment", "price", "cost",
        "内存", "硬盘", "主板",
    ]
    matches = sum(1 for k in weak_keys if k in text)
    return matches >= 2


def is_cost_related(title: str, summary: str = "") -> bool:
    text = (title + " " + summary).lower()
    strong = [
        "price", "pricing", "cost", "expensive", "hike", "shortage", "涨价", "降价",
        "价格", "成本", "短缺", "合约价", "现货", "bom", "memory crunch", "asps",
        "$", "美元", "元", "涨至", "降至", "supply chain"
    ]
    return any(kw.lower() in text for kw in strong)

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
        return "涉及价格或供应链变化，对笔记本整机成本与出货影响较大。"
    return {
        "AI与芯片": "AI PC / NPU / 端侧算力相关，影响下一代笔记本产品定义。",
        "OEM品牌": "联想/戴尔/惠普/华硕等品牌动态，关注产品与出货策略。",
        "ODM代工": "广达/仁宝/纬创/华勤等代工厂动态，反映笔记本供应链走势。",
        "市场出货": "笔记本出货与市场份额数据，反映真实需求。",
        "产品发布": "笔记本新品发布，关注定位、配置与价格。",
        "成本价格": "价格与成本相关，影响整机定价与利润。",
        "综合": "笔记本电脑行业相关资讯。",
    }.get(category, "笔记本电脑行业相关资讯。")


def is_mostly_chinese(s: str) -> bool:
    if not s:
        return False
    cn = sum(1 for c in s if "一" <= c <= "鿿")
    return cn > max(2, len(s) * 0.15)


def translate_with_qwen(text: str, to_lang: str) -> str:
    """to_lang: 'zh' or 'en'"""
    if not text or not text.strip():
        return text
    if to_lang == "zh":
        prompt = f"""将下面的英文翻译成简洁自然的中文，只输出译文，不要解释：\n\n{text[:500]}"""
    else:
        prompt = f"""Translate the following Chinese into clear, concise English. Output only the translation:\n\n{text[:500]}"""
    result = call_qwen(prompt, max_tokens=180)
    return result.strip() if result else text


def bilingual_fields(title: str, summary: str, reason: str, cost_flag: bool, category: str):
    """Return title_zh, title_en, summary_zh, summary_en, reason_zh, reason_en"""
    if is_mostly_chinese(title):
        title_zh, title_en = title, (translate_with_qwen(title, "en") if USE_OLLAMA else title)
    else:
        title_en, title_zh = title, (translate_with_qwen(title, "zh") if USE_OLLAMA else title)

    if summary:
        if is_mostly_chinese(summary):
            summary_zh, summary_en = summary, (translate_with_qwen(summary, "en") if USE_OLLAMA else summary)
        else:
            summary_en, summary_zh = summary, (translate_with_qwen(summary, "zh") if USE_OLLAMA else summary)
    else:
        summary_zh, summary_en = "", ""

    # reason is usually Chinese from our prompts; make EN version
    reason_zh = reason or default_reason(category, cost_flag)
    if USE_OLLAMA and reason_zh:
        reason_en = translate_with_qwen(reason_zh, "en") or reason_zh
    else:
        reason_en = reason_zh

    return title_zh, title_en, summary_zh, summary_en, reason_zh, reason_en


def extract_image(entry) -> str:
    """从 RSS entry 中提取图片 URL，找不到返回空字符串"""
    # media:thumbnail / media:content
    for media_key in ["media_thumbnail", "media_content"]:
        media_list = entry.get(media_key, [])
        if media_list:
            url = media_list[0].get("url", "")
            if url and url.startswith("http"):
                return url
    # enclosure (image type)
    for enc in entry.get("enclosures", []):
        href = enc.get("href", "")
        mtype = enc.get("type", "")
        if href.startswith("http") and ("image" in mtype or href.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))):
            return href
    # <img> inside summary/content
    for field in ["summary", "content", "description", "summary_detail"]:
        raw = entry.get(field, "")
        if isinstance(raw, dict):
            raw = raw.get("value", "")
        if raw:
            m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw)
            if m:
                url = m.group(1)
                if url.startswith("http"):
                    return url
                if url.startswith("//"):
                    return "https:" + url
    return ""


# 品牌 → 域名映射，用于通过 Google favicon 服务获取 logo
BRAND_DOMAINS = {
    # OEM
    "lenovo": "lenovo.com", "联想": "lenovo.com",
    "dell": "dell.com", "戴尔": "dell.com",
    "hp ": "hp.com", "hewlett packard": "hp.com", "惠普": "hp.com",
    "asus": "asus.com", "华硕": "asus.com",
    "acer": "acer.com", "宏碁": "acer.com",
    "msi": "msi.com", "微星": "msi.com",
    "razer": "razer.com",
    "samsung": "samsung.com", "三星": "samsung.com",
    "apple": "apple.com", "苹果": "apple.com",
    "framework": "frame.work",
    "lg ": "lg.com", "lg gram": "lg.com",
    # 芯片
    "intel": "intel.com", "英特尔": "intel.com",
    "amd": "amd.com", "超威": "amd.com",
    "nvidia": "nvidia.com", "英伟达": "nvidia.com",
    "qualcomm": "qualcomm.com", "高通": "qualcomm.com",
    "snapdragon": "qualcomm.com",
    "mediatek": "mediatek.com", "联发科": "mediatek.com",
    # 存储
    "micron": "micron.com", "美光": "micron.com",
    "samsung": "samsung.com",
    "sk hynix": "skhynix.com", "海力士": "skhynix.com",
    "crucial": "crucial.com",
    "kingston": "kingston.com", "金士顿": "kingston.com",
    "western digital": "wd.com", "wd ": "wd.com", "西数": "wd.com",
    "seagate": "seagate.com", "希捷": "seagate.com",
    "kioxia": "kioxia.com", "铠侠": "kioxia.com",
    # ODM
    "quanta": "quanta.com", "广达": "quanta.com",
    "compal": "compal.com", "仁宝": "compal.com",
    "wistron": "wistron.com", "纬创": "wistron.com",
    "pegatron": "pegatron.com", "和硕": "pegatron.com",
    "inventec": "inventec.com", "英业达": "inventec.com",
    "huaqin": "huaqin.com", "华勤": "huaqin.com",
    "luxshare": "luxshare.com.cn", "立讯": "luxshare.com.cn",
    # OS / 平台
    "microsoft": "microsoft.com", "微软": "microsoft.com",
    "windows": "microsoft.com",
    "google": "google.com", "谷歌": "google.com",
    # 其他
    "asrock": "asrock.com",
    "gigabyte": "gigabyte.com", "技嘉": "gigabyte.com",
    "corsair": "corsair.com", "海盗船": "corsair.com",
    "logitech": "logitech.com", "罗技": "logitech.com",
    "sony": "sony.com", "索尼": "sony.com",
    "huawei": "huawei.com", "华为": "huawei.com",
    "xiaomi": "mi.com", "小米": "mi.com",
    "tcl": "tcl.com",
    "honor": "honor.com", "荣耀": "honor.com",
}

# 缓存已生成的 logo URL
_brand_cache = {}


def detect_brand(title: str, summary: str = "") -> str:
    """检测新闻中涉及的品牌，返回品牌名（用于显示），无匹配返回空字符串"""
    cache_key = title[:80] + summary[:80]
    if cache_key in _brand_cache:
        return _brand_cache[cache_key]

    text = (title + " " + summary).lower()
    for brand, domain in BRAND_DOMAINS.items():
        if brand in text:
            _brand_cache[cache_key] = brand.strip()
            return brand.strip()
    _brand_cache[cache_key] = ""
    return ""


def brand_logo_url(brand: str) -> str:
    """获取品牌 logo 的主 URL（favicon.im，国内可访问）"""
    if not brand:
        return ""
    domain = BRAND_DOMAINS.get(brand, brand)
    return f"https://favicon.im/{domain}?larger=true"


def brand_logo_fallback(brand: str) -> str:
    """获取备用 logo URL（国内 CDN）"""
    if not brand:
        return ""
    domain = BRAND_DOMAINS.get(brand, brand)
    return f"https://api.iowen.cn/favicon/{domain}.png"


def fetch_stock_price() -> dict:
    """
    获取联想集团（00992.HK）股价，失败返回空 dict。
    使用 Yahoo Finance chart API（无需 key）。
    """
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/0992.HK"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code != 200:
            return {}
        data = resp.json()
        meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
        if not meta:
            return {}
        price = meta.get("regularMarketPrice")
        prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
        currency = meta.get("currency", "HKD")
        if price is None:
            return {}
        change = price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0
        ts = meta.get("regularMarketTime")
        from datetime import datetime as dt, timezone as tz, timedelta as td
        market_time = ""
        if ts:
            market_time = dt.fromtimestamp(ts, tz(td(hours=8))).strftime("%m-%d %H:%M")
        return {
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "currency": currency,
            "symbol": "00992.HK",
            "name": "联想集团",
            "time": market_time,
            "up": change >= 0,
        }
    except Exception as e:
        print(f"[WARN] 股价获取失败: {e}")
        return {}


def fetch_entries(max_items: int = 55):
    entries = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; PC-HOT-Bot/1.4)"}

    for source_name, url in RSS_SOURCES:
        try:
            print(f"抓取 {source_name} ...")
            resp = requests.get(url, headers=headers, timeout=18)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            count = 0
            for entry in feed.entries[:28]:
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
                image = extract_image(entry)
                brand = detect_brand(title, summary)
                entries.append({
                    "title": title,
                    "summary": clean_text(summary),
                    "link": link,
                    "source": source_name,
                    "dt": dt or datetime.now(timezone.utc),
                    "category": cat,
                    "cost_flag": cost_flag,
                    "reason": "",
                    "image": image,
                    "brand": brand,
                })
                count += 1
            print(f"  → {count} 条")
        except Exception as e:
            print(f"  失败: {e}")

    # 去重 + 成本优先排序
    seen = set()
    unique = []
    def _laptop_boost(e):
        t = (e["title"] + " " + e.get("summary", "")).lower()
        strong = ["laptop", "notebook", "ai pc", "thinkpad", "笔记本", "legion", "xps", "zenbook"]
        return 0 if any(s in t for s in strong) else 1
    for e in sorted(entries, key=lambda x: (_laptop_boost(x), not x["cost_flag"], -x["dt"].timestamp())):
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

def load_history(max_items=500):
    """读取 data/news_history.jsonl，返回列表（最多 max_items 条，按时间倒序）"""
    history_path = Path("data/news_history.jsonl")
    if not history_path.exists():
        return []
    items = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            items.append(json.loads(line))
        except Exception:
            continue
    items.sort(
        key=lambda x: x.get("published_at", x.get("first_collected_at", "")),
        reverse=True,
    )
    return items[:max_items]


def render_html(entries, history=None):
    now = datetime.now(timezone(timedelta(hours=8)))
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
    history_json = json.dumps(history or [], ensure_ascii=False)
    brand_domains_json = json.dumps(BRAND_DOMAINS, ensure_ascii=False)

    # 数据来源列表
    source_list_html = " · ".join(
        f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(name)}</a>'
        for name, url in RSS_SOURCES
    )

    # 品牌热度统计（右栏）
    brand_counts = {}
    for e in entries:
        b = e.get("brand")
        if b:
            brand_counts[b] = brand_counts.get(b, 0) + 1
    top_brands = sorted(brand_counts.items(), key=lambda x: -x[1])[:8]
    max_brand_count = top_brands[0][1] if top_brands else 1
    brand_rank_html = ""
    for i, (brand, count) in enumerate(top_brands):
        rank_class = "brand-rank-top" if i < 3 else ""
        bar_width = int(count / max_brand_count * 100)
        brand_domain = BRAND_DOMAINS.get(brand, brand)
        initial = brand[0].upper()
        brand_rank_html += f"""
          <div class="brand-rank-item">
            <span class="brand-rank-num {rank_class}">{i+1}</span>
            <div class="brand-rank-avatar">
              <img src="{html.escape(brand_logo_url(brand))}" data-domain="{html.escape(brand_domain)}" data-try="0" alt="{html.escape(brand)}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
              <span class="brand-rank-initial" style="display:none">{initial}</span>
            </div>
            <div class="brand-rank-info">
              <div class="brand-rank-name">{html.escape(brand)}</div>
              <div class="brand-rank-bar"><div class="brand-rank-bar-fill" style="width:{bar_width}%"></div></div>
            </div>
            <span class="brand-rank-count">{count}</span>
          </div>"""
    if not top_brands:
        brand_rank_html = '<p class="sidebar-empty">暂无品牌数据</p>'

    # 分类占比统计（右栏）
    cat_counts = {}
    for e in entries:
        c = e["category"]
        cat_counts[c] = cat_counts.get(c, 0) + 1
    total_entries = len(entries)
    cat_stat_html = ""
    CATEGORY_ORDER = ["AI与芯片", "OEM品牌", "ODM代工", "成本价格", "市场出货", "产品发布", "综合"]
    cat_colors = {
        "AI与芯片": "#8b5cf6", "OEM品牌": "#3b82f6", "ODM代工": "#06b6d4",
        "成本价格": "#f59e0b", "市场出货": "#10b981", "产品发布": "#ec4899", "综合": "#64748b"
    }
    for cat in CATEGORY_ORDER:
        if cat not in cat_counts: continue
        count = cat_counts[cat]
        pct = round(count / total_entries * 100, 1) if total_entries else 0
        color = cat_colors.get(cat, "#64748b")
        cat_stat_html += f"""
          <div class="cat-stat-item" data-cat-key="{html.escape(cat)}">
            <div class="cat-stat-label">
              <span class="cat-stat-dot" style="background:{color}"></span>
              <span>{html.escape(cat)}</span>
              <span class="cat-stat-num">{count}</span>
            </div>
            <div class="cat-stat-bar"><div class="cat-stat-bar-fill" style="width:{pct}%;background:{color}"></div></div>
          </div>"""

    # 分类标签（左栏用，带计数）
    cat_tags = ""
    for cat in CATEGORIES:
        if cat not in cat_counts: continue
        count = cat_counts[cat]
        cat_tags += f'<button class="tag-btn" data-filter="{html.escape(cat)}">{html.escape(cat)} ({count})</button>'

    # 股价卡片（右栏）
    stock = fetch_stock_price()
    if stock:
        up_class = "stock-up" if stock["up"] else "stock-down"
        arrow = "↑" if stock["up"] else "↓"
        sign = "+" if stock["up"] else ""
        stock_html = f"""
        <div class="sidebar-section stock-card">
          <div class="stock-header">
            <div class="stock-title">
              <span class="stock-name">{html.escape(stock['name'])}</span>
              <span class="stock-symbol">{stock['symbol']}</span>
            </div>
            <span class="stock-currency">{stock['currency']}</span>
          </div>
          <div class="stock-price-row">
            <span class="stock-price">{stock['price']}</span>
            <span class="stock-change {up_class}">{arrow} {sign}{stock['change']} ({sign}{stock['change_pct']}%)</span>
          </div>
          <div class="stock-time">{stock['time']}</div>
        </div>"""
    else:
        stock_html = ""

    # 热榜：成本相关优先展示
    cost_entries = [e for e in entries if e["cost_flag"]]
    other_entries = [e for e in entries if not e["cost_flag"]]
    hot_candidates = (cost_entries + other_entries)[:10]

    hot_html = ""
    for i, e in enumerate(hot_candidates[:8]):
        rank_class = "top3" if i < 3 else ""
        cost_mark = " · 成本" if e["cost_flag"] else ""
        t_zh = html.escape(e.get("title_zh") or e["title"])
        t_en = html.escape(e.get("title_en") or e["title"])
        brand = e.get("brand") or ""
        brand_domain = BRAND_DOMAINS.get(brand, brand) if brand else ""
        if brand:
            # 品牌头像：有 logo 用 logo，没有就用首字母
            initial = brand[0].upper() if brand else ""
            brand_html = f"""
          <div class="hot-brand-avatar" title="{html.escape(brand)}">
            <img class="hot-brand-logo" src="{html.escape(brand_logo_url(brand))}" data-domain="{html.escape(brand_domain)}" data-try="0" alt="{html.escape(brand)}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
            <span class="hot-brand-initial" style="display:none">{initial}</span>
          </div>"""
        else:
            brand_html = '<div class="hot-brand-avatar hot-brand-default"><span>•</span></div>'
        feed_id = "feed-" + hashlib.md5(e["link"].encode()).hexdigest()[:12]
        hot_html += f"""
      <div class="hot-item" data-feed-id="{feed_id}" onclick="scrollToFeed('{feed_id}')">
        <div class="hot-rank {rank_class}">{i+1}</div>
        {brand_html}
        <div class="hot-content">
          <div class="hot-title">
            <a href="{html.escape(e['link'])}" target="_blank" rel="noopener" class="hot-link" onclick="event.stopPropagation()">
              <span class="lang-zh">{t_zh}</span>
              <span class="lang-en" style="display:none">{t_en}</span>
            </a>
          </div>
        </div>
        <div class="hot-heat">
          <span class="lang-zh">{heat_score(i, e['cost_flag'])} 热度{cost_mark}</span>
          <span class="lang-en" style="display:none">{heat_score(i, e['cost_flag'])} heat{" · Cost" if e["cost_flag"] else ""}</span>
        </div>
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
            day_title_zh = f"今天 {now.strftime('%m月%d日')} {weekday}"
            day_title_en = f"Today {now.strftime('%Y-%m-%d')}"
        elif label == "昨天":
            day_title_zh = f"昨天 {(now - timedelta(days=1)).strftime('%m月%d日')}"
            day_title_en = f"Yesterday {(now - timedelta(days=1)).strftime('%Y-%m-%d')}"
        else:
            day_title_zh = "更早内容"
            day_title_en = "Earlier"

        feed_sections += f'<div class="day-block">\n<div class="day-title"><span class="lang-zh">{day_title_zh}</span><span class="lang-en" style="display:none">{day_title_en}</span></div>\n'
        for e in items:
            time_str = e["dt"].astimezone(timezone(timedelta(hours=8))).strftime("%H:%M")
            heat = heat_score(global_rank, e["cost_flag"])
            global_rank += 1
            reason = e.get("reason") or default_reason(e["category"], e["cost_flag"])
            cost_badge = '<span class="cost-badge">成本相关</span>' if e["cost_flag"] else ""

            title_zh = e.get("title_zh") or e["title"]
            title_en = e.get("title_en") or e["title"]
            summary_zh = e.get("summary_zh") or e.get("summary") or ""
            summary_en = e.get("summary_en") or e.get("summary") or ""
            reason_zh = e.get("reason_zh") or reason
            reason_en = e.get("reason_en") or reason

            brand = e.get("brand") or ""
            brand_domain = BRAND_DOMAINS.get(brand, brand) if brand else ""
            brand_html = f'<img class="brand-logo feed-brand" src="{html.escape(brand_logo_url(brand))}" data-domain="{html.escape(brand_domain)}" data-try="0" alt="{html.escape(brand)}" title="{html.escape(brand)}" loading="lazy" onerror="fixFavicon(this)">' if brand else ""

            feed_item_id = "feed-" + hashlib.md5(e["link"].encode()).hexdigest()[:12]
            feed_sections += f"""
      <article class="feed-item" id="{feed_item_id}" data-cat="{html.escape(e['category'])}" data-title="{html.escape((title_zh + ' ' + title_en).lower())}" data-cost="{'1' if e['cost_flag'] else '0'}">
        {brand_html}
        <div class="feed-main">
        <div class="feed-meta">
          <span class="feed-time">{time_str}</span>
          <span class="feed-source">{html.escape(e['source'])}</span>
          <span class="cat-tag" data-cat-key="{html.escape(e['category'])}">{html.escape(e['category'])}</span>
          {cost_badge}
          <span class="feed-heat">{heat} 热度</span>
          <button class="copy-btn" onclick="copyLink(event, this)" data-link="{html.escape(e['link'])}" title="复制链接">🔗</button>
        </div>
        <div class="feed-title">
          <a href="{html.escape(e['link'])}" target="_blank" rel="noopener">
            <span class="lang-zh">{html.escape(title_zh)}</span>
            <span class="lang-en" style="display:none">{html.escape(title_en)}</span>
          </a>
        </div>
        <div class="feed-summary">
          <span class="lang-zh">{html.escape(summary_zh) or '（暂无摘要）'}</span>
          <span class="lang-en" style="display:none">{html.escape(summary_en) or '(No summary)'}</span>
        </div>
        <div class="feed-reason">
          <strong class="lang-zh">推荐理由：</strong><strong class="lang-en" style="display:none">Why it matters: </strong>
          <span class="lang-zh">{html.escape(reason_zh)}</span>
          <span class="lang-en" style="display:none">{html.escape(reason_en)}</span>
        </div>
        {f'<div class="feed-image-wrap"><img class="feed-image" src="{html.escape(e.get("image") or "")}" alt="" loading="lazy" onerror="this.parentElement.remove()"></div>' if e.get("image") else ""}
        </div><!-- /feed-main -->
      </article>"""
        feed_sections += "\n</div>\n"

    cost_count = sum(1 for e in entries if e["cost_flag"])

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PC HOT — 笔记本电脑行业动态（OEM / ODM / AI PC）</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <style>
    :root {{
      --bg: #f0f2f5;
      --card: #ffffff;
      --text: #111827;
      --text2: #4b5563;
      --muted: #9ca3af;
      --border: #e5e7eb;
      --accent: #3b82f6;
      --accent-soft: #eff6ff;
      --hot: #ef4444;
      --cost: #d97706;
      --cost-bg: #fffbeb;
      --shadow: 0 1px 3px rgba(0,0,0,.06), 0 1px 2px rgba(0,0,0,.04);
      --shadow-hover: 0 10px 25px -5px rgba(0,0,0,.08), 0 4px 6px -2px rgba(0,0,0,.03);
      --radius: 14px;
    }}
    [data-theme="dark"] {{
      --bg: #0f172a;
      --card: #1e293b;
      --text: #f1f5f9;
      --text2: #cbd5e1;
      --muted: #64748b;
      --border: #334155;
      --accent: #60a5fa;
      --accent-soft: #1e3a5f;
      --hot: #f87171;
      --cost: #fbbf24;
      --cost-bg: #422006;
      --shadow: 0 1px 3px rgba(0,0,0,.3), 0 1px 2px rgba(0,0,0,.2);
      --shadow-hover: 0 10px 25px -5px rgba(0,0,0,.4), 0 4px 6px -2px rgba(0,0,0,.2);
    }}
    [data-theme="dark"] header {{ background: #0b1120; }}
    [data-theme="dark"] .feed-reason {{
      background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    }}
    [data-theme="dark"] .stats {{ background: var(--accent-soft); color: #93c5fd; }}
    [data-theme="dark"] .hot-item:hover {{ background: #334155; }}
    [data-theme="dark"] .tag-btn:hover {{ border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }}
    [data-theme="dark"] .hot-brand-default {{ background: #334155; color: #64748b; }}
    [data-theme="dark"] .brand-logo {{ background: #334155; }}
    [data-theme="dark"] .feed-image {{ border-color: #334155; }}
    [data-theme="dark"] .back-today-btn:hover {{ background: var(--accent-soft); }}
    [data-theme="dark"] .no-data {{ color: #64748b; }}
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.65;
      min-height: 100vh;
    }}
    a {{ color: inherit; text-decoration: none; transition: color .15s; }}
    a:hover {{ color: var(--accent); }}

    /* Header */
    header {{
      background: #111827;
      border-bottom: none;
      position: sticky; top: 0; z-index: 50;
    }}
    .header-inner {{
      max-width: 920px; margin: 0 auto; padding: 14px 20px;
      display: flex; align-items: center; justify-content: space-between; gap: 16px;
    }}
    .brand {{
      display: flex; align-items: center; gap: 12px;
    }}
    .logo-badge {{
      background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
      color: #fff; font-size: .68rem; font-weight: 700;
      padding: 4px 9px; border-radius: 8px; letter-spacing: .04em;
      box-shadow: 0 2px 8px rgba(59,130,246,.35);
    }}
    .pc-name {{
      font-weight: 700; font-size: 1.2rem; letter-spacing: -0.03em; color: #fff;
    }}
    .brand-divider {{
      width: 1px; height: 22px; background: #4b5563;
    }}
    .lenovo-logo {{
      font-weight: 700; font-size: 1.1rem; letter-spacing: -0.02em;
      color: #e2231a; font-family: Arial, "Helvetica Neue", sans-serif;
    }}
    .tec-badge {{
      font-weight: 700; font-size: 0.95rem; letter-spacing: 0.08em;
      color: #fff; padding: 2px 8px; border: 1.5px solid #fff;
      border-radius: 4px; font-family: Arial, sans-serif;
    }}
    .search-box {{ flex: 1; max-width: 280px; }}
    .search-box input {{
      width: 100%; padding: 9px 14px 9px 36px;
      border: 1px solid #374151; border-radius: 10px;
      font-size: .9rem; outline: none; background: #1f2937; color: #e5e7eb;
      transition: border-color .15s, box-shadow .15s;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='%239ca3af' viewBox='0 0 16 16'%3E%3Cpath d='M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85zm-5.242.656a5 5 0 1 1 0-10 5 5 0 0 1 0 10z'/%3E%3C/svg%3E");
      background-repeat: no-repeat; background-position: 12px center;
    }}
    .search-box input::placeholder {{ color: #6b7280; }}
    .search-box input:focus {{
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(59,130,246,.25);
      background-color: #111827;
    }}

    main {{ max-width: 1400px; margin: 0 auto; padding: 24px 20px 60px; }}
    .layout {{ display: flex; gap: 24px; align-items: flex-start; }}
    .sidebar {{ width: 200px; flex-shrink: 0; position: sticky; top: 80px; }}
    .sidebar-right {{ width: 260px; }}
    .sidebar-section {{ background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; box-shadow: var(--shadow); margin-bottom: 16px; }}
    .sidebar-title {{ font-size: .78rem; font-weight: 700; color: var(--text2); margin-bottom: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    .sidebar-empty {{ font-size: .8rem; color: var(--muted); text-align: center; padding: 16px 0; }}
    .time-filters {{ display: flex; flex-direction: column; gap: 6px; }}
    .time-btn {{ background: transparent; border: 1px solid var(--border); padding: 9px 14px; border-radius: 8px; font-size: .85rem; cursor: pointer; color: var(--text2); text-align: left; transition: all .15s; font-weight: 500; }}
    .time-btn:hover {{ border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }}
    .time-btn.active {{ background: var(--accent); color: #fff; border-color: var(--accent); box-shadow: 0 2px 8px rgba(59,130,246,.3); }}
    .cat-filters {{ display: flex; flex-direction: column; gap: 4px; }}
    .cat-filters .tag-btn {{
      width: 100%; justify-content: space-between; display: flex;
      padding: 7px 12px; font-size: .82rem;
    }}
    .content {{ flex: 1; min-width: 0; }}
    .no-data {{ text-align: center; padding: 48px 20px; color: var(--muted); font-size: .9rem; }}

    /* ===== 品牌热度榜 ===== */
    .brand-rank-list {{ display: flex; flex-direction: column; gap: 10px; }}
    .brand-rank-item {{
      display: flex; align-items: center; gap: 10px;
    }}
    .brand-rank-num {{
      width: 18px; text-align: center; font-size: .75rem;
      font-weight: 700; color: var(--muted); flex-shrink: 0;
    }}
    .brand-rank-num.brand-rank-top {{ color: var(--hot); font-size: .85rem; }}
    .brand-rank-avatar {{
      width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      display: flex; align-items: center; justify-content: center;
      overflow: hidden; border: 1.5px solid #fff;
      box-shadow: 0 1px 4px rgba(0,0,0,.1);
    }}
    .brand-rank-avatar img {{
      width: 20px; height: 20px; object-fit: contain;
      background: #fff; padding: 2px; border-radius: 50%;
    }}
    .brand-rank-initial {{
      color: #fff; font-weight: 700; font-size: .75rem;
      display: none; align-items: center; justify-content: center;
      width: 100%; height: 100%;
    }}
    .brand-rank-info {{ flex: 1; min-width: 0; }}
    .brand-rank-name {{
      font-size: .8rem; font-weight: 600; color: var(--text);
      margin-bottom: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }}
    .brand-rank-bar {{
      height: 4px; border-radius: 2px; background: #e2e8f0;
      overflow: hidden;
    }}
    .brand-rank-bar-fill {{
      height: 100%; border-radius: 2px;
      background: linear-gradient(90deg, #667eea, #764ba2);
    }}
    .brand-rank-count {{
      font-size: .75rem; font-weight: 600; color: var(--muted);
      flex-shrink: 0; min-width: 18px; text-align: right;
    }}

    /* ===== 分类占比统计 ===== */
    .cat-stat-list {{ display: flex; flex-direction: column; gap: 10px; }}
    .cat-stat-item {{ cursor: pointer; }}
    .cat-stat-label {{
      display: flex; align-items: center; gap: 6px;
      font-size: .8rem; margin-bottom: 4px;
    }}
    .cat-stat-dot {{
      width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
    }}
    .cat-stat-label span:nth-child(2) {{ flex: 1; color: var(--text2); }}
    .cat-stat-num {{ color: var(--muted); font-weight: 600; font-size: .75rem; }}
    .cat-stat-bar {{
      height: 6px; border-radius: 3px; background: #e2e8f0; overflow: hidden;
    }}
    .cat-stat-bar-fill {{ height: 100%; border-radius: 3px; transition: width .3s; }}
    .cat-stat-item:hover .cat-stat-bar-fill {{ opacity: .8; }}

    /* ===== 股价卡片 ===== */
    .stock-card {{
      background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
      border: 1px solid #bae6fd;
    }}
    [data-theme="dark"] .stock-card {{
      background: linear-gradient(135deg, #0c4a6e 0%, #075985 100%);
      border-color: #0369a1;
    }}
    .stock-header {{
      display: flex; justify-content: space-between; align-items: flex-start;
      margin-bottom: 8px;
    }}
    .stock-title {{ display: flex; flex-direction: column; }}
    .stock-name {{ font-weight: 700; font-size: .95rem; color: var(--text); }}
    .stock-symbol {{ font-size: .7rem; color: var(--muted); }}
    .stock-currency {{ font-size: .7rem; color: var(--muted); }}
    .stock-price-row {{
      display: flex; align-items: baseline; gap: 10px; margin-bottom: 4px;
    }}
    .stock-price {{ font-size: 1.5rem; font-weight: 800; color: var(--text); line-height: 1; }}
    .stock-change {{ font-size: .78rem; font-weight: 600; padding: 2px 6px; border-radius: 4px; }}
    .stock-up {{ color: #dc2626; background: #fee2e2; }}
    .stock-down {{ color: #16a34a; background: #dcfce7; }}
    [data-theme="dark"] .stock-up {{ color: #fca5a5; background: rgba(220,38,38,.2); }}
    [data-theme="dark"] .stock-down {{ color: #86efac; background: rgba(22,163,74,.2); }}
    .stock-time {{ font-size: .7rem; color: var(--muted); }}

    .section-header {{
      display: flex; align-items: baseline; justify-content: space-between;
      margin-bottom: 14px;
    }}
    .section-header h2 {{
      font-size: 1.15rem; font-weight: 700; letter-spacing: -0.02em;
    }}
    .section-header .date {{ font-size: .85rem; color: var(--muted); }}
    .back-today-btn {{
      background: transparent; border: 1px solid var(--border);
      padding: 6px 14px; border-radius: 8px;
      font-size: .82rem; cursor: pointer; color: var(--text2);
      transition: all .15s; font-weight: 500;
    }}
    .back-today-btn:hover {{
      border-color: var(--accent); color: var(--accent);
      background: var(--accent-soft);
    }}

    /* Tags */
    .tags {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px; }}
    .tag-btn {{
      background: var(--card); border: 1px solid var(--border);
      padding: 6px 14px; border-radius: 999px; font-size: .8rem;
      cursor: pointer; color: var(--text2); transition: all .15s;
      font-weight: 500;
    }}
    .tag-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
    .tag-btn.active {{
      background: var(--accent); color: #fff; border-color: var(--accent);
      box-shadow: 0 2px 8px rgba(59,130,246,.3);
    }}
    .tag-btn.cost-filter {{ border-color: #fcd34d; color: var(--cost); }}
    .tag-btn.cost-filter.active {{
      background: var(--cost); color: #fff; border-color: var(--cost);
      box-shadow: 0 2px 8px rgba(217,119,6,.3);
    }}

    /* Hot list */
    .hot-list {{
      background: var(--card); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 8px 0; margin-bottom: 28px;
      box-shadow: var(--shadow);
    }}
    .hot-item {{
      display: flex; align-items: flex-start; gap: 14px;
      padding: 12px 18px; transition: background .15s;
      cursor: pointer;
    }}
    .hot-item:hover {{ background: #f1f5f9; }}
    .hot-rank {{
      font-weight: 800; font-size: 1.05rem; color: var(--muted);
      min-width: 24px; text-align: center; font-variant-numeric: tabular-nums;
    }}
    .hot-rank.top3 {{
      background: linear-gradient(135deg, #ef4444, #f97316);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
      background-clip: text;
    }}
    .hot-content {{ flex: 1; min-width: 0; }}
    .hot-title {{ font-size: .95rem; font-weight: 550; line-height: 1.4; }}
    .hot-link {{ color: inherit; text-decoration: none; display: block; }}
    .hot-link:hover {{ color: var(--accent); }}
    .hot-brand-avatar {{
      width: 40px; height: 40px; border-radius: 50%; flex-shrink: 0;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      display: flex; align-items: center; justify-content: center;
      overflow: hidden; border: 2px solid #fff;
      box-shadow: 0 2px 8px rgba(0,0,0,.1);
    }}
    .hot-brand-logo {{
      width: 28px; height: 28px; object-fit: contain;
      background: #fff; padding: 2px; border-radius: 50%;
    }}
    .hot-brand-initial {{
      color: #fff; font-weight: 700; font-size: 1rem;
      display: none; align-items: center; justify-content: center;
      width: 100%; height: 100%;
    }}
    .hot-brand-default {{
      background: #e2e8f0; color: #94a3b8;
    }}
    .hot-brand-default span {{
      font-size: 1.2rem; line-height: 1;
    }}
    .brand-logo {{
      width: 28px; height: 28px; border-radius: 6px; flex-shrink: 0;
      object-fit: contain; background: #f8fafc; padding: 3px;
      border: 1px solid var(--border);
    }}
    .hot-heat {{
      font-size: .78rem; color: var(--hot); font-weight: 600;
      white-space: nowrap; padding-top: 2px;
    }}

    .stats {{
      font-size: .82rem; color: var(--muted); margin-bottom: 18px;
      padding: 10px 14px; background: var(--accent-soft);
      border-radius: 10px; color: #1e40af;
    }}
    .stats strong {{ color: var(--accent); }}

    /* Day blocks */
    .day-block {{ margin-bottom: 32px; }}
    .day-title {{
      font-size: 1.05rem; font-weight: 700; margin-bottom: 14px;
      padding-bottom: 8px; border-bottom: 2px solid var(--border);
      letter-spacing: -0.01em;
    }}

    /* Feed cards */
    .feed-item {{
      background: var(--card); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 16px 18px; margin-bottom: 12px;
      box-shadow: var(--shadow); transition: all .2s;
      display: flex; gap: 12px; align-items: flex-start;
    }}
    .feed-item:hover {{
      border-color: #c7d2fe;
      box-shadow: var(--shadow-hover);
      transform: translateY(-1px);
    }}
    .feed-item.hidden {{ display: none; }}
    .feed-item.highlight-flash {{
      animation: highlightFlash 1.5s ease-out;
    }}
    @keyframes highlightFlash {{
      0%   {{ box-shadow: 0 0 0 0 rgba(59,130,246,.5); border-color: #3b82f6; }}
      50%  {{ box-shadow: 0 0 0 8px rgba(59,130,246,0); border-color: #3b82f6; }}
      100% {{ box-shadow: 0 0 0 0 rgba(59,130,246,0); }}
    }}
    .feed-main {{ flex: 1; min-width: 0; }}
    .feed-brand {{ margin-top: 2px; }}
    .feed-meta {{
      display: flex; align-items: center; gap: 8px;
      font-size: .78rem; color: var(--muted); margin-bottom: 8px; flex-wrap: wrap;
    }}
    .feed-time {{ font-variant-numeric: tabular-nums; font-weight: 500; }}
    .feed-source {{ color: var(--accent); font-weight: 600; }}
    .cat-tag {{
      background: var(--accent-soft); color: var(--accent);
      padding: 2px 9px; border-radius: 6px; font-size: .74rem; font-weight: 500;
    }}
    .cost-badge {{
      background: var(--cost-bg); color: var(--cost);
      padding: 2px 9px; border-radius: 6px; font-size: .74rem; font-weight: 600;
    }}
    .feed-heat {{ margin-left: auto; color: var(--hot); font-weight: 600; }}
    .copy-btn {{
      background: transparent; border: none; cursor: pointer;
      font-size: .85rem; padding: 2px 6px; border-radius: 4px;
      opacity: .5; transition: all .15s; margin-left: 4px;
    }}
    .copy-btn:hover {{ opacity: 1; background: var(--accent-soft); }}
    .copy-btn.copied {{ opacity: 1; color: #10b981; }}
    .feed-title {{
      font-size: 1.02rem; font-weight: 650; margin-bottom: 8px;
      line-height: 1.45; letter-spacing: -0.01em;
    }}
    .feed-summary {{
      font-size: .9rem; color: var(--text2); margin-bottom: 10px; line-height: 1.55;
    }}
    .feed-image-wrap {{ margin-top: 10px; }}
    .feed-image {{
      width: 100%; max-height: 280px; border-radius: 8px; object-fit: cover;
      border: 1px solid var(--border);
    }}
    .feed-reason {{
      font-size: .84rem; color: var(--text2);
      background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
      border-radius: 10px; padding: 10px 12px;
      border-left: 3px solid var(--accent);
    }}
    .feed-reason strong {{ color: var(--text); font-weight: 600; }}


    .lang-toggle {{
      display: flex; align-items: center; gap: 0;
      background: #1f2937; border: 1px solid #374151;
      border-radius: 8px; overflow: hidden; flex-shrink: 0;
    }}
    .lang-toggle button {{
      background: transparent; border: none; color: #9ca3af;
      padding: 6px 12px; font-size: 0.8rem; font-weight: 600;
      cursor: pointer; transition: all .15s;
    }}
    .lang-toggle button.active {{
      background: #3b82f6; color: #fff;
    }}
    .lang-toggle button:hover:not(.active) {{ color: #e5e7eb; }}
    .theme-toggle {{
      width: 36px; height: 36px; border-radius: 50%;
      background: #374151; border: 1px solid #4b5563;
      color: #fff; cursor: pointer; font-size: 1rem;
      display: flex; align-items: center; justify-content: center;
      transition: all .15s;
    }}
    .theme-toggle:hover {{ background: #4b5563; transform: scale(1.08); }}

    footer {{
      max-width: 920px; margin: 0 auto; padding: 28px 20px;
      border-top: 1px solid var(--border); text-align: center;
      font-size: .8rem; color: var(--muted);
    }}
    footer p {{ margin-bottom: 4px; }}
    footer strong {{ color: var(--text2); }}
    footer a {{ color: var(--muted); text-decoration: underline; text-underline-offset: 2px; }}
    footer a:hover {{ color: var(--accent); }}
    .footer-sources {{ font-size: .75rem; line-height: 1.8; }}
    .footer-sources a {{ margin: 0 2px; }}
    .footer-links {{ margin-top: 8px; font-size: .78rem; }}

    .back-to-top {{
      position: fixed; right: 24px; bottom: 24px;
      width: 44px; height: 44px; border-radius: 50%;
      background: var(--accent); color: #fff;
      border: none; cursor: pointer; font-size: 1.2rem;
      box-shadow: 0 4px 16px rgba(59,130,246,.35);
      opacity: 0; visibility: hidden;
      transition: all .2s; z-index: 100;
    }}
    .back-to-top:hover {{
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(59,130,246,.45);
    }}
    .back-to-top.show {{ opacity: 1; visibility: visible; }}

    @media (max-width: 1200px) {{
      .sidebar-right {{ display: none; }}
      main {{ max-width: 900px; }}
    }}
    @media (max-width: 600px) {{
      main {{ max-width: 100%; padding: 16px 12px 40px; }}
      .header-inner {{ flex-wrap: wrap; }}
      .search-box {{ max-width: 100%; order: 3; width: 100%; }}
      .hot-item {{ padding: 10px 14px; }}
      .feed-item {{ padding: 14px; }}
      .layout {{ flex-direction: column; gap: 16px; }}
      .sidebar {{ width: 100%; position: static; }}
      .sidebar-right {{ display: none; }}
      .time-filters {{ flex-direction: row; flex-wrap: wrap; }}
      .time-btn {{ flex: 1; min-width: 80px; text-align: center; }}
      .cat-filters {{ flex-direction: row; flex-wrap: wrap; gap: 6px; }}
      .cat-filters .tag-btn {{
        width: auto; padding: 5px 12px; font-size: .78rem;
        flex: 1; min-width: calc(33.33% - 4px);
      }}
      .feed-image {{ max-height: 200px; }}
      .hot-brand-avatar {{ width: 36px; height: 36px; }}
      .hot-brand-logo {{ width: 24px; height: 24px; }}
      .brand-logo {{ width: 24px; height: 24px; }}
      .back-to-top {{ right: 16px; bottom: 16px; width: 40px; height: 40px; }}
    }}
  </style>

</head>
<body>
  <header>
    <div class="header-inner">
      <div class="brand">
        <span class="logo-badge">PC</span>
        <span class="pc-name">PC HOT</span>
        <span class="brand-divider"></span>
        <span class="lenovo-logo">Lenovo</span>
        <span class="tec-badge">TEC</span>
      </div>
      <div style="display:flex;align-items:center;gap:12px;">
        <div class="search-box"><input type="text" id="searchInput" placeholder="搜索标题..." oninput="filterItems()" data-i18n-placeholder="search"></div>
        <button id="themeToggle" class="theme-toggle" onclick="toggleTheme()" title="切换主题">🌙</button>
        <div class="lang-toggle">
          <button type="button" id="btnZh" class="active" onclick="setLang('zh')">中文</button>
          <button type="button" id="btnEn" onclick="setLang('en')">EN</button>
        </div>
      </div>
    </div>
  </header>
  <main>
    <div class="layout">
    <!-- 左栏 -->
    <aside class="sidebar sidebar-left">
      <div class="sidebar-section">
        <h3 class="sidebar-title" data-i18n="timeRange">时间范围</h3>
        <div class="time-filters">
          <button class="time-btn active" data-range="today" data-i18n="today">今天</button>
          <button class="time-btn" data-range="7" data-i18n="lastWeek">近一周</button>
          <button class="time-btn" data-range="30" data-i18n="lastMonth">近一月</button>
          <button class="time-btn" data-range="0" data-i18n="allHistory">全部历史</button>
        </div>
      </div>
      <div class="sidebar-section">
        <h3 class="sidebar-title" data-i18n="categories">分类筛选</h3>
        <div class="cat-filters">
          <button class="tag-btn active" data-filter="all" data-i18n="all">全部</button>
          <button class="tag-btn cost-filter" data-filter="cost" data-i18n="costOnly">只看成本相关</button>
          {cat_tags}
        </div>
      </div>
    </aside>

    <!-- 中栏 -->
    <div class="content">
    <div id="todayView">
    <div class="section-header">
      <h2 data-i18n="hotTitle">精选热榜（笔记本 / AI PC）</h2>
      <span class="date">{now.strftime('%m月%d日')} · {weekday}</span>
    </div>
    <div class="hot-list">{hot_html}</div>
    <div class="stats">
      本次聚合 <strong>{len(entries)}</strong> 条 · 其中成本/价格相关 <strong>{cost_count}</strong> 条 · 来自 {len(set(e['source'] for e in entries))} 个来源
      {' · 已用本地 Qwen 增强' if USE_OLLAMA else ''}
    </div>
    <div class="section-header"><h2 data-i18n="latestTitle">最新精选</h2></div>
    {feed_sections}
    </div><!-- /todayView -->
    <div id="historyView" style="display:none">
      <div class="section-header">
        <h2 id="historyTitle" data-i18n="archiveTitle">历史归档</h2>
        <div style="display:flex;align-items:center;gap:12px;">
          <span class="date" id="historyCount"></span>
          <button class="back-today-btn" onclick="switchToToday()" data-i18n="backToday">← 返回今日</button>
        </div>
      </div>
      <div id="historyContainer"></div>
    </div>
    </div><!-- /content -->

    <!-- 右栏 -->
    <aside class="sidebar sidebar-right">
      {stock_html}
      <div class="sidebar-section">
        <h3 class="sidebar-title" data-i18n="brandRank">今日品牌热度</h3>
        <div class="brand-rank-list">
          {brand_rank_html}
        </div>
      </div>
      <div class="sidebar-section">
        <h3 class="sidebar-title" data-i18n="catStats">分类分布</h3>
        <div class="cat-stat-list">
          {cat_stat_html}
        </div>
      </div>
    </aside>

    </div><!-- /layout -->
  </main>
  <footer>
    <p data-i18n="footer1"><strong>PC HOT</strong> — 聚焦笔记本电脑 · OEM / ODM · AI PC</p>
    <p>更新于 {now.strftime('%Y-%m-%d %H:%M')} (北京时间)</p>
    <p class="footer-sources"><span data-i18n="footerSources">数据来源：</span>{source_list_html}</p>
    <p class="footer-links">
      <a href="https://github.com/xuzhenjiangwudi-create/PC-HOT" target="_blank" rel="noopener">GitHub</a>
      · <span data-i18n="footerPowered">由 RSS + Qwen 驱动</span>
    </p>
  </footer>
  <button id="backToTop" class="back-to-top" onclick="window.scrollTo({{top:0,behavior:'smooth'}})" title="回到顶部">↑</button>
  <script>
    const I18N = {{
      zh: {{
        search: "搜索标题...",
        hotTitle: "精选热榜（笔记本 / AI PC）",
        latestTitle: "最新精选",
        all: "全部",
        costOnly: "只看成本相关",
        reason: "推荐理由：",
        footer1: "PC HOT — 聚焦笔记本电脑 · OEM / ODM · AI PC",
        footerSources: "数据来源：",
        footerPowered: "由 RSS + Qwen 驱动",
        costBadge: "成本相关",
        heat: "热度",
        timeRange: "时间范围",
        categories: "分类筛选",
        brandRank: "今日品牌热度",
        catStats: "分类分布",
        today: "今天",
        lastWeek: "近一周",
        lastMonth: "近一月",
        allHistory: "全部历史",
        archiveTitle: "历史归档",
        noData: "暂无数据",
        items: "条",
        backToday: "← 返回今日",
        cats: {{
          "AI与芯片": "AI与芯片", "OEM品牌": "OEM品牌", "ODM代工": "ODM代工",
          "成本价格": "成本价格", "市场出货": "市场出货", "产品发布": "产品发布", "综合": "综合"
        }}
      }},
      en: {{
        search: "Search titles...",
        hotTitle: "Top Stories (Laptop / AI PC)",
        latestTitle: "Latest",
        all: "All",
        costOnly: "Cost only",
        reason: "Why it matters: ",
        footer1: "PC HOT — Laptop Industry · OEM / ODM · AI PC",
        footerSources: "Sources:",
        footerPowered: "Powered by RSS + Qwen",
        costBadge: "Cost",
        heat: "heat",
        timeRange: "Time Range",
        categories: "Categories",
        brandRank: "Brand Heat",
        catStats: "Category Distribution",
        today: "Today",
        lastWeek: "Last Week",
        lastMonth: "Last Month",
        allHistory: "All History",
        archiveTitle: "Archive",
        noData: "No data",
      items: "items",
      backToday: "← Back to Today",
      cats: {{
          "AI与芯片": "AI & Chips", "OEM品牌": "OEM Brands", "ODM代工": "ODM",
          "成本价格": "Cost & Price", "市场出货": "Shipments", "产品发布": "Launches", "综合": "General"
        }}
      }}
    }};

    let currentLang = localStorage.getItem("pc_hot_lang") || "zh";
    let currentTheme = localStorage.getItem("pc_hot_theme");
    if (!currentTheme) {{
      currentTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }}
    function applyTheme() {{
      document.documentElement.setAttribute("data-theme", currentTheme);
      const btn = document.getElementById("themeToggle");
      if (btn) btn.textContent = currentTheme === "dark" ? "☀️" : "🌙";
    }}
    function toggleTheme() {{
      currentTheme = currentTheme === "dark" ? "light" : "dark";
      localStorage.setItem("pc_hot_theme", currentTheme);
      applyTheme();
    }}
    applyTheme();

    function setLang(lang) {{
      currentLang = lang;
      localStorage.setItem("pc_hot_lang", lang);
      document.getElementById("btnZh").classList.toggle("active", lang === "zh");
      document.getElementById("btnEn").classList.toggle("active", lang === "en");
      applyI18n();
    }}

    function applyI18n() {{
      const t = I18N[currentLang];
      const search = document.getElementById("searchInput");
      if (search) search.placeholder = t.search;
      document.querySelectorAll("[data-i18n]").forEach(el => {{
        const key = el.getAttribute("data-i18n");
        if (t[key]) el.textContent = t[key];
      }});
      document.querySelectorAll(".tag-btn").forEach(btn => {{
        const f = btn.dataset.filter;
        if (f === "all") btn.textContent = t.all;
        else if (f === "cost") btn.textContent = t.costOnly;
        else if (t.cats && t.cats[f]) {{
          const n = (btn.textContent.match(/\((\d+)\)/) || [])[1];
          btn.textContent = n ? (t.cats[f] + " (" + n + ")") : t.cats[f];
        }}
      }});
      document.querySelectorAll(".cost-badge").forEach(el => {{ el.textContent = t.costBadge; }});
      document.querySelectorAll(".cat-tag").forEach(el => {{
        const raw = el.getAttribute("data-cat-key") || el.textContent.trim();
        el.setAttribute("data-cat-key", raw);
        if (t.cats && t.cats[raw]) el.textContent = t.cats[raw];
      }});
      // 分类分布卡片的分类名
      document.querySelectorAll(".cat-stat-item").forEach(el => {{
        const key = el.getAttribute("data-cat-key");
        const labelSpan = el.querySelector(".cat-stat-label span:nth-child(2)");
        if (key && labelSpan && t.cats && t.cats[key]) {{
          labelSpan.textContent = t.cats[key];
        }}
      }});
      document.documentElement.lang = currentLang === "zh" ? "zh-CN" : "en";
      const showZh = currentLang === "zh";
      document.querySelectorAll(".lang-zh").forEach(el => {{ el.style.display = showZh ? "" : "none"; }});
      document.querySelectorAll(".lang-en").forEach(el => {{ el.style.display = showZh ? "none" : ""; }});
    }}

    function fixFavicon(img) {{
      const domain = img.dataset.domain;
      if (!domain) {{ img.remove(); return; }}
      const tryNum = parseInt(img.dataset.try || '0');
      const sources = [
        'https://api.iowen.cn/favicon/' + domain + '.png',
        'https://icons.duckduckgo.com/ip3/' + domain + '.ico',
        'https://www.google.com/s2/favicons?domain=' + domain + '&sz=64'
      ];
      if (tryNum < sources.length) {{
        img.dataset.try = String(tryNum + 1);
        img.src = sources[tryNum];
      }} else {{
        img.remove();
      }}
    }}

    function scrollToFeed(id) {{
      const el = document.getElementById(id);
      if (!el) return;
      el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
      el.classList.add('highlight-flash');
      setTimeout(() => el.classList.remove('highlight-flash'), 1500);
    }}

    function switchToToday() {{
      document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
      document.querySelector('.time-btn[data-range="today"]').classList.add('active');
      document.getElementById('todayView').style.display = '';
      document.getElementById('historyView').style.display = 'none';
      // 恢复今日分类计数
      document.querySelectorAll('.tag-btn').forEach(btn => {{
        const f = btn.dataset.filter;
        if (f === 'all' || f === 'cost') return;
        const orig = btn.dataset.origText;
        if (orig) btn.textContent = orig;
      }});
      tagBtns.forEach(b => b.classList.remove('active'));
      document.querySelector('.tag-btn[data-filter="all"]').classList.add('active');
      currentFilter = 'all';
      filterItems();
      window.scrollTo({{ top: 0, behavior: 'smooth' }});
    }}

    function copyLink(e, btn) {{
      e.stopPropagation();
      const link = btn.dataset.link;
      if (!link) return;
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        navigator.clipboard.writeText(link).then(() => {{
          showCopySuccess(btn);
        }}).catch(() => fallbackCopy(link, btn));
      }} else {{
        fallbackCopy(link, btn);
      }}
    }}
    function fallbackCopy(text, btn) {{
      const ta = document.createElement('textarea');
      ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      try {{ document.execCommand('copy'); showCopySuccess(btn); }} catch(e) {{}}
      document.body.removeChild(ta);
    }}
    function showCopySuccess(btn) {{
      const orig = btn.textContent;
      btn.textContent = '✓';
      btn.classList.add('copied');
      setTimeout(() => {{
        btn.textContent = orig;
        btn.classList.remove('copied');
      }}, 1500);
    }}

    const searchInput = document.getElementById("searchInput");
    const tagBtns = document.querySelectorAll(".tag-btn");
    let currentFilter = "all";
    // 保存初始标签文本（今日计数）
    tagBtns.forEach(btn => {{
      if (btn.dataset.filter !== 'all' && btn.dataset.filter !== 'cost') {{
        btn.dataset.origText = btn.textContent;
      }}
    }});
    tagBtns.forEach(btn => {{
      btn.addEventListener("click", () => {{
        tagBtns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        currentFilter = btn.dataset.filter;
        filterItems();
      }});
    }});
    function filterItems() {{
      const q = (searchInput.value || "").trim().toLowerCase();
      document.querySelectorAll(".feed-item").forEach(item => {{
        const cat = item.dataset.cat || "";
        const title = item.dataset.title || "";
        const isCost = item.dataset.cost === "1";
        let match = true;
        if (currentFilter === "cost") match = isCost;
        else if (currentFilter !== "all") match = cat === currentFilter;
        if (q && !title.includes(q)) match = false;
        item.classList.toggle("hidden", !match);
      }});
    }}

    // ==================== 历史归档 ====================
    const HISTORY_DATA = {history_json};

    function escapeHtml(s) {{
      const d = document.createElement('div');
      d.textContent = s || '';
      return d.innerHTML;
    }}

    function renderHistoryView(days) {{
      const container = document.getElementById('historyContainer');
      const countEl = document.getElementById('historyCount');
      const now = new Date();
      let filtered = HISTORY_DATA;
      if (days > 0) {{
        const cutoff = new Date(now.getTime() - days * 86400000);
        filtered = HISTORY_DATA.filter(item => {{
          const d = new Date(item.published_at || item.first_collected_at);
          return d >= cutoff;
        }});
      }}
      filtered.sort((a, b) => new Date(b.published_at || b.first_collected_at) - new Date(a.published_at || a.first_collected_at));

      const groups = {{}};
      filtered.forEach(item => {{
        const d = new Date(item.published_at || item.first_collected_at);
        const key = d.toLocaleDateString('zh-CN');
        if (!groups[key]) groups[key] = [];
        groups[key].push(item);
      }});
      const sortedDates = Object.keys(groups).sort((a, b) => new Date(b) - new Date(a));

      const t = I18N[currentLang];
      let html = '';
      for (const date of sortedDates) {{
        html += '<div class="day-block"><div class="day-title">' + date + '</div>';
        for (const item of groups[date]) {{
          const d = new Date(item.published_at || item.first_collected_at);
          const timeStr = d.toTimeString().slice(0, 5);
          const cat = item.category || '综合';
          const catLabel = (t.cats && t.cats[cat]) || cat;
          const reasonLabel = currentLang === 'zh' ? '推荐理由：' : 'Why it matters: ';
          const brandDomains = JSON.parse('{brand_domains_json}');
          let brandHtml = '';
          if (item.brand && brandDomains[item.brand]) {{
            const bd = brandDomains[item.brand];
            brandHtml = '<img class="brand-logo feed-brand" src="https://favicon.im/' + bd + '?larger=true" data-domain="' + bd + '" data-try="0" alt="' + escapeHtml(item.brand) + '" title="' + escapeHtml(item.brand) + '" loading="lazy" onerror="fixFavicon(this)">';
          }}
          html += '<article class="feed-item" data-cat="' + escapeHtml(cat) + '" data-title="' + escapeHtml((item.title || '').toLowerCase()) + '" data-cost="0">' +
            brandHtml +
            '<div class="feed-main">' +
            '<div class="feed-meta">' +
              '<span class="feed-time">' + timeStr + '</span>' +
              '<span class="feed-source">' + escapeHtml(item.source || '') + '</span>' +
              '<span class="cat-tag">' + escapeHtml(catLabel) + '</span>' +
              '<span class="feed-heat">' + (item.heat || '') + '</span>' +
              '<button class="copy-btn" onclick="copyLink(event, this)" data-link="' + escapeHtml(item.link || '#') + '" title="复制链接">🔗</button>' +
            '</div>' +
            '<div class="feed-title"><a href="' + escapeHtml(item.link || '#') + '" target="_blank" rel="noopener">' +
              '<span class="lang-zh">' + escapeHtml(item.title || '') + '</span>' +
              '<span class="lang-en" style="display:none">' + escapeHtml(item.title_en || item.title || '') + '</span>' +
            '</a></div>' +
            '<div class="feed-summary">' +
              '<span class="lang-zh">' + escapeHtml(item.summary || '') + '</span>' +
              '<span class="lang-en" style="display:none">' + escapeHtml(item.summary_en || item.summary || '') + '</span>' +
            '</div>' +
            '<div class="feed-reason"><strong class="lang-zh">推荐理由：</strong><strong class="lang-en" style="display:none">Why it matters: </strong>' +
              '<span class="lang-zh">' + escapeHtml(item.reason || '') + '</span>' +
              '<span class="lang-en" style="display:none">' + escapeHtml(item.reason_en || item.reason || '') + '</span>' +
            '</div>' +
            (item.image ? '<div class="feed-image-wrap"><img class="feed-image" src="' + escapeHtml(item.image) + '" alt="" loading="lazy" onerror="this.parentElement.remove()"></div>' : '') +
            '</div>' +
          '</article>';
        }}
        html += '</div>';
      }}
      container.innerHTML = html || '<p class="no-data">' + (t.noData || '暂无数据') + '</p>';
      countEl.textContent = filtered.length + ' ' + t.items;

      // 更新分类标签的计数（基于当前历史数据）
      const catCounts = {{}};
      filtered.forEach(item => {{
        const c = item.category || '综合';
        catCounts[c] = (catCounts[c] || 0) + 1;
      }});
      document.querySelectorAll('.tag-btn').forEach(btn => {{
        const f = btn.dataset.filter;
        if (f === 'all' || f === 'cost') return;
        const count = catCounts[f] || 0;
        const label = (t.cats && t.cats[f]) || f;
        btn.textContent = label + ' (' + count + ')';
      }});
    }}

    document.querySelectorAll('.time-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const range = btn.dataset.range;
        if (range === 'today') {{
          document.getElementById('todayView').style.display = '';
          document.getElementById('historyView').style.display = 'none';
          // 恢复今日分类计数
          document.querySelectorAll('.tag-btn').forEach(btn => {{
            const f = btn.dataset.filter;
            if (f === 'all' || f === 'cost') return;
            const orig = btn.dataset.origText;
            if (orig) btn.textContent = orig;
          }});
        }} else {{
          tagBtns.forEach(b => b.classList.remove('active'));
          document.querySelector('.tag-btn[data-filter="all"]').classList.add('active');
          currentFilter = 'all';
          document.getElementById('todayView').style.display = 'none';
          document.getElementById('historyView').style.display = '';
          renderHistoryView(parseInt(range));
          filterItems();
        }}
      }});
    }});

    setLang(currentLang);

    // 回到顶部按钮
    const backToTopBtn = document.getElementById('backToTop');
    window.addEventListener('scroll', () => {{
      if (window.scrollY > 400) {{
        backToTopBtn.classList.add('show');
      }} else {{
        backToTopBtn.classList.remove('show');
      }}
    }});
  </script>
</body>
</html>"""


def save_history(entries):
    """将本次抓取的条目追加到 data/news_history.jsonl（按 link 去重）"""
    history_path = Path("data/news_history.jsonl")
    history_path.parent.mkdir(exist_ok=True)

    existing_links = set()
    if history_path.exists():
        for line in history_path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
                if item.get("link"):
                    existing_links.add(item["link"])
            except Exception:
                continue

    now_iso = datetime.now(timezone(timedelta(hours=8))).isoformat()
    new_count = 0
    with open(history_path, "a", encoding="utf-8") as f:
        for e in entries:
            if e["link"] in existing_links:
                continue
            existing_links.add(e["link"])
            item = {
                "id": hashlib.md5(e["link"].encode()).hexdigest()[:20],
                "title": e.get("title_zh") or e["title"],
                "title_en": e.get("title_en") or e["title"],
                "summary": e.get("summary_zh") or e.get("summary") or "",
                "summary_en": e.get("summary_en") or e.get("summary") or "",
                "link": e["link"],
                "source": e["source"],
                "published_at": e["dt"].astimezone(timezone.utc).isoformat(),
                "first_collected_at": now_iso,
                "last_seen_at": now_iso,
                "category": e["category"],
                "reason": e.get("reason_zh") or e.get("reason") or default_reason(e["category"], e["cost_flag"]),
                "reason_en": e.get("reason_en") or e.get("reason") or default_reason(e["category"], e["cost_flag"]),
                "ai_enhanced": USE_OLLAMA,
                "image": e.get("image") or "",
                "brand": e.get("brand") or "",
            }
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            new_count += 1
    print(f"历史记录: 新增 {new_count} 条 → {history_path}")


def cleanup_history(max_days=90, max_items=2000):
    """清理超过 max_days 天的历史数据，保留最多 max_items 条"""
    history_path = Path("data/news_history.jsonl")
    if not history_path.exists():
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
    kept = []
    removed = 0

    for line in history_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            dt_str = item.get("published_at", item.get("first_collected_at", ""))
            if dt_str:
                try:
                    dt = datetime.fromisoformat(dt_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt >= cutoff:
                        kept.append(line)
                    else:
                        removed += 1
                        continue
                except Exception:
                    kept.append(line)
            else:
                kept.append(line)
        except Exception:
            kept.append(line)

    if len(kept) > max_items:
        kept = kept[-max_items:]

    history_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    print(f"历史清理: 删除 {removed} 条超期数据，保留 {len(kept)} 条")
    return removed


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

    entries = fetch_entries(55)
    print(f"\n共获取 {len(entries)} 条 PC 相关资讯")
    cost_n = sum(1 for e in entries if e["cost_flag"])
    print(f"其中成本/价格相关: {cost_n} 条")

    # 推荐理由 + 中英双语（所有条目都生成双语字段，AI 增强仅限前 n 条）
    n = min(MAX_ENHANCE, len(entries)) if USE_OLLAMA else min(8, len(entries))
    print(f"\n处理前 {n} 条（AI 推荐理由），共 {len(entries)} 条生成双语字段...")
    for i, e in enumerate(entries):
        if i < n:
            print(f"  [{i+1}/{n}] {e['title'][:40]}...")
            if USE_OLLAMA:
                e["reason"] = enhance_reason(e["title"], e["summary"], e["category"], e["cost_flag"])
            else:
                e["reason"] = default_reason(e["category"], e["cost_flag"])
        else:
            e["reason"] = e.get("reason") or default_reason(e["category"], e["cost_flag"])
        # 所有条目都生成双语字段
        tz, te, sz, se, rz, re_ = bilingual_fields(
            e["title"], e["summary"], e["reason"], e["cost_flag"], e["category"]
        )
        e["title_zh"], e["title_en"] = tz, te
        e["summary_zh"], e["summary_en"] = sz, se
        e["reason_zh"], e["reason_en"] = rz, re_
        if i < n:
            print(f"      ZH: {tz[:36]}...")

    html = render_html(entries, history=load_history())
    Path("index.html").write_text(html, encoding="utf-8")
    print(f"\n已生成 index.html")

    save_history(entries)
    cleanup_history()

    # 发送邮件通知
    try:
        from send_email import send_daily_report
        top = [e.get("title_en") or e.get("title_zh") or e["title"] for e in entries[:6]]
        cost_n = sum(1 for e in entries if e.get("cost_flag"))
        send_daily_report(entry_count=len(entries), cost_count=cost_n, top_titles=top)
    except Exception as e:
        print("邮件通知跳过:", e)

    print("执行: git add index.html && git commit -m \"focus cost\" && git push --force")


if __name__ == "__main__":
    main()
