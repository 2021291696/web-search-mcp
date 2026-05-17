"""
Web Search MCP Server — 多后端联网搜索
=========================================
专为 Claude Code + DeepSeek 用户设计。
自动检测最优后端，零配置可用。

后端优先级（自动检测环境变量）：
  1. Perplexity  — AI 驱动的搜索，需 PERPLEXITY_API_KEY
  2. Brave       — 高质量搜索 API，需 BRAVE_API_KEY
  3. SearXNG     — 自托管，隐私友好，需 SEARXNG_URL
  4. DuckDuckGo  — 免费免 Key，默认兜底

Provides: web_search(query, max_results) and web_fetch(url, prompt)
"""

import json
import os
import sys
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("web-search")

# ─── 后端检测 ───────────────────────────────────────────────────────

def detect_backend() -> str:
    """按优先级检测可用后端"""
    if os.environ.get("PERPLEXITY_API_KEY"):
        return "perplexity"
    if os.environ.get("BRAVE_API_KEY"):
        return "brave"
    if os.environ.get("SEARXNG_URL"):
        return "searxng"
    return "duckduckgo"

BACKEND = detect_backend()
BACKEND_LABELS = {
    "perplexity": "Perplexity AI",
    "brave": "Brave Search",
    "searxng": "SearXNG",
    "duckduckgo": "DuckDuckGo (Free)",
}

# ─── 工具注册 ────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools():
    backend_hint = BACKEND_LABELS[BACKEND]
    return [
        Tool(
            name="web_search",
            description=(
                f"Search the web using {backend_hint}. "
                "Returns title, URL, and snippet for each result. "
                "Use for current events, recent info, and factual lookups."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query string"},
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 5, max: 10)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="web_fetch",
            description=(
                "Fetch and extract readable content from a web page URL. "
                "Returns clean markdown text. Use for reading articles, documentation, and web pages."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL of the web page to fetch"},
                    "prompt": {
                        "type": "string",
                        "description": "What information to extract from the page (e.g. 'extract the main content')",
                    },
                },
                "required": ["url"],
            },
        ),
    ]

# ─── 搜索后端实现 ─────────────────────────────────────────────────────

def search_duckduckgo(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo — 免费免注册，全球可用（国内需梯子）"""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        raise RuntimeError(
            "duckduckgo_search not installed. Run: pip install duckduckgo-search"
        )

    results = list(DDGS().text(query, max_results=max_results))
    return [
        {"title": r.get("title", "N/A"), "url": r.get("href", "N/A"), "snippet": r.get("body", "")[:300]}
        for r in results
    ]


def search_brave(query: str, max_results: int = 5) -> list[dict]:
    """Brave Search API — 免费 2000次/月，注册: https://brave.com/search/api/"""
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        raise RuntimeError("BRAVE_API_KEY not set")

    import urllib.request
    import urllib.parse

    url = "https://api.search.brave.com/res/v1/web/search"
    params = urllib.parse.urlencode({"q": query, "count": min(max_results, 20)})
    req = urllib.request.Request(f"{url}?{params}")
    req.add_header("Accept", "application/json")
    req.add_header("X-Subscription-Token", api_key)

    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())

    results = []
    for r in (data.get("web", {}).get("results", [])):
        results.append({
            "title": r.get("title", "N/A"),
            "url": r.get("url", "N/A"),
            "snippet": r.get("description", "")[:300],
        })
    return results[:max_results]


def search_searxng(query: str, max_results: int = 5) -> list[dict]:
    """SearXNG — 自托管搜索聚合，可部署在国内/本地，隐私友好"""
    searxng_url = os.environ.get("SEARXNG_URL", "").rstrip("/")
    if not searxng_url:
        raise RuntimeError("SEARXNG_URL not set")

    import urllib.request
    import urllib.parse

    url = f"{searxng_url}/search"
    params = urllib.parse.urlencode({"q": query, "format": "json", "categories": "general"})
    req = urllib.request.Request(f"{url}?{params}")
    req.add_header("User-Agent", "web-search-mcp/2.0")

    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())

    results = []
    for r in data.get("results", [])[:max_results]:
        results.append({
            "title": r.get("title", "N/A"),
            "url": r.get("url", "N/A"),
            "snippet": r.get("content", "")[:300],
        })
    return results


