#!/usr/bin/env python3
"""迁移脚本：重新分类 + 过滤无关条目 + 清理过期数据

用法：
    python scripts/migrate_history.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from generate_news import get_category, is_relevant, cleanup_history


def main():
    history_path = Path(__file__).parent.parent / "data" / "news_history.jsonl"
    if not history_path.exists():
        print("未找到 data/news_history.jsonl，跳过")
        return

    lines = history_path.read_text(encoding="utf-8").splitlines()
    updated = 0
    removed = 0
    total = 0
    new_lines = []

    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            total += 1
            title = item.get("title", "")
            summary = item.get("summary", "")

            # 用新过滤逻辑剔除无关条目
            if not is_relevant(title, summary):
                removed += 1
                continue

            # 重新分类
            old_cat = item.get("category", "")
            new_cat = get_category(title, summary)
            if old_cat != new_cat:
                item["category"] = new_cat
                updated += 1
            new_lines.append(json.dumps(item, ensure_ascii=False))
        except Exception as e:
            print(f"  跳过无法解析的行: {e}")
            new_lines.append(line)

    history_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"重新分类: 共 {total} 条，修正 {updated} 条分类，删除 {removed} 条无关")

    # 清理超期数据
    cleanup_history()


if __name__ == "__main__":
    main()
