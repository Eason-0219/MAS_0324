# graph/nodes.py
"""
LangGraph 節點定義 - RAG 邏輯復刻版
邏輯來源：MAS終版_UI後端模擬.py
架構適配：新版模組化架構
"""

import time
import json
from typing import Dict, Any, List, Optional

from config.settings import settings
from graph.state import MASState
from graph.router import hybrid_router
from tools.robot_control import robot_controller
from tools.sop_query_rag import sop_query_tool
from tools.safety_query_rag import safety_query_tool
from tools.troubleshoot_rag import troubleshoot_tool
from mcp_servers.tools import mcp_tools
from mcp_servers.client import mcp_client  # MCP 標準協議 Client
from utils.language import language_processor
from memory.graphiti_service import memory_service
from rag.vector_retriever import vector_retriever  # 直接引用檢索器以復刻舊版混合檢索邏輯

# 條件導入
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


class GraphNodes:
    """LangGraph 節點集合"""
    
    def __init__(self):
        # GPT 客戶端（用於複雜任務）
        self.gpt_client = None
        if OPENAI_AVAILABLE and settings.openai_api_key:
            self.gpt_client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url
            )
    
    # ============================================================
    # 輔助方法 (適配舊版邏輯)
    # ============================================================

    def _format_history(self, history: List[Dict[str, str]], max_turns: int = 5) -> str:
        """將對話歷史格式化為舊版 Prompt 需要的字串格式"""
        if not history:
            return "N/A"
        formatted = []
        # 取最後 N 輪
        recent = history[-max_turns:]
        for h in recent:
            user_text = h.get('user', '')
            assistant_text = h.get('assistant', '')
            formatted.append(f"User: {user_text}")
            formatted.append(f"Agent: {assistant_text}")
        return "\n".join(formatted)

    def _get_lang_hint(self, lang_code: str) -> str:
        """舊版 Prompt 需要的語言提示"""
        if lang_code.startswith("zh"):
            return "Traditional Chinese"
        elif lang_code.startswith("en"):
            return "English"
        elif lang_code.startswith("vi"):
            return "Vietnamese"
        elif lang_code.startswith("id"):
            return "Indonesian"
        return "Traditional Chinese" # 預設

    def _detect_redirect(self, response: str) -> Optional[str]:
        """
        偵測 Agent 回應中的二次路由標記。

        SOP Agent 可能說：「Please route to safety agent」
        Safety Agent 可能說：「Please route to SOP agent」

        Returns:
            路由目標字串（"sop" / "safety" / "troubleshoot"），或 None
        """
        lower = response.lower()
        if "route to safety" in lower or "route to the safety" in lower:
            return "safety"
        if "route to sop" in lower or "route to the sop" in lower:
            return "sop"
        if "route to troubleshoot" in lower or "route to the troubleshoot" in lower:
            return "troubleshoot"
        return None

    # ============================================================
    # 路由節點
    # ============================================================
    
    def hybrid_router_node(self, state: MASState) -> MASState:
        """Qwen 0.6B 路由節點 (增加狀態優先權檢查)"""
        user_input = state["user_input"]
        
        # 0. 狀態優先檢查：如果 Checklist 進行中 或 等待姓名身高，強制路由給 Safety Agent
        checklist_active = state.get("checklist_active", False)
        awaiting_name = state.get("awaiting_name_height", False)
        
        if checklist_active or awaiting_name:
            print(f"🔒 狀態鎖定 (Checklist: {checklist_active}, AwaitingName: {awaiting_name}) -> Safety Agent")
            state["route_decision"] = "safety"
            state["tool_name"] = "query_safety_guidelines"
            state["tool_args"] = {}
            state["model_used"] = "state_lock"
            return state

        # 1. 偵測語言
        detected_lang, _ = language_processor.detect_language(user_input)
        state["detected_language"] = detected_lang
        
        # 2. Qwen/規則 路由
        route_result = hybrid_router.route(user_input, debug=True)
        
        state["route_decision"] = route_result["route"]
        state["needs_gpt"] = route_result.get("needs_gpt", False)
        state["tool_name"] = route_result["tool_name"]
        state["tool_args"] = route_result["tool_args"]
        state["model_used"] = route_result["method"]
        state["latency_ms"] = route_result["latency_ms"]
        state["intent_confidence"] = route_result.get("confidence", 0.8)
        
        return state
    
    # ============================================================
    # Agent 節點
    # ============================================================
    
    def robot_agent_node(self, state: MASState) -> MASState:
        """機器人控制 - 本地執行 Modbus (保持新版的高效邏輯)"""
        tool_args = state.get("tool_args", {})
        detected_lang = state.get("detected_language", "zh")
        start_time = time.perf_counter()
        
        result = robot_controller.execute(
            action=tool_args.get("action"),
            speed=tool_args.get("speed")
        )
        
        response = result["message"]
        if result.get("modbus") and result["modbus"].get("register"):
            modbus_info = result["modbus"]
            response += f" [Modbus: Register={modbus_info['register']}, Value={modbus_info['value']}]"
        
        response = language_processor.process_response(response, detected_lang)
        
        state["tool_result"] = result["message"]
        state["agent_response"] = response
        state["modbus_result"] = result.get("modbus")
        state["model_used"] = "local"
        state["latency_ms"] = state.get("latency_ms", 0) + (time.perf_counter() - start_time) * 1000
        
        return state
    
    def sop_agent_node(self, state: MASState) -> MASState:
        """SOP 查詢 - 復刻舊版 RAG 邏輯，注入長期記憶"""
        user_input = state["user_input"]
        detected_lang = state.get("detected_language", "zh")
        start_time = time.perf_counter()

        # 1. 執行檢索 (純 RAG)
        rag_result = sop_query_tool.query(user_query=user_input)
        context_str = rag_result.get("context", "SOP 文件中未找到相關資訊。")

        # 2. 注入長期記憶
        memory_context = ""
        try:
            mem_ctx = memory_service.get_memory_context()
            if mem_ctx:
                memory_context = "\n─ Long-term Memory ─\n" + mem_ctx + "\n────────────────────\n"
                print(f"🧠 已檢索長期記憶上下文")
        except Exception as e:
            print(f"⚠️ 記憶檢索失敗: {e}")

        # 3. 構建 Prompt (完全復刻舊版)
        history_str = self._format_history(state.get("conversation_history", []))
        lang_hint = self._get_lang_hint(detected_lang)

        sop_prompt = f"""
You are a helpful multilingual agent explaining the graphics card assembly process based ONLY on the provided Standard Operating Procedure (SOP) context.
**REMEMBER to Respond in {lang_hint}(Include the words retrieved from SOP context, which means when user use {lang_hint}, you should translate the retrieved words from SOP context to {lang_hint} and only respond with the translated edition), user may talk to you in any language. Be concise and directly answer the user's question using the context.
- If the context doesn't contain the answer, state that the information is not available in the provided SOP documents. Do not invent information.
- If some part of user's query is asking or intending to ask about **safety/operational requirement** steps/rules, do not misunderstand it as sop steps.Do not invent information.Just output the the part of query that match your capabilities, **and output:"Current documents are not related to safety/operational requirement. Please route to safety agent"**.
- If user is asking about the process, steps, procedures, reference to the SOP concern information.
SOP Context:
---
{context_str}
---
{memory_context}
Language: {lang_hint}
Conversation History:
{history_str}
User's Question: {user_input}
Your Answer:
"""
        # 3. 呼叫 LLM
        response = self._call_gpt_raw(sop_prompt)
        response = language_processor.process_response(response, detected_lang)

        state["tool_result"] = context_str
        state["agent_response"] = response
        state["model_used"] = settings.openai_model
        state["latency_ms"] = state.get("latency_ms", 0) + (time.perf_counter() - start_time) * 1000

        # Phase 4: 偵測二次路由標記
        redirect = self._detect_redirect(response)
        if redirect:
            state["next_agent"] = redirect
            state["redirect_reason"] = f"sop_agent → {redirect}"
            print(f"   🔄 二次路由標記偵測到: {redirect}")

        return state
    
    def safety_agent_node(self, state: MASState) -> MASState:
        """安全須知 - RAG (復刻舊版邏輯) + 進產線核對清單"""
        user_input = state["user_input"]
        detected_lang = state.get("detected_language", "zh")
        start_time = time.perf_counter()

        # --- 0. 優先檢查：是否為交班/身份更新 (全域攔截) ---
        # 只要句子裡有 "身高" 和數字，就嘗試解析並更新設定
        if "身高" in user_input and any(char.isdigit() for char in user_input):
            parsed = safety_query_tool.parse_name_height(user_input)
            
            if parsed["success"]:
                name = parsed["name"]
                height = parsed["height"]
                
                # 🔧 關鍵動作：更新機械手臂控制器
                robot_controller.set_height(height)
                profile = robot_controller.current_profile
                
                # 更新 State
                state["operator_name"] = name
                state["operator_height"] = height
                state["height_profile"] = profile
                
                # 如果這是在 checklist 結尾等待輸入，解除該狀態
                state["awaiting_name_height"] = False 
                
                response = (f"✅ 交班確認！已識別操作員：{name} (身高 {height} cm)。\n\n"
                           f"🤖 機械手臂參數已自動調整為 **設定檔 {profile}** (適配身高範圍)。\n"
                           f"請注意交接事項與作業安全。")
            else:
                # 解析失敗但意圖明顯時的提示
                response = "收到身高資訊，但格式無法精確識別。請嘗試：「我是Edward，身高182公分」。"

            state["agent_response"] = language_processor.process_response(response, detected_lang)
            state["model_used"] = "rule_update_profile"
            state["latency_ms"] = state.get("latency_ms", 0) + (time.perf_counter() - start_time) * 1000
            return state

        # --- 1. 處理姓名身高輸入 (核對清單完成後) ---
        if state.get("awaiting_name_height", False):
            parsed = safety_query_tool.parse_name_height(user_input)
            
            if parsed["success"]:
                name = parsed["name"]
                height = parsed["height"]
                
                # 設定機械手臂身高設定檔
                robot_controller.set_height(height)
                profile = robot_controller.current_profile
                
                # 更新 state
                state["operator_name"] = name
                state["operator_height"] = height
                state["height_profile"] = profile
                state["awaiting_name_height"] = False
                
                response = (f"✅ 收到，{name} 操作員，身高 {height} 公分。\n\n"
                           f"🤖 機械手臂已設定為「設定檔 {profile}」。\n\n"
                           f"所有前置作業已確認完成，請注意安全！現在可以開始作業了。")
            else:
                response = parsed["message"]
            
            state["agent_response"] = language_processor.process_response(response, detected_lang)
            state["model_used"] = "rule"
            state["latency_ms"] = state.get("latency_ms", 0) + (time.perf_counter() - start_time) * 1000
            return state

        # --- 2. 開始進產線核對清單 ---
        if "進產線" in user_input or "进产线" in user_input:
            result = safety_query_tool.start_entry_checklist()
            
            # 更新狀態
            state["checklist_active"] = True
            state["current_checklist_index"] = 0 # 初始索引
            state["checklist_items"] = safety_query_tool.ENTRY_CHECKLIST # 可選，存items方便除錯
            
            response = result["message"]
            state["agent_response"] = language_processor.process_response(response, detected_lang)
            state["model_used"] = "rule"
            return state
        
        # --- 3. 處理核對清單回應 ---
        if state.get("checklist_active", False) and safety_query_tool.get_checklist_status()["is_active"]:
            result = safety_query_tool.process_checklist_response(user_input)
            
            # 🔴 關鍵修正：確實更新 State 中的狀態與索引
            state["checklist_active"] = result.get("checklist_active", False)
            state["current_checklist_index"] = result.get("current_checklist_index", 0)
            
            # 如果完成核對清單，設定 awaiting_name_height
            if result.get("awaiting_name_height", False):
                state["awaiting_name_height"] = True
            
            response = result["message"]
            state["agent_response"] = language_processor.process_response(response, detected_lang)
            state["model_used"] = "rule"
            return state

        # --- 復刻舊版標準 RAG 查詢邏輯 ---
        
        # 1. 檢索 (復刻舊版：同時搜 Safety 和 Troubleshooting)
        # 舊版: k=2 for safety, k=1 for troubleshooting
        res_s = vector_retriever.retrieve_for_safety(user_input, top_k=2)
        res_t = vector_retriever.retrieve_for_troubleshooting(user_input, top_k=1)
        
        # 合併結果
        all_results = res_s + res_t
        if all_results:
            context_str = "\n---\n".join([r.document.content for r in all_results])
        else:
            context_str = "安全文件中未找到相關資訊。"

        # 2. 構建 Prompt (完全復刻舊版)
        history_str = self._format_history(state.get("conversation_history", []))
        lang_hint = self._get_lang_hint(detected_lang)

        safety_prompt = f"""
You are a multilingual **Safety Agent** in a graphics card assembly production line.
Your role is to **search through the provided safety/operational requirement documents** and **accurately answer user questions related to safety protocols, operation requirements, troubleshooting, and best practices in {lang_hint}**.
- Base answers **only on information found in the provided documents**.
- If the user ask query about or similar to "If I forget something in the SOP". You should answer it.
- If some part of user's query is about **sop** steps, state: "Current documents are not related to SOP. Please route to SOP agent". For example, if user ask "What is the sixth operational requirement before starting the operation, and also tell me the sixth step in our graphic card assembly SOP?" you should answer "The sixth operational requirement is to..." and "Current documents are not related to SOP. Please route to SOP agent".
- If info not found, state that.
Safety/Operational Requirement Context:
---
{context_str}
---
Conversation History: {history_str}
Language: {lang_hint}
User Query: {user_input}
Your Answer:
"""
        # 3. 呼叫 LLM
        response = self._call_gpt_raw(safety_prompt)
        response = language_processor.process_response(response, detected_lang)

        state["tool_result"] = context_str
        state["agent_response"] = response
        state["model_used"] = settings.openai_model
        state["latency_ms"] = state.get("latency_ms", 0) + (time.perf_counter() - start_time) * 1000

        # Phase 4: 偵測二次路由標記
        redirect = self._detect_redirect(response)
        if redirect:
            state["next_agent"] = redirect
            state["redirect_reason"] = f"safety_agent → {redirect}"
            print(f"   🔄 二次路由標記偵測到: {redirect}")

        return state
    
    def troubleshoot_agent_node(self, state: MASState) -> MASState:
        """問題排解 Agent - 復刻舊版 Safety Agent 的邏輯 (因為舊版兩者合併)"""
        # 在舊版設計中，Troubleshooting 是包含在 Safety Agent 的 Prompt 邏輯裡的。
        # 為了適配新架構的 Router，我們這裡使用和 Safety Node 幾乎一樣的邏輯，
        # 但側重於 Troubleshooting 檢索。
        
        user_input = state["user_input"]
        detected_lang = state.get("detected_language", "zh")
        start_time = time.perf_counter()

        # 1. 檢索 (側重 Troubleshooting: k=3, Safety: k=1)
        res_t = vector_retriever.retrieve_for_troubleshooting(user_input, top_k=3)
        res_s = vector_retriever.retrieve_for_safety(user_input, top_k=1)
        
        all_results = res_t + res_s
        if all_results:
            context_str = "\n---\n".join([r.document.content for r in all_results])
        else:
            context_str = "問題排解文件中未找到相關資訊。"

        # 2. 構建 Prompt (使用 Safety Agent 的 Prompt，因為它包含了 troubleshooting 邏輯)
        history_str = self._format_history(state.get("conversation_history", []))
        lang_hint = self._get_lang_hint(detected_lang)

        # 使用同樣的 Prompt 模板，因為它已經寫得很好，能處理 troubleshooting
        trouble_prompt = f"""
You are a multilingual **Safety and Troubleshooting Agent** in a graphics card assembly production line.
Your role is to **search through the provided troubleshooting and safety documents** and **accurately answer user questions related to problems, errors, dropped tools, and best practices in {lang_hint}**.
- Base answers **only on information found in the provided documents**.
- If the user asks "What if I dropped a screw" or "Speed is too fast", answer directly from context.
- If info not found, state that and suggest contacting a supervisor.
Context:
---
{context_str}
---
Conversation History: {history_str}
Language: {lang_hint}
User Query: {user_input}
Your Answer:
"""
        # 3. 呼叫 LLM
        response = self._call_gpt_raw(trouble_prompt)
        response = language_processor.process_response(response, detected_lang)

        state["tool_result"] = context_str
        state["agent_response"] = response
        state["model_used"] = settings.openai_model
        state["latency_ms"] = state.get("latency_ms", 0) + (time.perf_counter() - start_time) * 1000

        return state

    def chat_agent_node(self, state: MASState) -> MASState:
        """對話 Agent - 復刻舊版 Chat Agent Prompt，注入長期記憶"""
        user_input = state["user_input"]
        detected_lang = state.get("detected_language", "zh")
        start_time = time.perf_counter()
        
        history_str = self._format_history(state.get("conversation_history", []))
        lang_hint = self._get_lang_hint(detected_lang)
        
        # 注入長期記憶
        memory_context = ""
        try:
            mem_ctx = memory_service.get_memory_context()
            if mem_ctx:
                memory_context = "\n─ Long-term Memory ─\n" + mem_ctx + "\n────────────────────\n"
                print(f"🧠 已檢索長期記憶上下文")
        except Exception as e:
            print(f"⚠️ 記憶檢索失敗: {e}")
        
        # 復刻舊版 chat_prompt_content_template
        chat_prompt = f"""
You are a friendly and helpful multilingual AI agent in a graphics card production line environment.
Engage in conversation naturally in {lang_hint}.
When user introduce themselves, you can respond with a friendly greeting and ask them how you can help them.
**BUT**, when user ask about "your capabilities", "who are you", "what can you do", "what is you duty", "introduce yourself", ... etc. Any related input, refer to **Your primary functions** section below, and
keep your responses concise and relevant to our production line setting if possible.
**Your primary functions** : Controlling specific robot actions (夾取散熱風扇, 機械手臂伸出, 放置散熱風扇, 全速運行機械手臂, 原速運行機械手臂, 慢速運行機械手臂), answering questions about the Standard Operating Procedure (SOP), and helping check or answering questions about safety/operational requirements. **all the content in {lang_hint} **
**ANSWER LOGIC** :  User's intent can be seperated into 4 categories:
    - Ask you to perform actions/function outside **Your primary functions**, then you should tell user you CANNOT offer to perform actions outside these functions (like searching online, booking tickets, etc.).
    - Maybe user just purely misspelled the action name, or ask you to perform actions in a way that is not clear, if you realize that, you should check with user to clarify the action name and tell user all the correct action name in **Your primary functions**.
    - Just general chat, then you can chat with user.
    - Maybe user would ask you to do something which is okay to do(things that won't break the system, like asking about the jokes, storys, your opinion about something, ... etc.), then you can chat with user.
    - Maybe user would ask you to translate something into specific language, then you should translate it for user.
{memory_context}
Conversation History:
{history_str}
User: {user_input}
Agent:
"""
        response = self._call_gpt_raw(chat_prompt)
        response = language_processor.process_response(response, detected_lang)
        
        state["agent_response"] = response
        state["model_used"] = "gpt-5-mini"
        state["latency_ms"] = state.get("latency_ms", 0) + (time.perf_counter() - start_time) * 1000
        
        return state

    def mcp_agent_node(self, state: MASState) -> MASState:
            """MCP 查詢 - 優先使用 router 的 tool_args，備援 GPT 解析"""
            user_input = state.get("user_input", "")
            detected_lang = state.get("detected_language", "zh")
            start_time = time.perf_counter()

            # 1. 永遠讓 GPT 解析參數（支援時區、城市等語意理解）
            # 規則層只負責路由到 mcp，參數解析交給 GPT
            queries = self._parse_mcp_with_gpt(user_input)

            # 2. 依序執行所有查詢，收集結果
            results = []
            for q in queries:
                try:
                    result = mcp_client.query(
                        query_type=q.get("query_type", "search"),
                        timezone=q.get("timezone", "Asia/Taipei"),
                        city=q.get("city", "Taipei"),
                        query=q.get("query", user_input),
                    )
                    if result.get("message"):
                        results.append(result["message"])
                except Exception as e:
                    results.append(f"查詢失敗: {e}")

            combined = "\n".join(results) if results else "查詢無結果"

            # 3. 若是搜尋結果，讓 GPT 整理成乾淨的中文摘要
            query_type = queries[0].get("query_type", "") if queries else ""
            if query_type == "search" and self.gpt_client and combined != "查詢無結果":
                try:
                    summary_prompt = f"""你是資訊整理助手。根據以下搜尋結果，用繁體中文整理出清晰、完整的回答。
- 直接回答用戶問題，不要說「根據搜尋結果」
- 保留重要細節和數字
- 去除廣告、導覽列、無關內容
- 格式清晰易讀

用戶問題：{user_input}

搜尋結果：
{combined[:8000]}"""
                    gpt_response = self.gpt_client.chat.completions.create(
                        model=settings.openai_model,
                        messages=[{"role": "user", "content": summary_prompt}],
                        temperature=1,
                        max_tokens=4000,
                        extra_body={"provider": {"order": ["OpenAI"], "allow_fallbacks": False}}
                    )
                    if gpt_response and gpt_response.choices and gpt_response.choices[0].message.content:
                        combined = gpt_response.choices[0].message.content
                except Exception as e:
                    print(f"⚠️ GPT 整理搜尋結果失敗: {e}")

            response = language_processor.process_response(combined, detected_lang)

            state["tool_result"] = combined
            state["agent_response"] = response
            state["model_used"] = settings.openai_model
            state["latency_ms"] = state.get("latency_ms", 0) + (time.perf_counter() - start_time) * 1000
            return state
    
    def _parse_mcp_with_gpt(self, user_input: str) -> list:
        """用 GPT 解析 MCP 查詢參數，支援多工具並行，回傳 list"""
        import re

        # 備援邏輯：GPT 不可用時的簡單規則
        def _fallback() -> list:
            queries = []
            if any(kw in user_input for kw in ["天氣", "weather"]):
                queries.append({"query_type": "weather", "city": "Taipei"})
            if any(kw in user_input for kw in ["幾點", "時間", "time"]):
                queries.append({"query_type": "time", "timezone": "Asia/Taipei"})
            if any(kw in user_input for kw in ["幾號", "日期", "星期"]):
                queries.append({"query_type": "date"})
            if any(kw in user_input for kw in ["搜尋", "查", "search"]):
                queries.append({"query_type": "search", "query": user_input})
            return queries if queries else [{"query_type": "search", "query": user_input}]

        if not self.gpt_client:
            return _fallback()

        system_prompt = """你是 MCP 查詢參數解析器。根據用戶輸入，解析出所有需要查詢的工具，以 JSON 陣列回傳。

類型規則：
1. search: 包含「搜尋」、「找」、「新聞」、「消息」、「是誰」、「什麼是」、「上網查」
2. weather: 包含「天氣」、「氣溫」、「下雨」、「溫度」
3. time: 包含「幾點」、「時間」、「現在幾點」、「當地時間」
4. date: 包含「幾號」、「星期幾」、「日期」、「今天」

參數規則：
- weather: city 必須翻譯為英文城市名
- time: timezone 使用 IANA 格式，根據用戶提到的地點推斷，若無指定預設 Asia/Taipei
  常用時區範例：
  台灣→Asia/Taipei, 日本/東京/大阪→Asia/Tokyo, 韓國/首爾→Asia/Seoul,
  北京/上海/香港→Asia/Shanghai, 新加坡→Asia/Singapore,
  曼谷/泰國→Asia/Bangkok, 越南/河內/胡志明→Asia/Ho_Chi_Minh,
  印尼/雅加達/爪哇→Asia/Jakarta, 峇厘島/峇里島/龍目島→Asia/Makassar,
  印度→Asia/Kolkata, 杜拜→Asia/Dubai, 倫敦→Europe/London,
  巴黎/柏林/羅馬→Europe/Paris, 紐約→America/New_York,
  洛杉磯→America/Los_Angeles, 雪梨/澳洲→Australia/Sydney,
  紐西蘭→Pacific/Auckland, 夏威夷→Pacific/Honolulu
- 若用戶同時問天氣和時間，陣列中包含兩個物件

輸出範例（問峇厘島時間）：
[{"query_type": "time", "timezone": "Asia/Makassar"}]

輸出範例（同時問天氣和時間）：
[{"query_type": "weather", "city": "Kaohsiung"}, {"query_type": "time", "timezone": "Asia/Taipei"}]

只返回 JSON 陣列，不要 Markdown 或其他文字。"""

        try:
            response = self.gpt_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                temperature=1,
                max_tokens=2000,
                extra_body={"provider": {"order": ["OpenAI"], "allow_fallbacks": False}}
            )

            if not response or not response.choices or not response.choices[0].message:
                return _fallback()

            content = response.choices[0].message.content
            if content is None:
                return _fallback()
            
            content = content.strip()

            # 尋找 JSON 陣列
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, list) and parsed:
                    return parsed

            # 若回傳的是單一物件，包成 list
            match_obj = re.search(r'\{.*\}', content, re.DOTALL)
            if match_obj:
                parsed = json.loads(match_obj.group(0))
                if isinstance(parsed, dict):
                    return [parsed]

            return _fallback()

        except Exception as e:
            print(f"⚠️ GPT 解析 MCP 參數失敗: {e}")
            return _fallback()
    
    

    # ============================================================
    # 底層呼叫
    # ============================================================
    
    def _call_gpt_raw(self, full_prompt: str) -> str:
        """直接呼叫 GPT (raw mode)，用於傳遞舊版設計的完整 Prompt"""
        if not self.gpt_client:
            return "GPT Client not available."
        
        try:
            # 舊版使用 system message 傳遞整個 context 和 prompt
            response = self.gpt_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": full_prompt}
                ],
                temperature=1,
                max_tokens=16000,
                extra_body={"provider": {"order": ["OpenAI"], "allow_fallbacks": False}}
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"⚠️ GPT 錯誤: {e}")
            return f"抱歉，發生錯誤: {e}"

    def _call_gpt(self, system_prompt: str, user_input: str) -> str:
        """標準 GPT 呼叫 (新版使用)"""
        if not self.gpt_client:
            return "GPT not available."
        try:
            response = self.gpt_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                temperature=1,
                max_tokens=16000,
                extra_body={"provider": {"order": ["OpenAI"], "allow_fallbacks": False}}
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error: {e}"


# 全域節點實例
graph_nodes = GraphNodes()