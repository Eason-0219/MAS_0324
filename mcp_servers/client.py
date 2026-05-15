# mcp/client.py
"""
MCP Client — 透過 HTTP 呼叫 MCP Servers

架構：
  MAS nodes.py → mcp_client.query()
                    → HTTP POST → MCP Server (time/weather/search)
                    → 降級：直接呼叫 mcp/tools.py

MCP Server 啟動方式（各自獨立 port）：
  python mcp/time_server.py    → http://localhost:8001
  python mcp/weather_server.py → http://localhost:8002
  python mcp/search_server.py  → http://localhost:8003
"""

import httpx
import asyncio
from typing import Dict, Any, Optional

# 確認 mcp 套件是否可用
try:
    import mcp
    from mcp.client.sse import sse_client
    from mcp.client.session import ClientSession
    MCP_SDK_AVAILABLE = True
except ImportError:
    MCP_SDK_AVAILABLE = False


class MASMCPClient:
    """
    MAS 系統的 MCP HTTP Client

    透過 HTTP 呼叫各 MCP Server 的工具。
    Server 未啟動時自動降級為直接呼叫 mcp/tools.py。
    """

    # MCP Server HTTP 端點 (SSE)
    SERVERS = {
        "time":    {"url": "http://localhost:8001/sse",  "tools": ["get_current_time", "get_date_info"]},
        "weather": {"url": "http://localhost:8002/sse",  "tools": ["get_weather"]},
        "search":  {"url": "http://localhost:8003/sse",  "tools": ["web_search"]},
    }

    def __init__(self):
        self._fallback_tools = None
        self._http = httpx.Client(timeout=6.0)

    def _get_fallback_tools(self):
        if self._fallback_tools is None:
            from mcp_servers.tools import MCPTools
            self._fallback_tools = MCPTools()
        return self._fallback_tools

    def _find_server(self, tool_name: str) -> Optional[str]:
        for name, cfg in self.SERVERS.items():
            if tool_name in cfg["tools"]:
                return name
        return None

    async def _async_call_tool(self, url: str, tool_name: str, args: Dict[str, Any]) -> str:
        """使用官方 SDK 透過 SSE 呼叫工具"""
        async with sse_client(url) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=args)
                if result.content:
                    return result.content[0].text
                return str(result)

    def call_tool(self, tool_name: str, args: Dict[str, Any]) -> str:
        """
        呼叫 MCP 工具。
        優先走 HTTP MCP Server，失敗時降級為本地工具。
        """
        server_name = self._find_server(tool_name)
        if server_name and MCP_SDK_AVAILABLE:
            url = self.SERVERS[server_name]["url"]
            try:
                # 在執行緒池中，可以直接使用 asyncio.run
                return asyncio.run(self._async_call_tool(url, tool_name, args))
            except Exception as e:
                print(f"   ⚠️ MCP Server '{server_name}' 不可用，降級: {e}")

        # 降級
        return self._call_fallback(tool_name, args)

    def _call_fallback(self, tool_name: str, args: Dict[str, Any]) -> str:
        """直接呼叫本地工具（MCP Server 未啟動時）"""
        tools = self._get_fallback_tools()
        if tool_name == "get_current_time":
            r = tools.get_current_time(args.get("timezone_name", "Asia/Taipei"))
        elif tool_name == "get_date_info":
            r = tools.get_date_info()
        elif tool_name == "get_weather":
            r = tools.get_weather(city=args.get("city", "Taipei"), language=args.get("language", "zh_tw"))
        elif tool_name == "web_search":
            r = tools.web_search(query=args.get("query", ""), max_results=args.get("max_results", 5))
        else:
            return f"未知工具: {tool_name}"
        return r.get("message", str(r))

    def query(self, query_type: str, **kwargs) -> Dict[str, Any]:
        """
        統一查詢介面，供 nodes.py 的 mcp_agent_node 呼叫。
        """
        tool_map = {
            "time":    ("get_current_time", {"timezone_name": kwargs.get("timezone", "Asia/Taipei")}),
            "date":    ("get_date_info",    {}),
            "weather": ("get_weather",      {"city": kwargs.get("city", "Taipei"), "language": "zh_tw"}),
            "search":  ("web_search",       {"query": kwargs.get("query", ""), "max_results": 5}),
        }
        if query_type not in tool_map:
            return {"success": False, "message": f"未知查詢類型: {query_type}"}

        tool_name, tool_args = tool_map[query_type]
        try:
            message = self.call_tool(tool_name, tool_args)
            return {"success": True, "message": message}
        except Exception as e:
            return {"success": False, "message": f"MCP 呼叫失敗: {e}"}

    def get_status(self) -> Dict[str, Any]:
        """檢查各 MCP Server 是否在線"""
        status = {}
        for name, cfg in self.SERVERS.items():
            try:
                r = self._http.get(cfg["url"].replace("/mcp", "/health"), timeout=1.0)
                status[name] = r.status_code == 200
            except Exception:
                status[name] = False
        return {"sdk_available": MCP_SDK_AVAILABLE, "servers": status}


# 全域實例
mcp_client = MASMCPClient()
