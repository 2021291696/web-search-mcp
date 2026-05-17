# web-search-mcp — 多后端联网搜索 MCP

专为 **Claude Code + DeepSeek** 等无内置联网功能的 API 用户设计。免费零配置可用，按需升级更高质量后端。

## 后端选择

| 后端 | 需要 | 费用 | 质量 | 适用 |
|------|------|------|------|------|
| **DuckDuckGo** | 无 | 免费 | ⭐⭐ | 全球（国内需梯子） |
| **SearXNG** | `SEARXNG_URL` | 免费 | ⭐⭐⭐ | **国内用户首选**，自部署 |
| **Brave Search** | `BRAVE_API_KEY` | 2000次/月免费 | ⭐⭐⭐⭐ | 国际用户高质量 |
| **Perplexity** | `PERPLEXITY_API_KEY` | 付费 | ⭐⭐⭐⭐⭐ | AI 驱动搜索+总结 |

**自动检测**：启动时按 `Perplexity → Brave → SearXNG → DuckDuckGo` 优先级自动选择。设了哪个环境变量就用哪个，都没设就用 DuckDuckGo。

## 安装

### 全局用户（推荐）

```powershell
# 1. 克隆
git clone https://github.com/2021291696/web-search-mcp.git
cd web-search-mcp

# 2. 安装依赖
pip install -r requirements.txt

# 3. 测试
python server.py
# 应该看到: [web-search] Backend: DuckDuckGo (Free)
```

### 配置 CC 的 MCP 入口

在项目或全局 `.mcp.json` 中添加：

```json
{
  "mcpServers": {
    "web-search": {
      "type": "stdio",
      "command": "python",
      "args": ["D:/path/to/web-search-mcp/server.py"]
    }
  }
}
```

## 地区专属指南

### 🇨🇳 国内用户

DuckDuckGo 国内需梯子。推荐两种方案：

**方案 A：自部署 SearXNG（免费，无需梯子）**

```bash
# 在你的国内服务器/VPS 上部署 SearXNG（Docker 一键）
docker run -d -p 8080:8080 searxng/searxng

# 本地设环境变量
setx SEARXNG_URL "http://你的服务器IP:8080"
```

**方案 B：保持 DDG + 梯子**

确保 CC 启动时梯子已开，DDG 后端即可正常使用。

### 🌍 国际用户

推荐升级到 Brave Search（质量更高）：

```bash
# 1. 注册免费 API Key: https://brave.com/search/api/
# 2. 设置环境变量
setx BRAVE_API_KEY "your-key-here"
# 重启终端后生效
```

## 工具

### web_search
参数：`query`（必填）、`max_results`（可选，默认 5，最大 10）

### web_fetch
参数：`url`（必填）、`prompt`（可选）

## 故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| `duckduckgo_search not installed` | 依赖缺失 | `pip install duckduckgo-search` |
| DDG 返回空 | 国内网络不通 | 开梯子 或 部署 SearXNG |
| `BRAVE_API_KEY not set` | 环境变量未设 | `setx BRAVE_API_KEY "xxx"` 后重启终端 |
| 搜索无结果 | DDG 限流 | 等几分钟 或 升级到其他后端 |

## License

MIT
