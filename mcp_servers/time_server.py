# mcp/time_server.py
"""
MCP Server: 時間與日期查詢 (HTTP 模式)
標準 FastMCP — 以 HTTP SSE 方式運行，Client 透過 HTTP 呼叫
"""

from datetime import datetime, timezone, timedelta
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("time-service", host="0.0.0.0", port=8001)

TIMEZONE_OFFSETS = {
    "Asia/Taipei": 8, "Asia/Tokyo": 9, "Asia/Shanghai": 8,
    "Asia/Hong_Kong": 8, "Asia/Singapore": 8, "Asia/Seoul": 9,
    "Asia/Bangkok": 7, "Asia/Jakarta": 7, "Asia/Ho_Chi_Minh": 7,
    "Asia/Manila": 8, "Asia/Kolkata": 5.5, "Asia/Dubai": 4,
    "America/New_York": -5, "America/Los_Angeles": -8,
    "America/Chicago": -6, "America/Denver": -7,
    "Europe/London": 0, "Europe/Paris": 1, "Europe/Berlin": 1,
    "Europe/Moscow": 3, "Australia/Sydney": 11, "Pacific/Auckland": 13,
    "UTC": 0,
}
WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


@mcp.tool()
def get_current_time(timezone_name: str = "Asia/Taipei") -> str:
    """獲取指定時區的當前時間。

    Args:
        timezone_name: IANA 時區名稱，例如 Asia/Taipei, Asia/Tokyo, America/New_York
    """
    offset_hours = TIMEZONE_OFFSETS.get(timezone_name, 8)
    tz = timezone(timedelta(hours=offset_hours))
    now = datetime.now(tz)
    return (
        f"現在是 {now.strftime('%Y年%m月%d日')} "
        f"{WEEKDAYS[now.weekday()]} "
        f"{now.strftime('%H:%M:%S')} ({timezone_name})"
    )


@mcp.tool()
def get_date_info() -> str:
    """獲取今天的日期與星期資訊（台北時間）。"""
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    return f"今天是 {now.strftime('%Y年%m月%d日')} {WEEKDAYS[now.weekday()]}"


if __name__ == "__main__":
    # 以 HTTP 模式啟動，port 8001
    mcp.run(transport="sse")
