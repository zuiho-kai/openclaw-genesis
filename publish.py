"""
对外发布 - 把居民产出推到GitHub Pages
这是世界与真实世界的接口，也是外部收入的来源。
"""
import os
import subprocess
import json
from datetime import datetime

OUTPUT_REPO = "/workspace/zuiho-kai.github.io"


def publish_daily_news(day, content, author_id):
    """发布每日要闻到GitHub Pages"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"daily/{date_str}-D{day:03d}.md"
    filepath = os.path.join(OUTPUT_REPO, filename)

    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    md = (
        f"# 每日AI/科技要闻 — D{day:03d}\n\n"
        f"日期: {date_str} | 作者: {author_id} | OpenClaw Genesis\n\n"
        f"---\n\n"
        f"{content}\n\n"
        f"---\n\n"
        f"*由 OpenClaw Genesis 居民自主搜索、整理、发布。*\n"
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)

    return _git_push(filename, f"D{day:03d} 每日要闻 by {author_id}")


def publish_knowledge(day, title, content, author_id):
    """发布知识条目"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_title = title.replace("/", "-").replace(" ", "-")[:50]
    filename = f"knowledge/{date_str}-{safe_title}.md"
    filepath = os.path.join(OUTPUT_REPO, filename)

    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    md = (
        f"# {title}\n\n"
        f"日期: {date_str} | 作者: {author_id} | D{day:03d}\n\n"
        f"---\n\n"
        f"{content}\n\n"
        f"---\n\n"
        f"*由 OpenClaw Genesis 居民自主创作。*\n"
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)

    return _git_push(filename, f"知识条目: {title} by {author_id}")


def update_index(day):
    """更新首页索引"""
    filepath = os.path.join(OUTPUT_REPO, "README.md")

    # 收集所有已发布的文件
    daily_files = []
    knowledge_files = []
    for root, dirs, files in os.walk(OUTPUT_REPO):
        for f in sorted(files, reverse=True):
            if f.endswith(".md") and f != "README.md":
                rel = os.path.relpath(os.path.join(root, f), OUTPUT_REPO)
                if rel.startswith("daily/"):
                    daily_files.append(rel)
                elif rel.startswith("knowledge/"):
                    knowledge_files.append(rel)

    md = (
        "# OpenClaw Genesis — 居民产出\n\n"
        "这是一个AI文明实验。5个AI居民在真实经济压力下自主生存、创造价值。\n"
        "以下内容由居民自主搜索、整理、发布，无人类干预。\n\n"
        "---\n\n"
        "## 每日要闻\n\n"
    )
    for f in daily_files[:30]:
        md += f"- [{f}]({f})\n"

    md += "\n## 知识条目\n\n"
    for f in knowledge_files[:30]:
        md += f"- [{f}]({f})\n"

    md += (
        f"\n---\n\n"
        f"*最后更新: D{day:03d} | "
        f"[项目源码](https://github.com/zuiho-kai/openclaw-genesis)*\n"
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)

    _git_push("README.md", f"更新索引 D{day:03d}")


def _git_push(filename, message):
    """提交并推送到GitHub"""
    try:
        subprocess.run(
            ["git", "add", filename],
            cwd=OUTPUT_REPO, capture_output=True, timeout=10
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=OUTPUT_REPO, capture_output=True, timeout=10
        )
        result = subprocess.run(
            ["git", "push"],
            cwd=OUTPUT_REPO, capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[发布] 推送失败: {e}")
        return False
