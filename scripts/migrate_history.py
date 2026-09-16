#!/usr/bin/env python3
"""迁移脚本：用当前分类逻辑重新分类 news_history.jsonl 中的旧数据

用法：
    python scripts/migrate_history.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from generate_news import get_category


def main():
    history_path = Path(__file__).parent.parent / "data" / "news_history.jsonl"
    if not history_path.exists():
        print("未找到 data/news_history.jsonl，跳过")
        return

    lines = history_path.read_text(encoding="utf-8").splitlines()
    updated = 0
    total = 0
    new_lines = []

    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            total += 1
            old_cat = item.get("category", "")
            new_cat = get_category(item.get("title", ""), item.get("summary", ""))
            if old_cat != new_cat:
                item["category"] = new_cat
                updated += 1
            new_lines.append(json.dumps(item, ensure_ascii=False))
        except Exception as e:
            print(f"  跳过无法解析的行: {e}")
            new_lines.append(line)

    history_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"完成: 共 {total} 条，修正 {updated} 条分类")


if __name__ == "__main__":
    main()
