"""
Web Search MCP Server — AI 驱动的联网搜索
============================================
专为 Claude Code + DeepSeek 等无联网功能的 API 用户设计。
只设一个环境变量，AI 自己去搜索。

后端（设置任意一个即可，按优先级自动选择）：

  国内 — 设任一 KEY 即用：
    Zhipu     GLM_API_KEY      智谱 GLM，联网 tool calling
    Qwen      DASHSCOPE_API_KEY 阿里百炼，通义千问
    Kimi      MOONSHOT_API_KEY  月之暗面，Kimi 联网
    DeepSeek  DEEPSEEK_API_KEY  DeepSeek 平台（非开源模型，平台有联网）
    SiliconFlow SILICONFLOW_API_KEY 硅基流动，超市型聚合

  国际 — 设任一 KEY 即用：
    Perplexity  PERPLEXITY_API_KEY  AI 原生搜索，质量最高
    Gemini      GEMINI_API_KEY      Google 搜索原生集成，质量最高
    Brave       BRAVE_API_KEY       传统搜索 API，免费 2000/月
    OpenRouter  OPENROUTER_API_KEY  聚合平台，多模型可选

  兜底 — 什么都不设：
    DuckDuckGo  免费，零配置

Provides: web_search(query, max_results) and web_fetch(url, prompt)
"""

import json
import os
import sys
import asyncio
import re
import urllib.request
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("web-search")

# ─── Provider 注册表 ─────────────────────────────────────────────────

PROVIDERS = [
    # (env_var, name, label, region)
    # 国内
    ("GLM_API_KEY",       "zhipu",       "Zhipu GLM (智谱)",        "cn"),
    ("DASHSCOPE_API_KEY", "qwen",        "Qwen (通义千问)",          "cn"),
    ("MOONSHOT_API_KEY",  "kimi",        "Kimi (月之暗面)",          "cn"),
    ("DEEPSEEK_API_KEY",  "deepseek",    "DeepSeek Platform",        "cn"),
    ("SILICONFLOW_API_KEY","siliconflow", "SiliconFlow (硅基流动)",   "cn"),
    # 国际
    ("PERPLEXITY_API_KEY","perplexity",  "Perplexity AI",            "intl"),
    ("GEMINI_API_KEY",    "gemini",      "Gemini (Google Search)",   "intl"),
    ("BRAVE_API_KEY",     "brave",       "Brave Search API",         "intl"),
    ("OPENROUTER_API_KEY","openrouter",  "OpenRouter",               "intl"),
]

def detect_backend() -> str:
    for env_var, name, _, _ in PROVIDERS:
        if os.environ.get(env_var):
            return name
    return "duckduckgo"

BACKEND = detect_backend()
PROVIDER_MAP = {p[1]: p for p in PROVIDERS}
BACKEND_LABEL = PROVIDER_MAP.get(BACKEND, (None, None, "DuckDuckGo (Free)", None))[2]

# ─── 工具注册 ────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="web_search",
            description=(
                f"Search the web using {BACKEND_LABEL}. "
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
                "Returns clean markdown text."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL of the web page to fetch"},
                    "prompt": {
                        "type": "string",
                        "description": "What information to extract from the page",
                    },
                },
                "required": ["url"],
            },
        ),
    ]

# ─── OPENAI 兼容接口（通用） ──────────────────────────────────────────

