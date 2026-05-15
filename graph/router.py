# graph/router.py
"""
智慧混合路由器

策略：
1. Qwen 0.6B 做 Tool Calling 路由（快速，~50ms）
2. 簡單 Agent（robot, sop, safety, mcp）→ 本地處理
3. 複雜 Agent（chat, troubleshoot）→ gpt-5-mini 處理
"""

import time
from typing import Dict, Any, Optional

from config.settings import settings, TOOLS_DEFINITION

# 條件導入
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("⚠️ ollama 套件未安裝")


class HybridRouter:
    """
    智慧混合路由器
    
    - 路由：Qwen 0.6B（本地，快速）
    - 複雜任務標記：交給 GPT 處理
    """
    
    # 需要 GPT 處理的複雜 Agent
    COMPLEX_AGENTS = {"chat", "troubleshoot"}
    
    # 簡單 Agent（本地處理）
    SIMPLE_AGENTS = {"robot", "sop", "safety", "mcp"}
    
    def __init__(self):
        self.router_model = settings.ollama_router_model
        
        # 路由系統提示（給 Qwen）
        self.system_prompt = """你是意圖分類器。根據用戶輸入選擇最適合的工具。

可用工具：
1. control_robot - 控制機械手臂（伸出、收回、夾取、放置、調整速度）
2. query_sop - 查詢組裝步驟流程
3. query_safety_guidelines - 查詢安全須知、開工前注意事項、當使用者說出："我要進產線了"，強制路由至此
4. troubleshoot - 處理作業問題（螺絲掉落、工具掉落、忘記流程、異常狀況）
5. mcp_query - 查詢時間、日期、天氣、上網搜尋

判斷規則：
- 機械手臂相關（伸出、收回、夾、放、速度）→ control_robot
- 詢問步驟、流程、怎麼做 → query_sop
- 安全、注意事項、進產線 → query_safety_guidelines
- 問題、故障、掉了、怎麼辦、異常 → troubleshoot
- 時間、日期、天氣、搜尋、上網、查詢資訊、最新消息 → mcp_query
- 打招呼、閒聊、自我介紹、其他 → 不使用工具，直接回答"""
    
    # === 城市名中英對照表（MCP 天氣規則用）===
    CITY_MAP = {
        # 台灣
        "台北": "Taipei", "台中": "Taichung", "高雄": "Kaohsiung",
        "台南": "Tainan", "新竹": "Hsinchu", "桃園": "Taoyuan",
        "新北": "New Taipei", "基隆": "Keelung", "嘉義": "Chiayi",
        "彰化": "Changhua", "南投": "Nantou", "雲林": "Yunlin",
        "屏東": "Pingtung", "宜蘭": "Yilan", "花蓮": "Hualien",
        "台東": "Taitung", "澎湖": "Penghu", "苗栗": "Miaoli",
        # 日本
        "東京": "Tokyo", "大阪": "Osaka", "京都": "Kyoto",
        "札幌": "Sapporo", "福岡": "Fukuoka", "名古屋": "Nagoya",
        # 韓國
        "首爾": "Seoul", "釜山": "Busan",
        # 中國
        "北京": "Beijing", "上海": "Shanghai", "深圳": "Shenzhen",
        "廣州": "Guangzhou", "香港": "Hong Kong",
        # 東南亞
        "新加坡": "Singapore", "曼谷": "Bangkok", "河內": "Hanoi",
        "胡志明": "Ho Chi Minh City", "雅加達": "Jakarta",
        # 美國
        "紐約": "New York", "洛杉磯": "Los Angeles", "舊金山": "San Francisco",
        # 歐洲
        "倫敦": "London", "巴黎": "Paris", "柏林": "Berlin",
        # 大洋洲
        "雪梨": "Sydney", "墨爾本": "Melbourne",
    }

    # === 地點時區對照表（MCP 時間規則用）===
    TIMEZONE_MAP = {
        # 台灣
        "台灣": "Asia/Taipei", "台北": "Asia/Taipei", "台中": "Asia/Taipei",
        "高雄": "Asia/Taipei", "台南": "Asia/Taipei",
        # 日本
        "日本": "Asia/Tokyo", "東京": "Asia/Tokyo", "大阪": "Asia/Tokyo",
        "京都": "Asia/Tokyo", "札幌": "Asia/Tokyo", "福岡": "Asia/Tokyo",
        # 韓國
        "韓國": "Asia/Seoul", "首爾": "Asia/Seoul", "釜山": "Asia/Seoul",
        # 中國
        "中國": "Asia/Shanghai", "北京": "Asia/Shanghai", "上海": "Asia/Shanghai",
        "深圳": "Asia/Shanghai", "廣州": "Asia/Shanghai",
        # 香港
        "香港": "Asia/Hong_Kong",
        # 東南亞
        "新加坡": "Asia/Singapore",
        "泰國": "Asia/Bangkok", "曼谷": "Asia/Bangkok",
        "越南": "Asia/Ho_Chi_Minh", "河內": "Asia/Ho_Chi_Minh", "胡志明": "Asia/Ho_Chi_Minh",
        "印尼": "Asia/Jakarta", "雅加達": "Asia/Jakarta",
        "峇厘島": "Asia/Makassar", "峇里島": "Asia/Makassar", "巴厘島": "Asia/Makassar",
        "馬來西亞": "Asia/Kuala_Lumpur", "吉隆坡": "Asia/Kuala_Lumpur",
        "菲律賓": "Asia/Manila", "馬尼拉": "Asia/Manila",
        "緬甸": "Asia/Rangoon", "仰光": "Asia/Rangoon",
        "柬埔寨": "Asia/Phnom_Penh", "金邊": "Asia/Phnom_Penh",
        # 南亞
        "印度": "Asia/Kolkata", "孟買": "Asia/Kolkata", "新德里": "Asia/Kolkata",
        # 中東
        "杜拜": "Asia/Dubai", "阿布達比": "Asia/Dubai",
        # 歐洲
        "英國": "Europe/London", "倫敦": "Europe/London",
        "法國": "Europe/Paris", "巴黎": "Europe/Paris",
        "德國": "Europe/Berlin", "柏林": "Europe/Berlin",
        "義大利": "Europe/Rome", "羅馬": "Europe/Rome",
        "西班牙": "Europe/Madrid", "馬德里": "Europe/Madrid",
        # 美國
        "紐約": "America/New_York", "波士頓": "America/New_York",
        "洛杉磯": "America/Los_Angeles", "舊金山": "America/Los_Angeles",
        "芝加哥": "America/Chicago", "休士頓": "America/Chicago",
        "拉斯維加斯": "America/Los_Angeles",
        # 大洋洲
        "澳洲": "Australia/Sydney", "雪梨": "Australia/Sydney", "墨爾本": "Australia/Melbourne",
        "紐西蘭": "Pacific/Auckland", "奧克蘭": "Pacific/Auckland",
    }

    def _rule_based_check(self, user_input: str) -> Dict[str, Any]:
        """
        規則攔截器：針對明確指令直接返回結果，跳過 LLM
        覆蓋場景：機械手臂控制、SOP 查詢、安全須知、MCP 查詢
        """
        import re
        text = user_input.lower().replace(" ", "")
        
        # === 1. 機械手臂 - 速度控制（擴充口語表達）===
        # 調慢：「慢速」「太快」「太快了」「速度慢一點」「放慢」
        if ("慢" in text or "太快" in text or "放慢" in text) and \
           ("速" in text or "動" in text or "運" in text or "行" in text or "放" in text or "手臂" in text or "機械" in text):
            return {
                "route": "robot", "tool_name": "control_robot",
                "tool_args": {"action": "adjust_speed", "speed": "slow"},
                "method": "rule", "needs_gpt": False, "confidence": 1.0
            }
        # 調快：「快速」「太慢」「加快」「快一點」「提速」「全速」
        if ("快" in text or "全速" in text or "太慢" in text or "加快" in text or "提速" in text or "快一點" in text) and \
           ("速" in text or "加" in text or "動" in text or "運" in text or "行" in text or "手臂" in text or "機械" in text):
            return {
                "route": "robot", "tool_name": "control_robot",
                "tool_args": {"action": "adjust_speed", "speed": "fast"},
                "method": "rule", "needs_gpt": False, "confidence": 1.0
            }
        # 中速：「原速」「中速」「正常速度」「恢復速度」
        if ("原速" in text or "中速" in text or "正常" in text or "恢復" in text) and \
           ("速" in text or "動" in text or "運" in text or "手臂" in text or "機械" in text):
            return {
                "route": "robot", "tool_name": "control_robot",
                "tool_args": {"action": "adjust_speed", "speed": "medium"},
                "method": "rule", "needs_gpt": False, "confidence": 1.0
            }

        # === 2. 機械手臂 - 動作控制（擴充）===
        if "伸出" in text or "申出" in text or "展開" in text:
            return {
                "route": "robot", "tool_name": "control_robot",
                "tool_args": {"action": "extend"},
                "method": "rule", "needs_gpt": False, "confidence": 1.0
            }
        if "收回" in text or "縮回" in text or "收起" in text:
            return {
                "route": "robot", "tool_name": "control_robot",
                "tool_args": {"action": "retract"},
                "method": "rule", "needs_gpt": False, "confidence": 1.0
            }
        if "夾取" in text or "抓取" in text or "夾住" in text:
            return {
                "route": "robot", "tool_name": "control_robot",
                "tool_args": {"action": "grip"},
                "method": "rule", "needs_gpt": False, "confidence": 1.0
            }
        if "放置" in text and ("風" in text or "扇" in text):
            return {
                "route": "robot", "tool_name": "control_robot",
                "tool_args": {"action": "release"},
                "method": "rule", "needs_gpt": False, "confidence": 1.0
            }
        
        # === 3. Safety - 進產線與身份更新 ===
        if "身高" in text and re.search(r'\d+', text):
             return {
                "route": "safety", "tool_name": "query_safety_guidelines",
                "tool_args": {"category": "update_profile"},
                "method": "rule", "needs_gpt": False, "confidence": 1.0
            }
        if "進產線" in text or "进产线" in text:
            return {
                "route": "safety", "tool_name": "query_safety_guidelines",
                "tool_args": {"category": "pre_work"},
                "method": "rule", "needs_gpt": False, "confidence": 1.0
            }
        
        # === 4. SOP 查詢規則 ===
        # 「下一步」「上一步」「步驟」「流程」「SOP」
        if any(kw in text for kw in ["下一步", "上一步", "步驟", "流程", "sop", "組裝"]):
            return {
                "route": "sop", "tool_name": "query_sop",
                "tool_args": {"query_type": "all_steps"},
                "method": "rule", "needs_gpt": False, "confidence": 1.0
            }
        # 「第N步」— 正則匹配
        step_match = re.search(r'第([一二三四五六七八九十\d]+)步', text)
        if step_match:
            step_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
                        "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
            raw = step_match.group(1)
            step_num = step_map.get(raw, None)
            if step_num is None:
                try:
                    step_num = int(raw)
                except ValueError:
                    step_num = 1
            return {
                "route": "sop", "tool_name": "query_sop",
                "tool_args": {"query_type": "single_step", "step_number": step_num},
                "method": "rule", "needs_gpt": False, "confidence": 1.0
            }

        # === 5. MCP - 時間/日期/天氣/搜尋規則 ===
        # 時間查詢
        if any(kw in text for kw in ["幾點", "時間", "whattime", "幾時", "現在時間"]):
            return {
                "route": "mcp", "tool_name": "mcp_query",
                "tool_args": {"query_type": "time", "timezone": "Asia/Taipei"},
                "method": "rule", "needs_gpt": False, "confidence": 1.0
            }
        # 日期查詢
        if any(kw in text for kw in ["幾號", "星期幾", "日期", "whatday", "今天幾號"]):
            return {
                "route": "mcp", "tool_name": "mcp_query",
                "tool_args": {"query_type": "date"},
                "method": "rule", "needs_gpt": False, "confidence": 1.0
            }
        # 天氣查詢（含城市名解析）
        if any(kw in text for kw in ["天氣", "氣溫", "weather", "下雨", "溫度"]):
            city = "Taipei"  # 預設台北
            for cn_name, en_name in self.CITY_MAP.items():
                if cn_name in user_input:
                    city = en_name
                    break
            return {
                "route": "mcp", "tool_name": "mcp_query",
                "tool_args": {"query_type": "weather", "city": city},
                "method": "rule", "needs_gpt": False, "confidence": 1.0
            }
        # 搜尋查詢
        if any(kw in text for kw in ["搜尋", "搜索", "查詢", "search", "幫我查", "幫我找", "上網查", "上網搜", "網路查", "查一下", "最新消息", "最新資訊"]):
            # 提取搜尋關鍵字
            query = user_input
            for kw in ["搜尋", "搜索", "查詢", "search", "幫我查", "幫我找", "幫我", "上網查", "上網搜", "網路查", "查一下", "最新消息", "最新資訊", "上網"]:
                query = query.replace(kw, "")
            query = query.strip()
            if not query:
                query = user_input
            return {
                "route": "mcp", "tool_name": "mcp_query",
                "tool_args": {"query_type": "search", "query": query},
                "method": "rule", "needs_gpt": False, "confidence": 1.0
            }
        # 「今天」單獨出現（可能問日期）
        if text == "今天":
            return {
                "route": "mcp", "tool_name": "mcp_query",
                "tool_args": {"query_type": "date"},
                "method": "rule", "needs_gpt": False, "confidence": 1.0
            }
        
        
    def route(self, user_input: str, debug: bool = False) -> Dict[str, Any]:
        """
        混合路由：規則 -> Qwen -> Fallback
        
        
        Returns:
            {
                "route": str,           # 路由目標
                "method": str,          # "qwen-0.6b"
                "needs_gpt": bool,      # 是否需要 GPT 處理
                "tool_name": str,       # 工具名稱
                "tool_args": dict,      # 工具參數
                "latency_ms": float,    # 路由延遲
            }
        """
        start_time = time.perf_counter()
        
        # 1. 先跑規則檢查 (最快、最準)
        rule_result = self._rule_based_check(user_input)
        if rule_result:
            rule_result["latency_ms"] = (time.perf_counter() - start_time) * 1000
            if debug:
                print(f"   ⚡ 規則命中: {rule_result['route']} (Action: {rule_result['tool_args']})")
            return rule_result

        # 2. 規則沒中，才跑 Qwen LLM
        if not OLLAMA_AVAILABLE:
            return self._fallback_route(user_input, start_time)
        
        try:
            response = ollama.chat(
                model=self.router_model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_input}
                ],
                tools=TOOLS_DEFINITION,
                options={"temperature": 0}
            )
            
            latency = (time.perf_counter() - start_time) * 1000
            
            if debug:
                print(f"   🔀 Qwen 路由完成 ({latency:.0f}ms)")
            
            if response.message.tool_calls:
                tool_call = response.message.tool_calls[0]
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments or {}
                route = self._tool_to_route(tool_name)
                
                return {
                    "route": route,
                    "method": "qwen-0.6b",
                    "needs_gpt": route in self.COMPLEX_AGENTS,
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "latency_ms": latency,
                    "confidence": 0.9,
                }
            else:
                return {
                    "route": "chat",
                    "method": "qwen-0.6b",
                    "needs_gpt": True,
                    "tool_name": None,
                    "tool_args": {},
                    "latency_ms": latency,
                    "confidence": 0.8,
                }
                
        except Exception as e:
            print(f"   ⚠️ Qwen 路由錯誤: {e}")
            return self._fallback_route(user_input, start_time)
    
    def _fallback_route(self, user_input: str, start_time: float) -> Dict[str, Any]:
        """備援路由（Ollama 不可用時）"""
        latency = (time.perf_counter() - start_time) * 1000
        return {
            "route": "chat",
            "method": "fallback",
            "needs_gpt": True,
            "tool_name": None,
            "tool_args": {},
            "latency_ms": latency,
            "confidence": 0.5,
        }
    
    def _tool_to_route(self, tool_name: str) -> str:
        """工具名稱 → 路由"""
        mapping = {
            "control_robot": "robot",
            "query_sop": "sop",
            "query_safety_guidelines": "safety",
            "troubleshoot": "troubleshoot",
            "mcp_query": "mcp",
        }
        return mapping.get(tool_name, "chat")


# 全域路由器
hybrid_router = HybridRouter()
