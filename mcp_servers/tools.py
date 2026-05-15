# mcp/tools.py
"""
MCP (Model Context Protocol) 工具模組

提供外部資訊查詢功能：
- 時間查詢
- 天氣查詢
- 網路搜尋
"""

import time as _time
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

try:
    from zoneinfo import ZoneInfo
    ZONEINFO_AVAILABLE = True
except ImportError:
    ZONEINFO_AVAILABLE = False

from config.settings import settings


class MCPTools:
    """
    MCP 工具集合
    
    為 LLM 提供外部資訊存取能力
    """
    
    # 時區偏移量對照表
    TIMEZONE_OFFSETS = {
        # 亞洲
        "Asia/Taipei": 8,
        "Asia/Tokyo": 9,
        "Asia/Shanghai": 8,
        "Asia/Hong_Kong": 8,
        "Asia/Singapore": 8,
        "Asia/Seoul": 9,
        "Asia/Bangkok": 7,
        "Asia/Jakarta": 7,
        "Asia/Ho_Chi_Minh": 7,
        "Asia/Manila": 8,
        "Asia/Kolkata": 5.5,
        "Asia/Dubai": 4,
        # 美洲
        "America/New_York": -5,
        "America/Los_Angeles": -8,
        "America/Chicago": -6,
        "America/Denver": -7,
        "America/Sao_Paulo": -3,
        # 歐洲
        "Europe/London": 0,
        "Europe/Paris": 1,
        "Europe/Berlin": 1,
        "Europe/Moscow": 3,
        # 大洋洲
        "Australia/Sydney": 11,
        "Pacific/Auckland": 13,
        # 其他
        "UTC": 0,
    }
    
    def __init__(self):
        self.weather_api_key = settings.openweather_api_key
        self.http_client = httpx.Client(timeout=5.0)  # 從 10s 降到 5s
        # 天氣快取：{city: (timestamp, result)}
        self._weather_cache: Dict[str, tuple] = {}
        self._cache_ttl = 300  # 5 分鐘
        
    # ============================================================
    # 時間查詢
    # ============================================================
    
    def get_current_time(self, tz_name: str = "Asia/Taipei") -> Dict[str, Any]:
        """獲取當前時間，支援完整 IANA 時區"""
        try:
            if ZONEINFO_AVAILABLE:
                tz = ZoneInfo(tz_name)
                now = datetime.now(tz)
            else:
                # fallback: 用 offset 表
                offset_hours = self.TIMEZONE_OFFSETS.get(tz_name, 8)
                tz = timezone(timedelta(hours=offset_hours))
                now = datetime.now(tz)

            weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

            return {
                "success": True,
                "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
                "date": now.strftime("%Y年%m月%d日"),
                "time": now.strftime("%H:%M:%S"),
                "weekday": weekdays[now.weekday()],
                "timezone": tz_name,
                "message": f"現在是 {now.strftime('%Y年%m月%d日')} {weekdays[now.weekday()]} {now.strftime('%H:%M:%S')} ({tz_name})"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"無法取得時間: {e}"
            }
    
    def get_date_info(self) -> Dict[str, Any]:
        """獲取日期資訊"""
        result = self.get_current_time()
        if result["success"]:
            return {
                "success": True,
                "message": f"今天是 {result['date']} {result['weekday']}"
            }
        return result
    
    # ============================================================
    # 天氣查詢
    # ============================================================
    
    def get_weather(
        self, 
        city: str = "Taipei",
        language: str = "zh_tw"
    ) -> Dict[str, Any]:
        """
        獲取天氣資訊
        
        Args:
            city: 城市名稱
            language: 語言 (zh_tw, en, vi, id)
        
        Returns:
            天氣資訊
        """
        if not self.weather_api_key or self.weather_api_key == "your-openweather-api-key":
            return {
                "success": False,
                "message": "天氣 API 未設定，無法查詢天氣。請在 .env 中設定 OPENWEATHER_API_KEY"
            }
        
        # 快取命中檢查
        cache_key = f"{city}_{language}"
        if cache_key in self._weather_cache:
            ts, cached_result = self._weather_cache[cache_key]
            if _time.time() - ts < self._cache_ttl:
                cached_result["cached"] = True
                return cached_result
        
        try:
            # OpenWeatherMap API
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                "q": city,
                "appid": self.weather_api_key,
                "units": "metric",  # 攝氏溫度
                "lang": language
            }
            
            response = self.http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # 解析資料
            weather_desc = data["weather"][0]["description"]
            temp = data["main"]["temp"]
            feels_like = data["main"]["feels_like"]
            humidity = data["main"]["humidity"]
            wind_speed = data["wind"]["speed"]
            
            result = {
                "success": True,
                "city": city,
                "weather": weather_desc,
                "temperature": temp,
                "feels_like": feels_like,
                "humidity": humidity,
                "wind_speed": wind_speed,
                "message": f"{city} 目前天氣：{weather_desc}，氣溫 {temp}°C（體感 {feels_like}°C），濕度 {humidity}%，風速 {wind_speed} m/s"
            }
            # 寫入快取
            self._weather_cache[cache_key] = (_time.time(), result)
            return result
            
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "message": f"天氣查詢失敗: HTTP {e.response.status_code}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"天氣查詢失敗: {e}"
            }
    
    # ============================================================
    # 網路搜尋 (使用 Tavily)
    # ============================================================
    
    def web_search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """
        網路搜尋（優先 Tavily，備援 DuckDuckGo）
        """
        if settings.tavily_api_key and settings.tavily_api_key.startswith("tvly-"):
            return self._search_tavily(query, max_results)
        
        return self._search_duckduckgo(query, max_results)
    
    def _search_tavily(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Tavily AI 搜尋"""
        try:
            url = "https://api.tavily.com/search"
            payload = {
                "api_key": settings.tavily_api_key,
                "query": query,
                "search_depth": "advanced",
                "include_answer": True,
                "include_raw_content": False,
                "max_results": max_results
            }
            
            response = self.http_client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            results = []
            
            # Tavily 的 AI 答案
            ai_answer = data.get("answer", "")
            
            # 搜尋結果（含摘要）
            for item in data.get("results", [])[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("content", ""),
                    "url": item.get("url", "")
                })
            
            if ai_answer or results:
                # 組合回應
                message_parts = [f"🔍 搜尋「{query}」的結果："]
                
                if ai_answer:
                    message_parts.append(f"\n📝 摘要：\n{ai_answer}")
                
                if results:
                    message_parts.append("\n📰 相關資料：")
                    for i, r in enumerate(results[:5], 1):
                        message_parts.append(f"\n{i}. 📌 {r['title']}")
                        if r.get('snippet'):
                            message_parts.append(f"   {r['snippet']}")
                        if r.get('url'):
                            message_parts.append(f"   🔗 {r['url']}")
                
                return {
                    "success": True,
                    "query": query,
                    "answer": ai_answer,
                    "results": results,
                    "source": "Tavily",
                    "message": "\n".join(message_parts)
                }
            else:
                return {
                    "success": True,
                    "query": query,
                    "results": [],
                    "message": f"找不到關於「{query}」的結果"
                }
                
        except Exception as e:
            print(f"⚠️ Tavily 搜尋失敗: {e}")
            return self._search_duckduckgo(query, max_results)
    
    def _search_duckduckgo(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """DuckDuckGo 搜尋 (備援)"""
        try:
            url = "https://html.duckduckgo.com/html/"
            headers = {"User-Agent": "Mozilla/5.0"}
            
            response = self.http_client.post(url, data={"q": query}, headers=headers)
            response.raise_for_status()
            
            import re
            results = []
            pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>'
            
            for url, title in re.findall(pattern, response.text)[:max_results]:
                if title.strip():
                    results.append({"title": title.strip(), "url": url})
            
            if results:
                summary = "\n".join([f"• {r['title']}" for r in results[:5]])
                return {
                    "success": True,
                    "query": query,
                    "results": results,
                    "message": f"🔍 搜尋「{query}」：\n{summary}"
                }
            
            return {"success": True, "query": query, "results": [], "message": f"找不到「{query}」的結果"}
            
        except Exception as e:
            return {"success": False, "message": f"搜尋失敗: {e}"}
    
    # ============================================================
    # 統一查詢介面
    # ============================================================
    
    def query(self, query_type: str, **kwargs) -> Dict[str, Any]:
        """
        統一查詢介面
        
        Args:
            query_type: 查詢類型 (time, date, weather, search)
            **kwargs: 查詢參數
        
        Returns:
            查詢結果
        """
        if query_type == "time":
            return self.get_current_time(kwargs.get("timezone", "Asia/Taipei"))
        
        elif query_type == "date":
            return self.get_date_info()
        
        elif query_type == "weather":
            return self.get_weather(
                city=kwargs.get("city", "Taipei"),
                language=kwargs.get("language", "zh_tw")
            )
        
        elif query_type == "search":
            return self.web_search(
                query=kwargs.get("query", ""),
                max_results=kwargs.get("max_results", 5)
            )
        
        else:
            return {
                "success": False,
                "message": f"未知的查詢類型: {query_type}"
            }
    
    def close(self):
        """關閉 HTTP 客戶端"""
        self.http_client.close()


# 全域 MCP 工具實例
mcp_tools = MCPTools()
