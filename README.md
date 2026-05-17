# web-search-mcp — AI 驱动联网搜索

专为 **Claude Code + DeepSeek** 等无联网功能的 API 设计。**设一个环境变量即用**。

## 快速开始

```powershell
git clone https://github.com/2021291696/web-search-mcp.git
cd web-search-mcp
pip install -r requirements.txt
```

## 选一个后端（设一个环境变量即可）

### 🇨🇳 国内

| 后端 | 环境变量 | 注册地址 |
|------|----------|----------|
| **智谱 GLM** | `GLM_API_KEY` | [open.bigmodel.cn](https://open.bigmodel.cn) |
| **通义千问** | `DASHSCOPE_API_KEY` | [dashscope.aliyun.com](https://dashscope.aliyun.com) |
| **Kimi** | `MOONSHOT_API_KEY` | [platform.moonshot.cn](https://platform.moonshot.cn) |
| **硅基流动**（模型超市） | `SILICONFLOW_API_KEY` | [siliconflow.cn](https://siliconflow.cn) |
| **DeepSeek 平台** | `DEEPSEEK_API_KEY` | [platform.deepseek.com](https://platform.deepseek.com) |

### 🌍 国际

| 后端 | 环境变量 | 说明 |
|------|----------|------|
| **Perplexity** | `PERPLEXITY_API_KEY` | AI 原生搜索，质量最高 |
| **Gemini** | `GEMINI_API_KEY` | Google 搜索原生集成，质量最高，有免费额度 |
| **Brave** | `BRAVE_API_KEY` | 传统搜索 API，免费 2000次/月 |
| **OpenRouter** | `OPENROUTER_API_KEY` | 模型超市，可按需切换 |

### 🆓 兜底

什么都不设 → **DuckDuckGo**，免费，零配置。

## 配置 CC

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

## 工作原理

设了哪个 Key 就用哪个后端。多个 Key 都设了按优先级（国内优先，质量高的优先）。AI 自己调搜索引擎、读网页、返回结构化结果。用户只负责注册拿 Key。

## License

MIT
