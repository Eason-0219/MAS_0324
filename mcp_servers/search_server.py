# mcp/search_server.py
"""
MCP Server: 網路搜尋 (HTTP 模式)
"""

import os
from dotenv import load_dotenv

load_dotenv()
import re
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("search-service", host="0.0.0.0", port=8003)


@mcp.tool()
def web_search(query: str, max_results: int = 5) -> str:
    """搜尋網路上的最新資訊。

    Args:
        query: 搜尋關鍵字
        max_results: 最大結果數量（預設 5）
    """
    tavily_key = os.getenv("TAVILY_API_KEY", "")
    if tavily_key.startswith("tvly-"):
        return _search_tavily(query, tavily_key, max_results)
    return _search_duckduckgo(query, max_results)


def _search_tavily(query: str, api_key: str, max_results: int) -> str:
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(
                "https://api.tavily.com/search",
                json={"api_key": api_key, "query": query,
                      "search_depth": "basic", "include_answer": True,
                      "max_results": max_results}
            )
            resp.raise_for_status()
            data = resp.json()

        parts = [f"🔍 搜尋「{query}」的結果："]
        if data.get("answer"):
            parts.append(f"\n📝 摘要：{data['answer'][:300]}")
        for r in data.get("results", [])[:3]:
            parts.append(f"• {r.get('title', '')}")
        return "\n".join(parts) if len(parts) > 1 else f"找不到「{query}」的結果"

    except Exception as e:
        return _search_duckduckgo(query, max_results)


def _search_duckduckgo(query: str, max_results: int) -> str:
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                headers={"User-Agent": "Mozilla/5.0"}
            )
            resp.raise_for_status()

        results = []
        for _, title in re.findall(
            r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>',
            resp.text
        )[:max_results]:
            if title.strip():
                results.append(title.strip())

        if results:
            return f"🔍 搜尋「{query}」：\n" + "\n".join(f"• {r}" for r in results[:5])
        return f"找不到「{query}」的結果"

    except Exception as e:
        return f"搜尋失敗: {e}"


if __name__ == "__main__":
    mcp.run(transport="sse")