def search_perplexity(query: str, max_results: int = 5) -> list[dict]:
    """Perplexity AI — 智能搜索+总结，需付费 API Key"""
    api_key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not api_key:
        raise RuntimeError("PERPLEXITY_API_KEY not set")

    import urllib.request

    # Use Perplexity's online model for search
    req = urllib.request.Request(
        "https://api.perplexity.ai/chat/completions",
        data=json.dumps({
            "model": "sonar-pro",
            "messages": [
                {"role": "system", "content": "Search the web and return results as a list. Include title, URL, and snippet for each."},
                {"role": "user", "content": query},
            ],
            "max_tokens": 1024,
        }).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    # Perplexity returns text, not structured results — return as single result
    text = data["choices"][0]["message"]["content"]
    return [{"title": f"Perplexity: {query[:80]}", "url": "", "snippet": text}]


SEARCH_BACKENDS = {
    "duckduckgo": search_duckduckgo,
    "brave": search_brave,
    "searxng": search_searxng,
    "perplexity": search_perplexity,
}

# ─── 工具调用 ────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "web_search":
        query = arguments.get("query", "")
        max_results = min(arguments.get("max_results", 5), 10)

        try:
            results = SEARCH_BACKENDS[BACKEND](query, max_results)
        except RuntimeError as e:
            # Missing dependency or config — try fallback to DDG
            if BACKEND != "duckduckgo":
                try:
                    results = search_duckduckgo(query, max_results)
                except Exception:
                    return [TextContent(type="text", text=f"Search error: {e}\n\n"
                        "Tip: DuckDuckGo is the free default. Make sure 'pip install duckduckgo-search' is installed.")]
            else:
                return [TextContent(type="text", text=f"Search error: {e}")]

        if not results:
            return [TextContent(type="text", text="No results found.")]

        output = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "N/A")
            url = r.get("url", "N/A")
            snippet = r.get("snippet", "")[:300]
            output.append(f"{i}. **{title}**\n   URL: {url}\n   {snippet}")

        return [TextContent(type="text", text="\n\n".join(output))]

    elif name == "web_fetch":
        url = arguments.get("url", "")
        prompt = arguments.get("prompt", "Extract the main content")

        try:
            import urllib.request

            req = urllib.request.Request(url)
            req.add_header("User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            with urllib.request.urlopen(req, timeout=15) as r:
                content_type = r.headers.get("Content-Type", "")
                raw = r.read()

            # Decode
            encoding = "utf-8"
            if "charset=" in content_type:
                encoding = content_type.split("charset=")[-1].split(";")[0].strip()
            html = raw.decode(encoding, errors="replace")

            # Simple HTML-to-text
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
            except ImportError:
                # Fallback: basic regex stripping
                import re
                text = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
                text = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text).strip()

            lines = [l.strip() for l in text.split("\n") if l.strip()]
            text = "\n".join(lines[:500])[:8000]

            return [TextContent(type="text",
                text=f"Content from {url}:\n\n{text}\n\n(Extracted with prompt: {prompt})")]
        except Exception as e:
            return [TextContent(type="text", text=f"Fetch error: {e}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    # Startup info
    print(f"[web-search] Backend: {BACKEND_LABELS[BACKEND]}", file=sys.stderr)
    if BACKEND == "duckduckgo":
        print("[web-search] Tip: Set BRAVE_API_KEY for higher quality search (free 2000/mo)", file=sys.stderr)
        print("[web-search] Tip: Set SEARXNG_URL for self-hosted search (China-friendly)", file=sys.stderr)
    asyncio.run(main())