def _openai_chat(base_url: str, api_key: str, model: str, system: str,
                 user: str, tools: list = None, max_tokens: int = 1024,
                 extra_headers: dict = None) -> str:
    """调用任意 OPENAI 兼容接口"""
    body = {"model": model, "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], "max_tokens": max_tokens}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]


# ─── 搜索后端 ────────────────────────────────────────────────────────

SEARCH_SYSTEM = (
    "You are a web search assistant. Search the web for the user's query. "
    "Return results as a numbered list. Each result MUST include:\n"
    "1. **Title**\n   URL: https://...\n   Snippet: brief summary"
)


def search_zhipu(query: str, max_results: int = 5) -> list[dict]:
    """智谱 GLM — 联网 via tool calling"""
    return _openai_chat(
        base_url=os.environ.get("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
        api_key=os.environ["GLM_API_KEY"],
        model=os.environ.get("GLM_MODEL", "glm-4-flash"),
        system=SEARCH_SYSTEM,
        user=f"Search: {query}\nReturn at most {max_results} results.",
        tools=[{"type": "web_search", "web_search": {"search_query": query, "search_result": True}}],
    )


def search_qwen(query: str, max_results: int = 5) -> list[dict]:
    """通义千问 — 阿里百炼，支持联网搜索"""
    return _openai_chat(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=os.environ["DASHSCOPE_API_KEY"],
        model=os.environ.get("DASHSCOPE_MODEL", "qwen-plus"),
        system=SEARCH_SYSTEM,
        user=f"Search the web and return results: {query} (max {max_results})",
        tools=[{"type": "web_search", "web_search": {"search_query": query}}],
    )


def search_kimi(query: str, max_results: int = 5) -> list[dict]:
    """Kimi — 月之暗面，支持联网"""
    return _openai_chat(
        base_url="https://api.moonshot.cn/v1",
        api_key=os.environ["MOONSHOT_API_KEY"],
        model=os.environ.get("MOONSHOT_MODEL", "moonshot-v1-auto"),
        system=SEARCH_SYSTEM,
        user=f"Search: {query}\nReturn at most {max_results} results.",
    )


def search_deepseek(query: str, max_results: int = 5) -> list[dict]:
    """DeepSeek Platform — 平台 API（非开源模型），支持联网"""
    return _openai_chat(
        base_url="https://api.deepseek.com/v1",
        api_key=os.environ["DEEPSEEK_API_KEY"],
        model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        system=SEARCH_SYSTEM + " Enable web search.",
        user=f"Search: {query}\nReturn at most {max_results} results.",
        tools=[{"type": "web_search", "web_search": {"search_query": query, "search_result": True}}],
    )


def search_siliconflow(query: str, max_results: int = 5) -> list[dict]:
    """硅基流动 — 模型超市，可用有联网能力的模型"""
    return _openai_chat(
        base_url="https://api.siliconflow.cn/v1",
        api_key=os.environ["SILICONFLOW_API_KEY"],
        model=os.environ.get("SILICONFLOW_MODEL", "Qwen/Qwen3-235B-A22B"),
        system=SEARCH_SYSTEM + " If you have web search capability, use it. Otherwise, search from your knowledge and provide URLs you're confident about.",
        user=f"Search: {query}\nReturn at most {max_results} results.",
    )


def search_perplexity(query: str, max_results: int = 5) -> list[dict]:
    """Perplexity — 国际 AI 搜索"""
    return _openai_chat(
        base_url="https://api.perplexity.ai",
        api_key=os.environ["PERPLEXITY_API_KEY"],
        model=os.environ.get("PERPLEXITY_MODEL", "sonar-pro"),
        system=SEARCH_SYSTEM,
        user=f"Search: {query}\nReturn at most {max_results} results.",
    )


def search_gemini(query: str, max_results: int = 5) -> str:
    """Gemini — Google 搜索原生集成"""
    api_key = os.environ["GEMINI_API_KEY"]
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    body = json.dumps({
        "contents": [{"parts": [{"text": f"{SEARCH_SYSTEM}\n\nSearch: {query}\nReturn at most {max_results} results."}]}],
        "tools": [{"googleSearch": {}}],
    }).encode()

    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return data["candidates"][0]["content"]["parts"][0]["text"]


def search_brave(query: str, max_results: int = 5) -> list[dict]:
    """Brave Search API — 传统搜索，免费 2000/月"""
    import urllib.parse
    url = f"https://api.search.brave.com/res/v1/web/search?q={urllib.parse.quote(query)}&count={min(max_results, 20)}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    req.add_header("X-Subscription-Token", os.environ["BRAVE_API_KEY"])
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    return [{"title": r["title"], "url": r["url"], "snippet": r.get("description", "")[:300]}
            for r in data.get("web", {}).get("results", [])[:max_results]]


def search_openrouter(query: str, max_results: int = 5) -> list[dict]:
    """OpenRouter — 聚合平台"""
    return _openai_chat(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
        model=os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash"),
        system=SEARCH_SYSTEM,
        user=f"Search the web: {query}\nReturn at most {max_results} results.",
        max_tokens=2048,
    )


def search_duckduckgo(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo — 免费兜底"""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        raise RuntimeError("duckduckgo_search not installed. Run: pip install duckduckgo-search")
    return [{"title": r.get("title","N/A"), "url": r.get("href","N/A"), "snippet": r.get("body","")[:300]}
            for r in list(DDGS().text(query, max_results=max_results))]


SEARCH_FUNCTIONS = {
    "zhipu": search_zhipu, "qwen": search_qwen, "kimi": search_kimi,
    "deepseek": search_deepseek, "siliconflow": search_siliconflow,
    "perplexity": search_perplexity, "gemini": search_gemini,
    "brave": search_brave, "openrouter": search_openrouter,
    "duckduckgo": search_duckduckgo,
}

# Gemini returns str not list, wrap it
ORIG_GEMINI = search_gemini
def search_gemini_wrapped(q, n):
    return _parse_search_text(ORIG_GEMINI(q, n), n)
SEARCH_FUNCTIONS["gemini"] = search_gemini_wrapped


def _parse_search_text(text: str, max_results: int) -> list[dict]:
    """从 AI 回复中解析结构化搜索结果"""
    results = []
    pattern = r'(?:\d+[\.\)]\s*)?\*\*(.+?)\*\*\s*\n\s*(?:URL|url|链接)?[：:]\s*(\S+)\s*\n\s*(?:Snippet[：:]?\s*)?(.*?)(?=\n\d+[\.\)]|\n\*\*|\Z)'
    for title, url, snippet in re.findall(pattern, text, re.DOTALL)[:max_results]:
        if url.startswith("http"):
            results.append({"title": title.strip(), "url": url.strip(), "snippet": snippet.strip()[:300]})
    return results or [{"title": "Search result", "url": "", "snippet": text[:1000]}]


# ─── 工具调用 ────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "web_search":
        query = arguments.get("query", "")
        max_results = min(arguments.get("max_results", 5), 10)

        try:
            fn = SEARCH_FUNCTIONS[BACKEND]
            raw = fn(query, max_results)
            results = raw if isinstance(raw, list) else _parse_search_text(raw, max_results)
        except Exception as e:
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
            output.append(f"{i}. **{r.get('title','N/A')}**\n   URL: {r.get('url','N/A')}\n   {r.get('snippet','')[:300]}")
        return [TextContent(type="text", text="\n\n".join(output))]

    elif name == "web_fetch":
        url = arguments.get("url", "")
        prompt = arguments.get("prompt", "Extract the main content")
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            with urllib.request.urlopen(req, timeout=15) as r:
                raw = r.read()
            ct = r.headers.get("Content-Type", "")
            enc = ct.split("charset=")[-1].split(";")[0].strip() if "charset=" in ct else "utf-8"
            html = raw.decode(enc, errors="replace")
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                for t in soup(["script","style","nav","footer","header"]): t.decompose()
                text = soup.get_text(separator="\n", strip=True)
            except ImportError:
                text = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
                text = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text).strip()
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            return [TextContent(type="text", text=f"Content from {url}:\n\n{'\n'.join(lines[:500])[:8000]}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Fetch error: {e}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    print(f"[web-search] Backend: {BACKEND_LABEL}", file=sys.stderr)
    if BACKEND == "duckduckgo":
        print("[web-search] ======================================", file=sys.stderr)
        print("[web-search]   Zero config (DuckDuckGo Free)", file=sys.stderr)
        print("[web-search] ======================================", file=sys.stderr)
        print("[web-search]", file=sys.stderr)
        print("[web-search]   🇨🇳 国内 — 注册任意一个，设一个环境变量：", file=sys.stderr)
        print("[web-search]     智谱    setx GLM_API_KEY \"xxx\"    https://open.bigmodel.cn", file=sys.stderr)
        print("[web-search]     千问    setx DASHSCOPE_API_KEY \"xxx\" https://dashscope.aliyun.com", file=sys.stderr)
        print("[web-search]     Kimi    setx MOONSHOT_API_KEY \"xxx\"  https://platform.moonshot.cn", file=sys.stderr)
        print("[web-search]     硅基流动 setx SILICONFLOW_API_KEY \"xxx\" https://siliconflow.cn", file=sys.stderr)
        print("[web-search]", file=sys.stderr)
        print("[web-search]   🌍 International — set one env var:", file=sys.stderr)
        print("[web-search]     Perplexity setx PERPLEXITY_API_KEY \"xxx\"  https://perplexity.ai", file=sys.stderr)
        print("[web-search]     Gemini     setx GEMINI_API_KEY \"xxx\"      https://aistudio.google.com", file=sys.stderr)
        print("[web-search]     Brave      setx BRAVE_API_KEY \"xxx\"       https://brave.com/search/api (free 2k/mo)", file=sys.stderr)
    asyncio.run(main())
