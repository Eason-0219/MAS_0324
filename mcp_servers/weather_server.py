# mcp/weather_server.py
"""
MCP Server: 天氣查詢 (HTTP 模式)
"""

import os
import time as _time
import httpx
from dotenv import load_dotenv

load_dotenv()
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("weather-service", host="0.0.0.0", port=8002)

# 台灣縣市座標（OpenWeatherMap 縣市名稱支援有限，用座標更準確）
TW_CITY_COORDS = {
    "New Taipei":  (25.0169, 121.4627),
    "Keelung":     (25.1276, 121.7392),
    "Taoyuan":     (24.9936, 121.3010),
    "Hsinchu":     (24.8138, 120.9675),
    "Miaoli":      (24.5602, 120.8214),
    "Taichung":    (24.1477, 120.6736),
    "Changhua":    (24.0752, 120.5428),
    "Nantou":      (23.9610, 120.9718),
    "Yunlin":      (23.7092, 120.4313),
    "Chiayi":      (23.4800, 120.4491),
    "Tainan":      (22.9999, 120.2269),
    "Kaohsiung":   (22.6273, 120.3014),
    "Pingtung":    (22.6761, 120.4942),
    "Yilan":       (24.7021, 121.7377),
    "Hualien":     (23.9871, 121.6015),
    "Taitung":     (22.7583, 121.1444),
    "Penghu":      (23.5711, 119.5793),
}

_weather_cache: dict = {}
_cache_ttl = 300  # 5 分鐘


@mcp.tool()
def get_weather(city: str = "Taipei", language: str = "zh_tw") -> str:
    """查詢指定城市的即時天氣。

    Args:
        city: 城市英文名稱，例如 Taipei, Tokyo, Seoul, New York
        language: 回應語言代碼，例如 zh_tw, en
    """
    api_key = os.getenv("OPENWEATHER_API_KEY", "")
    if not api_key:
        return "天氣 API 未設定，請在 .env 中設定 OPENWEATHER_API_KEY"

    cache_key = f"{city}_{language}"
    if cache_key in _weather_cache:
        ts, cached = _weather_cache[cache_key]
        if _time.time() - ts < _cache_ttl:
            return cached + " (快取)"

    try:
        with httpx.Client(timeout=5.0) as client:
            # 台灣縣市用座標查詢，其他用城市名
            if city in TW_CITY_COORDS:
                lat, lon = TW_CITY_COORDS[city]
                params = {"lat": lat, "lon": lon, "appid": api_key, "units": "metric", "lang": language}
            else:
                params = {"q": city, "appid": api_key, "units": "metric", "lang": language}

            resp = client.get("https://api.openweathermap.org/data/2.5/weather", params=params)
            resp.raise_for_status()
            data = resp.json()

        desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        feels = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        wind = data["wind"]["speed"]

        msg = f"{city} 目前天氣：{desc}，氣溫 {temp}°C（體感 {feels}°C），濕度 {humidity}%，風速 {wind} m/s"
        _weather_cache[cache_key] = (_time.time(), msg)
        return msg

    except httpx.HTTPStatusError as e:
        return f"天氣查詢失敗: HTTP {e.response.status_code}"
    except Exception as e:
        return f"天氣查詢失敗: {e}"


if __name__ == "__main__":
    mcp.run(transport="sse")
