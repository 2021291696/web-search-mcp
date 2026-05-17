"""
Web Search MCP Server — AI 驱动的联网搜索
============================================
专为 Claude Code + DeepSeek 用户设计。
通过调用有联网能力的 AI 模型 API 实现搜索，无需自部署。

后端优先级（自动检测环境变量）：
  1. Zhipu GLM  — 智谱，国内首选，OPENAI 兼容接口 + GLM_API_KEY
  2. Perplexity  — 国际 AI 搜索，PERPLEXITY_API_KEY
  3. OpenRouter  — 聚合多模型，含联网版 Claude/GPT，OPENROUTER_API_KEY
  4. DuckDuckGo — 免费免 Key，默认兜底

Provides: web_search(query, max_results) and web_fetch(url, prompt)
"""

import json
import os
import sys
import asyncio
import re
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("web-search")

# ─── 后端检测 ───────────────────────────────────────────────────────

def detect_backend() -> str:
    if os.environ.get("GLM_API_KEY"):
        return "zhipu"
    if os.environ.get("PERPLEXITY_API_KEY"):
        return "perplexity"
    if os.environ.get("OPENROUTER_API_KEY"):
        return "openrouter"
    return "duckduckgo"

BACKEND = detect_backend()
BACKEND_LABELS = {
    "zhipu": "Zhipu GLM (智谱)",
    "perplexity": "Perplexity AI",
    "openrouter": "OpenRouter",
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

def _call_openai_compatible(base_url: str, api_key: str, model: str, messages: list,
                            tools: list = None, max_tokens: int = 1024) -> str:
    """通用 OPENAI 兼容接口调用"""
    import urllib.request

    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())

    return data["choices"][0]["message"]["content"]


def search_zhipu(query: str, max_results: int = 5) -> list[dict]:
    """智谱 GLM — 国内首选，OPENAI 兼容接口，支持联网搜索"""
    api_key = os.environ.get("GLM_API_KEY", "")
    base_url = os.environ.get("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    model = os.environ.get("GLM_MODEL", "glm-4-flash")

    if not api_key:
        raise RuntimeError("GLM_API_KEY not set. Get one at https://open.bigmodel.cn/")

    # 智谱的 web_search 通过 tools 机制触发
    result = _call_openai_compatible(
        base_url=base_url,
        api_key=api_key,
        model=model,
        messages=[
            {"role": "system", "content": "你是一个搜索助手。搜索并返回结果，每条包含标题、URL和摘要。格式：\n1. **标题**\n   URL: 链接\n   摘要"},
            {"role": "user", "content": f"搜索：{query}\n\n请返回最多{max_results}条结果，每条包含标题、URL和摘要。"},
        ],
        tools=[{
            "type": "web_search",
            "web_search": {
                "search_query": query,
                "search_result": True,
            },
        }],
    )

    # 解析智谱返回的搜索结果
    return _parse_search_text(result, max_results)


def search_perplexity(query: str, max_results: int = 5) -> list[dict]:
    """Perplexity — 国际 AI 搜索，质量高"""
    api_key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not api_key:
        raise RuntimeError("PERPLEXITY_API_KEY not set. Get one at https://www.perplexity.ai/")

    result = _call_openai_compatible(
        base_url="https://api.perplexity.ai",
        api_key=api_key,
        model=os.environ.get("PERPLEXITY_MODEL", "sonar-pro"),
        messages=[
            {"role": "system", "content": "Search the web and return results as a numbered list. Include title, URL, and snippet for each result."},
            {"role": "user", "content": query},
        ],
    )

    return _parse_search_text(result, max_results)


def search_openrouter(query: str, max_results: int = 5) -> list[dict]:
    """OpenRouter — 聚合平台，可调用多种联网模型"""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    # 支持用户自定义模型，默认用 Gemini（有联网能力）
    model = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash")

    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set. Get one at https://openrouter.ai/")

    result = _call_openai_compatible(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        model=model,
        messages=[
            {"role": "system", "content": "Search the web and return results as a numbered list. Include title, URL, and snippet for each result. Search the web first, then summarize."},
            {"role": "user", "content": query},
        ],
        max_tokens=2048,
    )

    return _parse_search_text(result, max_results)


def search_duckduckgo(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo — 免费免注册，兜底方案"""
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


def _parse_search_text(text: str, max_results: int) -> list[dict]:
    """从 AI 回复中解析搜索结果"""
    results = []

    # 尝试匹配编号格式：1. **Title**\n   URL: xxx\n   Snippet
    pattern = r'(?:\d+[\.\)]\s*)?\*\*(.+?)\*\*\s*\n\s*(?:URL|url|链接)?[：:]\s*(\S+)\s*\n\s*(.*?)(?=\n\d+[\.\)]|\n\*\*|\Z)'
    matches = re.findall(pattern, text, re.DOTALL)

    for title, url, snippet in matches[:max_results]:
        if url and url.startswith("http"):
            results.append({"title": title.strip(), "url": url.strip(), "snippet": snippet.strip()[:300]})

    if results:
        return results

    # 如果没匹配到结构化结果，返回原始文本作为单条
    return [{"title": "Search result", "url": "", "snippet": text[:1000]}]


SEARCH_BACKENDS = {
    "zhipu": search_zhipu,
    "perplexity": search_perplexity,
    "openrouter": search_openrouter,
    "duckduckgo": search_duckduckgo,
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
            if BACKEND != "duckduckgo":
                try:
                    results = search_duckduckgo(query, max_results)
                except Exception:
                    return [TextContent(type="text", text=f"Search error: {e}")]
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
                raw = r.read()

            content_type = r.headers.get("Content-Type", "")
            encoding = "utf-8"
            if "charset=" in content_type:
                encoding = content_type.split("charset=")[-1].split(";")[0].strip()
            html = raw.decode(encoding, errors="replace")

            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
            except ImportError:
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
    print(f"[web-search] Backend: {BACKEND_LABELS[BACKEND]}", file=sys.stderr)
    if BACKEND == "duckduckgo":
        print("[web-search] ======================================", file=sys.stderr)
        print("[web-search]   Zero config mode (DuckDuckGo Free)", file=sys.stderr)
        print("[web-search] ======================================", file=sys.stderr)
        print("[web-search]", file=sys.stderr)
        print("[web-search]   Upgrade options (just set one env var):", file=sys.stderr)
        print("[web-search]   🇨🇳 国内 → setx GLM_API_KEY \"your-key\"", file=sys.stderr)
        print("[web-search]       注册: https://open.bigmodel.cn/", file=sys.stderr)
        print("[web-search]   🌍 Global → setx PERPLEXITY_API_KEY \"your-key\"", file=sys.stderr)
        print("[web-search]       注册: https://www.perplexity.ai/", file=sys.stderr)
        print("[web-search]   🔀 Universal → setx OPENROUTER_API_KEY \"your-key\"", file=sys.stderr)
        print("[web-search]       注册: https://openrouter.ai/", file=sys.stderr)
    asyncio.run(main())
