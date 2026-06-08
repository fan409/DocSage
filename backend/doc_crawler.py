"""
DocSage 文档爬虫 - 从开源项目官方文档站抓取内容并保存为可上传的文本文件。

用法:
    python backend/doc_crawler.py --source all --max-pages 100
    python backend/doc_crawler.py --source spring --max-pages 50
    python backend/doc_crawler.py --source mybatis --max-pages 30
    python backend/doc_crawler.py --source langchain --max-pages 80
"""

import argparse
import asyncio
import hashlib
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import httpx
from bs4 import BeautifulSoup


# ─── 文档源配置 ────────────────────────────────────────────────────────

DOC_SOURCES = {
    "spring": {
        "name": "Spring Framework",
        "base_url": "https://docs.spring.io/spring-framework/reference/",
        "allowed_domains": ["docs.spring.io"],
        "content_selectors": ["article", "main", "#content", ".content"],
        "title_selector": "h1",
        "exclude_selectors": [
            "nav", "footer", ".toc", ".sidebar", "script", "style",
            ".nav-links", ".breadcrumb", "header", "#TableOfContents",
        ],
    },
    "mybatis": {
        "name": "MyBatis",
        "base_url": "https://mybatis.org/mybatis-3/zh/",
        "allowed_domains": ["mybatis.org"],
        "content_selectors": ["#content", ".document", "article", "main"],
        "title_selector": "h1",
        "exclude_selectors": [
            "nav", "footer", ".sphinxsidebar", "script", "style",
            ".headerlink", ".related",
        ],
    },
    "langchain": {
        "name": "LangChain (Python)",
        "base_url": "https://python.langchain.com/docs/",
        "allowed_domains": ["python.langchain.com"],
        "content_selectors": ["article", "main", "[role='main']", ".markdown"],
        "title_selector": "h1",
        "exclude_selectors": [
            "nav", "footer", "script", "style", ".pagination",
            ".theme-doc-sidebar-container", ".table-of-contents",
            "aside",
        ],
    },
}

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "docs"
REQUEST_DELAY = 1.0  # seconds between requests
REQUEST_TIMEOUT = 30.0


def slugify(url: str, max_len: int = 80) -> str:
    """Generate a filesystem-safe slug from a URL path."""
    path = urlparse(url).path.strip("/")
    slug = re.sub(r"[^\w\-.]", "_", path)
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug:
        slug = hashlib.md5(url.encode()).hexdigest()[:12]
    return slug[:max_len]


