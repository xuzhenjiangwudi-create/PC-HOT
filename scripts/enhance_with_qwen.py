#!/usr/bin/env python3
"""
PC HOT - 本地 Qwen 增强脚本（配合 Ollama）
功能：用本地 Qwen 模型生成更好的中文推荐理由 / 摘要
使用前请确保 Ollama 已启动，并且已拉取模型，例如：
  ollama pull qwen2.5:7b
  或你实际使用的模型名
"""

import json
import requests
from pathlib import Path
from datetime import datetime

# ============ 配置区 ============
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:7b"   # 改成你实际的模型名，比如 qwen2:7b / qwen:7b 等
MAX_ITEMS = 20             # 最多增强多少条（避免太慢）
# ==============================

def call_qwen(prompt: str, max_tokens: int = 200) -> str:
    """调用本地 Ollama"""
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.4,
                    "num_predict": max_tokens,
                }
            },
            timeout=90
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"  调用模型失败: {e}")
        return ""


def enhance_reason(title: str, summary: str, category: str) -> str:
    """生成更好的推荐理由"""
    prompt = f"""你是一名专业的 PC 硬件与科技媒体编辑。请根据下面的新闻，用 1-2 句中文写出简洁有价值的「推荐理由」。

要求：
- 不要复述标题
- 指出为什么值得关注（比如对价格、性能、生态、供应链的影响）
- 语气客观专业
- 不要超过 60 个字

新闻标题：{title}
摘要：{summary or '无'}
分类：{category}

直接输出推荐理由，不要加“推荐理由：”等前缀："""

    result = call_qwen(prompt, max_tokens=120)
    if not result:
        return "来自公开源聚合，点击标题可阅读原文。"
    # 简单清理
    result = result.replace("推荐理由：", "").replace("推荐理由", "").strip()
    return result[:100]


def main():
    print("=" * 50)
    print("PC HOT × 本地 Qwen 增强")
    print("=" * 50)

    # 检查 Ollama 是否可用
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        print(f"检测到本地模型: {models}")
        if not any(MODEL_NAME.split(":")[0] in m for m in models):
            print(f"\n警告：未找到包含 '{MODEL_NAME}' 的模型。")
            print("请先运行: ollama pull qwen2.5:7b   （或你实际的模型名）")
            print("然后修改本脚本顶部的 MODEL_NAME\n")
    except Exception as e:
        print(f"无法连接 Ollama ({e})")
        print("请先启动 Ollama，并确保服务在 http://localhost:11434")
        return

    # 这里演示如何增强几条示例新闻
    # 实际使用时，你可以先运行 generate_news.py 生成 index.html，
    # 或者把增强逻辑直接集成进 generate_news.py

    demo_items = [
        {
            "title": "Nvidia raises RTX Pro 6000 Blackwell price to a staggering $16,000",
            "summary": "The RTX Pro 6000 has gone through multiple price revisions since its launch, driven by the AI-fueled memory crunch.",
            "category": "显卡"
        },
        {
            "title": "Qualcomm's Snapdragon C wants to be the Arm chip for $300 laptops",
            "summary": "The processor has eight Qualcomm Kryo CPU cores, targeting budget Windows PCs.",
            "category": "处理器"
        },
    ]

    print(f"\n开始用 {MODEL_NAME} 生成推荐理由（演示 {len(demo_items)} 条）...\n")

    for i, item in enumerate(demo_items, 1):
        print(f"[{i}] {item['title'][:50]}...")
        reason = enhance_reason(item["title"], item["summary"], item["category"])
        print(f"    → {reason}\n")

    print("演示完成。")
    print("\n下一步建议：")
    print("1. 确认 MODEL_NAME 正确")
    print("2. 把 enhance_reason() 函数集成进 generate_news.py")
    print("3. 本地运行 generate_news.py 生成页面后 git push")


if __name__ == "__main__":
    main()
