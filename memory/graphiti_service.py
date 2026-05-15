# memory/graphiti_service.py
"""
記憶體服務 - 長期記憶管理
使用 LLM 智慧提取用戶資訊，Neo4j 儲存

核心功能：
1. LLM 判斷對話是否包含需要記憶的資訊
2. LLM 提取結構化事實（姓名、身高、偏好、任何重要資訊）
3. Neo4j 儲存用戶 Profile 和事實節點
4. 對話時讀取相關記憶並注入上下文
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field

try:
    from neo4j import GraphDatabase
    import logging
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    print("⚠️ neo4j 套件未安裝，記憶體服務將使用本地模式")

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from config.settings import settings


# ============================================================
# LLM 記憶提取器
# ============================================================

class MemoryExtractor:
    """使用 LLM 提取需要記憶的資訊"""
    
    EXTRACTION_PROMPT = """你是記憶提取助手。分析用戶的對話，判斷是否包含需要長期記住的資訊。

任務：
1. 判斷這句話是否包含「需要記憶的新資訊」
2. 如果是疑問句（問問題）→ 不需要記憶
3. 如果是陳述句且包含用戶的個人資訊 → 需要記憶

需要記憶的資訊類型：
- 姓名、暱稱
- 身體特徵（身高、體重等）
- 職位、角色、身份
- 偏好（喜歡的速度、習慣等）
- 技能等級（新手、專家等）
- 任何用戶主動分享的個人資訊

回應格式（JSON）：
{
  "should_remember": true/false,
  "reason": "簡短說明為什麼需要/不需要記憶",
  "facts": [
    {"type": "name", "value": "小明", "context": "用戶的名字"},
    {"type": "height", "value": "180cm", "context": "用戶的身高"},
    {"type": "role", "value": "操作員", "context": "用戶的職位"}
  ]
}

