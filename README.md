# web-search-mcp — AI 驱动联网搜索

专为 **Claude Code + DeepSeek** 等无联网功能的 API 设计。**只设一个环境变量就能用**，AI 自己去搜索。

## 后端（任选一个）

| 后端 | 设什么 | 费用 | 适合 |
|------|--------|------|------|
| **智谱 GLM** | `GLM_API_KEY` | 按量付费，便宜 | 🇨🇳 国内首选 |
| **Perplexity** | `PERPLEXITY_API_KEY` | 付费，有试用 | 🌍 国际首选 |
| **OpenRouter** | `OPENROUTER_API_KEY` | 按量付费 | 🔀 想用 Gemini/Claude 等 |
| **DuckDuckGo** | 无 | 免费 | 🆓 零配置兜底 |

## 安装

```powershell
# 1. 克隆
git clone https://github.com/2021291696/web-search-mcp.git
cd web-search-mcp

# 2. 安装依赖
pip install -r requirements.txt
```

## 配置

### 🇨🇳 国内用户 → 智谱 GLM（推荐）

```powershell
# 1. 注册获取 Key: https://open.bigmodel.cn/
# 2. 设置环境变量
setx GLM_API_KEY "your-key-here"
# 3. 重启终端
```

智谱 GLM-4-Flash 自带联网搜索，OPENAI 兼容接口，开箱即用。

### 🌍 国际用户 → Perplexity

```powershell
# 1. https://www.perplexity.ai/ → API → 获取 Key
setx PERPLEXITY_API_KEY "your-key"
```

Perplexity Sonar 专注 AI 搜索，结果质量高。

### 🔀 想自由选模型 → OpenRouter

```powershell
setx OPENROUTER_API_KEY "your-key"
:: 默认用 Gemini 2.5 Flash（有联网能力）
:: 可以自定义：setx OPENROUTER_MODEL "anthropic/claude-sonnet-4.6"
```

OpenRouter 聚合了 Gemini、Claude、GPT 等，可以按需选模型。

### 🆓 都不设 → DuckDuckGo 免费兜底

不设任何 Key 也能用，启动时会提示升级选项。

## 配置 CC 的 MCP 入口

在 `.mcp.json` 中添加：

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

## 工具

- `web_search` — 搜索网页
- `web_fetch` — 抓取网页内容

## 故障排查

| 问题 | 解决 |
|------|------|
| GLM 搜不出来 | 确认用的 model 支持 web_search，设为 `glm-4-flash` |
| 智谱 Key 在哪 | https://open.bigmodel.cn/ → API Keys |
| OpenRouter 联网 | 需模型本身支持联网，Gemini/Claude 可以 |
| 什么都不想配 | 用 DuckDuckGo，零配置 |

## License

MIT
