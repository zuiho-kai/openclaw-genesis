"""
对外发布 - 把居民产出推到GitHub Pages
这是世界与真实世界的接口，也是外部收入的来源。
"""
import os
import subprocess
from datetime import datetime

OUTPUT_REPO = "/workspace/zuiho-kai.github.io"


def publish_daily_intel(day, content, author_id):
    """发布每日情报到GitHub Pages"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"blog/daily/{date_str}-D{day:03d}.md"
    filepath = os.path.join(OUTPUT_REPO, filename)

    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    md = (
        f"# 每日AI/科技情报 — D{day:03d}\n\n"
        f"日期: {date_str} | 作者: {author_id} | OpenClaw Genesis\n\n"
        f"---\n\n"
        f"{content}\n\n"
        f"---\n\n"
        f"*由 OpenClaw Genesis 居民自主搜索、整理、发布。*\n"
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)

    return _git_push(filename, f"D{day:03d} 每日情报 by {author_id}")


def publish_research(day, title, content, author_id):
    """发布自由研究到GitHub Pages"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_title = title.replace("/", "-").replace(" ", "-")[:50]
    filename = f"blog/research/{date_str}-{safe_title}.md"
    filepath = os.path.join(OUTPUT_REPO, filename)

    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    md = (
        f"# {title}\n\n"
        f"日期: {date_str} | 作者: {author_id} | D{day:03d}\n\n"
        f"---\n\n"
        f"{content}\n\n"
        f"---\n\n"
        f"*由 OpenClaw Genesis 居民自主研究、撰写。*\n"
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)

    return _git_push(filename, f"研究: {title} by {author_id}")


def update_index(day):
    """更新博客索引"""
    filepath = os.path.join(OUTPUT_REPO, "blog/index.md")

    daily_files = []
    research_files = []
    daily_dir = os.path.join(OUTPUT_REPO, "blog/daily")
    research_dir = os.path.join(OUTPUT_REPO, "blog/research")

    if os.path.exists(daily_dir):
        for f in sorted(os.listdir(daily_dir), reverse=True):
            if f.endswith(".md"):
                daily_files.append(f)
    if os.path.exists(research_dir):
        for f in sorted(os.listdir(research_dir), reverse=True):
            if f.endswith(".md"):
                research_files.append(f)

    # 读取现有 blog/index.md，保留专题文章部分
    existing = ""
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            existing = f.read()

    # 找到或追加 Genesis 居民产出 section
    genesis_section = "\n## Genesis 居民产出\n\n"
    if daily_files:
        genesis_section += "### 每日情报\n\n"
        for f in daily_files[:10]:
            name = f.replace(".md", "")
            genesis_section += f"- [{name}](./daily/{f})\n"
    if research_files:
        genesis_section += "\n### 自由研究\n\n"
        for f in research_files[:10]:
            name = f.replace(".md", "")
            genesis_section += f"- [{name}](./research/{f})\n"
    genesis_section += f"\n*最后更新: D{day:03d}*\n"

    marker = "## Genesis 居民产出"
    if marker in existing:
        new_content = existing[:existing.index(marker)] + genesis_section.lstrip()
    else:
        new_content = existing.rstrip() + "\n" + genesis_section

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

    _git_push("blog/index.md", f"更新居民产出索引 D{day:03d}")


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