如果不需要記憶，facts 返回空陣列 []。
"""

    def __init__(self):
        self.client = None
        if OPENAI_AVAILABLE and settings.openai_api_key:
            self.client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url
            )
    
    def extract(self, user_input: str, assistant_response: str = "") -> Dict[str, Any]:
        """
        使用 LLM 提取需要記憶的資訊
        
        Returns:
            {
                "should_remember": bool,
                "reason": str,
                "facts": [{"type": str, "value": str, "context": str}, ...]
            }
        """
        if not self.client:
            return {"should_remember": False, "reason": "LLM 不可用", "facts": []}
        
        try:
            response = self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": self.EXTRACTION_PROMPT},
                    {"role": "user", "content": f"用戶說：{user_input}"}
                ],
                temperature=0,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            
            # 解析 JSON
            # 處理可能的 markdown 格式
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            result = json.loads(content)
            return result
            
        except Exception as e:
            print(f"⚠️ 記憶提取錯誤: {e}")
            return {"should_remember": False, "reason": str(e), "facts": []}


# ============================================================
# 記憶體服務主類
# ============================================================

class MemoryService:
    """
    記憶體服務
    
    功能：
    - 短期記憶：當前對話歷史
    - 長期記憶：用戶事實（Neo4j）
    - LLM 智慧提取
    """
    
    def __init__(self):
        self.neo4j_driver = None
        self.connected = False
        self.extractor = MemoryExtractor()
        
        # 短期記憶
        self.current_session: Dict[str, Any] = {
            "user_id": "default",
            "conversation_history": [],
            "start_time": datetime.now()
        }
        
        # 本地快取（Neo4j 不可用時）
        self.local_cache: Dict[str, Any] = {
            "users": {},
            "facts": {},  # user_id -> [facts]
            "episodes": []
        }
    
    # ============================================================
    # 連接管理
    # ============================================================
    
    def connect(self) -> bool:
        """連接 Neo4j"""
        if not NEO4J_AVAILABLE:
            print("📦 使用本地快取模式")
            return False
        
        try:
            self.neo4j_driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password)
            )
            with self.neo4j_driver.session() as session:
                session.run("RETURN 1")
            
            self.connected = True
            print(f"✅ 已連接 Neo4j: {settings.neo4j_uri}")
            self._init_schema()
            return True
            
        except Exception as e:
            print(f"⚠️ Neo4j 連接失敗: {e}，使用本地模式")
            self.connected = False
            return False
    
    def _init_schema(self):
        """初始化 Schema"""
        if not self.connected:
            return
        
        with self.neo4j_driver.session() as session:
            # 用戶索引
            session.run("""
                CREATE INDEX user_id_index IF NOT EXISTS
                FOR (u:User) ON (u.user_id)
            """)
            # 事實索引
            session.run("""
                CREATE INDEX fact_type_index IF NOT EXISTS
                FOR (f:Fact) ON (f.type)
            """)
    
    def close(self):
        """關閉連接"""
        if self.neo4j_driver:
            self.neo4j_driver.close()
            print("🔌 Neo4j 已關閉")
    
    # ============================================================
    # 會話管理
    # ============================================================
    
    def start_session(self, user_id: str = "default"):
        """開始新會話"""
        self.current_session = {
            "user_id": user_id,
            "conversation_history": [],
            "start_time": datetime.now()
        }
        
        # 載入用戶記憶
        facts = self.get_user_facts(user_id)
        if facts:
            name_fact = next((f for f in facts if f.get("type") == "name"), None)
            if name_fact:
                print(f"👋 歡迎回來，{name_fact['value']}!")
            else:
                print(f"🆕 新會話開始 (已有 {len(facts)} 條記憶)")
        else:
            print(f"🆕 新會話開始")
    
    # ============================================================
    # 記憶保存（LLM 提取）
    # ============================================================
    
    def add_to_history(
        self, 
        user_input: str, 
        assistant_response: str,
        tool_used: Optional[str] = None,
        tool_args: Optional[Dict[str, Any]] = None
    ):
        """添加對話並使用 LLM 提取記憶"""
        user_id = self.current_session["user_id"]
        
        # 保存到短期記憶
        entry = {
            "user": user_input,
            "assistant": assistant_response,
            "tool": tool_used,
            "timestamp": datetime.now().isoformat()
        }
        self.current_session["conversation_history"].append(entry)
        
        # 使用 LLM 提取需要記憶的資訊
        extraction = self.extractor.extract(user_input, assistant_response)
        
        if extraction.get("should_remember") and extraction.get("facts"):
            print(f"🧠 LLM 判斷需要記憶: {extraction.get('reason', '')}")
            for fact in extraction["facts"]:
                self._save_fact(user_id, fact)
        
        # 保存對話到長期記憶
        self._save_episode(user_id, user_input, assistant_response, tool_used)
    
    def _save_fact(self, user_id: str, fact: Dict[str, Any]):
        """保存事實到 Neo4j"""
        fact_type = fact.get("type", "unknown")
        fact_value = fact.get("value", "")
        fact_context = fact.get("context", "")
        
        print(f"   💾 記憶: [{fact_type}] {fact_value}")
        
        if self.connected:
            try:
                with self.neo4j_driver.session() as session:
                    # 使用 MERGE 避免重複，並更新時間戳
                    session.run("""
                        MERGE (u:User {user_id: $user_id})
                        MERGE (u)-[:HAS_FACT]->(f:Fact {type: $type})
                        SET f.value = $value,
                            f.context = $context,
                            f.updated_at = datetime()
                    """,
                        user_id=user_id,
                        type=fact_type,
                        value=fact_value,
                        context=fact_context
                    )
            except Exception as e:
                print(f"⚠️ 保存事實失敗: {e}")
        else:
            # 本地模式
            if user_id not in self.local_cache["facts"]:
                self.local_cache["facts"][user_id] = []
            
            # 更新或添加事實
            existing = next(
                (f for f in self.local_cache["facts"][user_id] if f["type"] == fact_type),
                None
            )
            if existing:
                existing["value"] = fact_value
                existing["context"] = fact_context
            else:
                self.local_cache["facts"][user_id].append({
                    "type": fact_type,
                    "value": fact_value,
                    "context": fact_context
                })
    
    def _save_episode(self, user_id: str, user_input: str, response: str, tool: Optional[str]):
        """保存對話到長期記憶"""
        if self.connected:
            try:
                with self.neo4j_driver.session() as session:
                    session.run("""
                        MERGE (u:User {user_id: $user_id})
                        CREATE (e:Episode {
                            user_input: $user_input,
                            response: $response,
                            tool: $tool,
                            timestamp: datetime()
                        })
                        CREATE (u)-[:HAD_CONVERSATION]->(e)
                    """,
                        user_id=user_id,
                        user_input=user_input,
                        response=response[:500],
                        tool=tool
                    )
            except Exception as e:
                print(f"⚠️ 保存對話失敗: {e}")
        else:
            self.local_cache["episodes"].append({
                "user_id": user_id,
                "user_input": user_input,
                "response": response,
                "tool": tool,
                "timestamp": datetime.now()
            })
    
    # ============================================================
    # 記憶讀取
    # ============================================================
    
    def get_user_facts(self, user_id: str) -> List[Dict[str, Any]]:
        """獲取用戶的所有事實"""
        facts = []
        
        if self.connected:
            try:
                with self.neo4j_driver.session() as session:
                    result = session.run("""
                        MATCH (u:User {user_id: $user_id})-[:HAS_FACT]->(f:Fact)
                        RETURN f.type as type, f.value as value, f.context as context
                        ORDER BY f.updated_at DESC
                    """, user_id=user_id)
                    
                    for record in result:
                        # 防止 None 值
                        fact_type = record["type"]
                        fact_value = record["value"]
                        if fact_type and fact_value:
                            facts.append({
                                "type": fact_type,
                                "value": fact_value,
                                "context": record["context"] or ""
                            })
            except Exception as e:
                print(f"⚠️ 獲取事實失敗: {e}")
        else:
            facts = self.local_cache["facts"].get(user_id, [])
        
        return facts
    
    def get_recent_episodes(self, user_id: str, limit: int = 5) -> List[Dict]:
        """獲取最近的對話"""
        episodes = []
        
        if self.connected:
            try:
                with self.neo4j_driver.session() as session:
                    result = session.run("""
                        MATCH (u:User {user_id: $user_id})-[:HAD_CONVERSATION]->(e:Episode)
                        RETURN e.user_input as user_input, e.response as response
                        ORDER BY e.timestamp DESC
                        LIMIT $limit
                    """, user_id=user_id, limit=limit)
                    
                    for record in result:
                        # 防止 None 值
                        user_input = record["user_input"]
                        response = record["response"]
                        if user_input:
                            episodes.append({
                                "user": user_input,
                                "assistant": response or ""
                            })
            except Exception as e:
                print(f"⚠️ 獲取對話失敗: {e}")
        else:
            user_episodes = [
                e for e in self.local_cache["episodes"]
                if e["user_id"] == user_id
            ][-limit:]
            for e in user_episodes:
                episodes.append({
                    "user": e["user_input"],
                    "assistant": e["response"] or ""
                })
        
        return episodes
    
    def get_memory_context(self, user_id: str = None) -> str:
        """
        獲取記憶上下文 - 供 LLM 使用
        
        將所有記憶整理成 LLM 可理解的格式
        """
        user_id = user_id or self.current_session["user_id"]
        context_parts = []
        
        # 1. 用戶事實
        facts = self.get_user_facts(user_id)
        if facts:
            fact_lines = []
            for fact in facts:
                fact_lines.append(f"- {fact['context']}: {fact['value']}")
            context_parts.append("【用戶資訊】\n" + "\n".join(fact_lines))
        
        # 2. 最近對話
        recent = self.get_recent_episodes(user_id, limit=3)
        if recent:
            history_lines = []
            for ep in reversed(recent):  # 按時間順序
                history_lines.append(f"用戶: {ep['user'][:80]}")
                history_lines.append(f"助手: {ep['assistant'][:80]}")
            context_parts.append("【近期對話】\n" + "\n".join(history_lines))
        
        # 3. 當前會話
        current = self.current_session["conversation_history"][-3:]
        if current:
            current_lines = []
            for entry in current:
                current_lines.append(f"用戶: {entry['user']}")
                current_lines.append(f"助手: {entry['assistant'][:80]}")
            context_parts.append("【本次對話】\n" + "\n".join(current_lines))
        
        if context_parts:
            return "\n\n".join(context_parts)
        return ""
    
    # ============================================================
    # 統計
    # ============================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取統計"""
        user_id = self.current_session["user_id"]
        stats = {
            "connected": self.connected,
            "current_user": user_id,
            "session_messages": len(self.current_session["conversation_history"]),
        }
        
        if self.connected:
            try:
                with self.neo4j_driver.session() as session:
                    # 總對話數
                    result = session.run("MATCH (e:Episode) RETURN count(e) as count")
                    stats["total_episodes"] = result.single()["count"]
                    
                    # 總用戶數
                    result = session.run("MATCH (u:User) RETURN count(u) as count")
                    stats["total_users"] = result.single()["count"]
                    
                    # 當前用戶的事實數
                    result = session.run("""
                        MATCH (u:User {user_id: $user_id})-[:HAS_FACT]->(f:Fact)
                        RETURN count(f) as count
                    """, user_id=user_id)
                    stats["user_facts"] = result.single()["count"]
            except:
                pass
        else:
            stats["total_episodes"] = len(self.local_cache["episodes"])
            stats["total_users"] = len(self.local_cache["facts"])
            stats["user_facts"] = len(self.local_cache["facts"].get(user_id, []))
        
        # 列出當前用戶的事實
        facts = self.get_user_facts(user_id)
        if facts:
            stats["facts_preview"] = facts[:5]
        
        return stats


# 全域實例
memory_service = MemoryService()