def is_valid_url(url: str, base_url: str, allowed_domains: list[str]) -> bool:
    """Check if a URL belongs to the same doc site and is a doc page."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    if parsed.netloc not in allowed_domains:
        return False
    # Skip anchors, pure media, and API endpoints
    path = parsed.path
    if path.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".zip")):
        return False
    # Must be under the base path
    base_path = urlparse(base_url).path
    if not path.startswith(base_path):
        return False
    return True


def extract_content(soup: BeautifulSoup, config: dict) -> tuple[str, str]:
    """Extract title and main text content from a parsed page."""
    # Remove unwanted elements
    for selector in config["exclude_selectors"]:
        for tag in soup.select(selector):
            tag.decompose()

    # Extract title
    title_tag = soup.select_one(config["title_selector"])
    title = title_tag.get_text(strip=True) if title_tag else ""

    # Extract content from the first matching selector
    content_element = None
    for selector in config["content_selectors"]:
        content_element = soup.select_one(selector)
        if content_element:
            break

    if not content_element:
        content_element = soup.body or soup

    # Convert to clean text, preserving structure
    lines = []
    for element in content_element.descendants:
        if element.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(element.name[1])
            text = element.get_text(strip=True)
            if text:
                lines.append(f"\n{'#' * level} {text}\n")
        elif element.name == "p":
            text = element.get_text(strip=True)
            if text:
                lines.append(text + "\n")
        elif element.name in ("li",):
            text = element.get_text(strip=True)
            if text:
                lines.append(f"- {text}")
        elif element.name == "pre":
            code = element.get_text()
            if code.strip():
                lines.append(f"\n```\n{code.strip()}\n```\n")
        elif element.name in ("td", "th"):
            text = element.get_text(strip=True)
            if text:
                lines.append(f"| {text} ", )
        elif element.name == "tr":
            lines.append("|")
        elif element.name in ("code",) and element.parent and element.parent.name != "pre":
            text = element.get_text(strip=True)
            if text:
                # inline code, handled at parent level
                pass

    content = "\n".join(lines)
    # Clean up excessive whitespace
    content = re.sub(r"\n{3,}", "\n\n", content)
    return title, content.strip()


async def crawl_source(
    source_key: str,
    config: dict,
    max_pages: int,
    client: httpx.AsyncClient,
) -> int:
    """Crawl a single documentation source. Returns count of pages saved."""
    base_url = config["base_url"]
    allowed_domains = config["allowed_domains"]
    output_dir = OUTPUT_DIR / source_key
    output_dir.mkdir(parents=True, exist_ok=True)

    visited: set[str] = set()
    queue: list[str] = [base_url]
    saved_count = 0

    print(f"\n{'='*60}")
    print(f"  Crawling: {config['name']}")
    print(f"  Base URL: {base_url}")
    print(f"  Max pages: {max_pages}")
    print(f"  Output: {output_dir}")
    print(f"{'='*60}")

    while queue and saved_count < max_pages:
        url = queue.pop(0)
        url = urldefrag(url)[0]  # strip fragment

        if url in visited:
            continue
        visited.add(url)

        try:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
        except (httpx.HTTPError, Exception) as e:
            print(f"  [SKIP] {url} -> {e}")
            await asyncio.sleep(REQUEST_DELAY)
            continue

        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type:
            await asyncio.sleep(REQUEST_DELAY)
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        title, text = extract_content(soup, config)

        if len(text) < 100:
            await asyncio.sleep(REQUEST_DELAY)
            continue

        # Save the page
        slug = slugify(url)
        filepath = output_dir / f"{slug}.txt"
        meta_header = f"---\ntitle: {title}\nurl: {url}\nsource: {config['name']}\n---\n\n"
        filepath.write_text(meta_header + text, encoding="utf-8")
        saved_count += 1
        print(f"  [{saved_count}/{max_pages}] {slug}.txt ({len(text)} chars)")

        # Discover new links
        for link in soup.find_all("a", href=True):
            abs_url = urljoin(url, link["href"])
            if is_valid_url(abs_url, base_url, allowed_domains) and abs_url not in visited:
                queue.append(abs_url)

        await asyncio.sleep(REQUEST_DELAY)

    print(f"  Done: {saved_count} pages saved to {output_dir}")
    return saved_count


async def main():
    parser = argparse.ArgumentParser(description="DocSage 文档爬虫")
    parser.add_argument(
        "--source",
        choices=["spring", "mybatis", "langchain", "all"],
        default="all",
        help="要爬取的文档源 (default: all)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=100,
        help="每个源最多爬取的页数 (default: 100)",
    )
    args = parser.parse_args()

    sources = DOC_SOURCES if args.source == "all" else {args.source: DOC_SOURCES[args.source]}

    headers = {
        "User-Agent": "DocSage-Bot/1.0 (educational; open-source doc assistant)",
        "Accept": "text/html,application/xhtml+xml",
    }

    async with httpx.AsyncClient(
        headers=headers,
        timeout=REQUEST_TIMEOUT,
        limits=httpx.Limits(max_connections=2),
    ) as client:
        total = 0
        for key, config in sources.items():
            count = await crawl_source(key, config, args.max_pages, client)
            total += count

    print(f"\nTotal pages crawled: {total}")
    print(f"Files saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
