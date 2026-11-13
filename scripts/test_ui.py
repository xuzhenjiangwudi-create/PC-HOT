"""快速生成带模拟数据的 UI demo 页面，用于验证新的 Bento Grid 设计"""
import sys
sys.path.insert(0, 'scripts')
from generate_news import render_html
from datetime import datetime, timezone, timedelta

# 模拟数据
now = datetime.now(timezone(timedelta(hours=8)))
mock_entries = []
brands = ["Lenovo", "HP", "Dell", "ASUS", "Acer", "Apple", "Microsoft", "Huawei"]
categories = ["AI与芯片", "OEM品牌", "ODM代工", "成本价格", "市场出货", "产品发布", "综合"]
sources = ["快科技", "IT之家", "中关村在线", "笔吧评测室", "超能网"]

for i in range(15):
    dt = now - timedelta(hours=i * 2)
    brand = brands[i % len(brands)]
    cat = categories[i % len(categories)]
    mock_entries.append({
        "title": f"测试新闻标题 {i+1} - {brand}发布新产品",
        "title_zh": f"测试新闻标题 {i+1} - {brand}发布新一代AI PC产品",
        "title_en": f"Test News {i+1} - {brand} Launches New AI PC",
        "link": f"https://example.com/news/{i+1}",
        "source": sources[i % len(sources)],
        "dt": dt,
        "category": cat,
        "cost_flag": i % 3 == 0,
        "brand": brand,
        "summary": f"这是第 {i+1} 条新闻的摘要内容，简要介绍了{brand}在{cat}领域的最新动态。",
        "summary_en": f"Summary of news {i+1} about {brand}'s latest development in {cat}.",
        "reason": f"该新闻涉及{cat}领域的重要进展，对行业格局有一定影响。",
        "reason_en": f"This news covers important progress in {cat}, which has certain impact on the industry landscape.",
        "image": f"https://picsum.photos/seed/news{i}/800/450" if i < 5 else None,
    })

# 模拟简报数据
briefing = {
    "zh": {
        "summary": "今日PC行业整体活跃度较高，AI PC赛道持续升温。联想、惠普等头部厂商相继发布新品，供应链方面内存价格出现波动。",
        "highlights": [
            "AI PC 新品密集发布，联想 YOGA 系列升级 Copilot+ 功能",
            "内存价格持续上涨，DRAM 合约价 Q4 预计涨 5-8%",
            "惠普发布新一代 ProBook 商务本，搭载骁龙 X Elite",
            "华硕 ROG 游戏本销量同比增长 23%，电竞市场回暖",
        ]
    },
    "en": {
        "summary": "Today's PC industry is highly active, with the AI PC track continuing to heat up. Leading manufacturers such as Lenovo and HP have successively released new products, and memory prices have fluctuated in the supply chain.",
        "highlights": [
            "AI PC new products密集发布, Lenovo YOGA series upgrades Copilot+ features",
            "Memory prices continue to rise, DRAM contract prices expected to rise 5-8% in Q4",
            "HP launches new ProBook business laptops with Snapdragon X Elite",
            "ASUS ROG gaming laptop sales up 23% YoY, e-sports market recovers",
        ]
    }
}

# 模拟竞品数据
competitor_data = {
    "brands": [
        {"name": "Lenovo", "total": 12, "trend7": [2, 1, 3, 2, 1, 2, 1]},
        {"name": "HP", "total": 8, "trend7": [1, 2, 1, 1, 2, 1, 0]},
        {"name": "Dell", "total": 6, "trend7": [1, 0, 1, 2, 1, 1, 0]},
        {"name": "ASUS", "total": 5, "trend7": [0, 1, 1, 0, 1, 1, 1]},
    ]
}

# 模拟价格雷达
price_radar = {
    "today_count": 5,
    "recent_count": 23,
    "by_brand": [
        ("Lenovo", 8), ("HP", 6), ("Dell", 4), ("ASUS", 3), ("Acer", 2)
    ]
}

html = render_html(mock_entries, history=[], briefing=briefing,
                   competitor_data=competitor_data, price_radar=price_radar)

with open('ui_demo.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Demo generated: ui_demo.html")
print(f"Total entries: {len(mock_entries)}")
