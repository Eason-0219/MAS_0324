# graph/workflow.py
"""
LangGraph 工作流程定義

流程圖（含 Phase 4 二次路由）：

  START → Router → [chat/robot/mcp/sop/safety/troubleshoot]
                         ↓
                   redirect_check
                    ↙         ↘
               (有標記)      (無標記)
                 ↓               ↓
           二次路由目標         END
"""

from typing import Literal
from langgraph.graph import StateGraph, END

from graph.state import MASState
from graph.nodes import graph_nodes


# ------------------------------------------------------------------
# 路由決策函數
# ------------------------------------------------------------------

def route_decision(
    state: MASState,
) -> Literal["chat", "sop", "safety", "robot", "troubleshoot", "mcp"]:
    """第一次路由決策"""
    route = state.get("route_decision", "chat")
    valid = {"chat", "sop", "safety", "robot", "troubleshoot", "mcp"}
    return route if route in valid else "chat"


def redirect_check(
    state: MASState,
) -> Literal["sop", "safety", "troubleshoot", "__end__"]:
    """
    Phase 4 二次路由檢查節點。

    若 Agent 回應中包含重導向標記（next_agent），
    則路由到對應 Agent；否則結束。
    """
    next_agent = state.get("next_agent")
    if next_agent in ("sop", "safety", "troubleshoot"):
        # 清除標記，避免無限迴圈
        state["next_agent"] = None
        return next_agent
    return "__end__"


# ------------------------------------------------------------------
# 工作流程建構
# ------------------------------------------------------------------

def create_workflow() -> StateGraph:
    """創建 LangGraph 工作流程（含二次路由）"""
    workflow = StateGraph(MASState)

    # ── 節點 ──────────────────────────────────────────────────────
    workflow.add_node("router",       graph_nodes.hybrid_router_node)
    workflow.add_node("chat",         graph_nodes.chat_agent_node)
    workflow.add_node("sop",          graph_nodes.sop_agent_node)
    workflow.add_node("safety",       graph_nodes.safety_agent_node)
    workflow.add_node("robot",        graph_nodes.robot_agent_node)
    workflow.add_node("troubleshoot", graph_nodes.troubleshoot_agent_node)
    workflow.add_node("mcp",          graph_nodes.mcp_agent_node)

    # ── 入口 ──────────────────────────────────────────────────────
    workflow.set_entry_point("router")

    # ── 第一次路由 ────────────────────────────────────────────────
    workflow.add_conditional_edges(
        "router",
        route_decision,
        {
            "chat":         "chat",
            "sop":          "sop",
            "safety":       "safety",
            "robot":        "robot",
            "troubleshoot": "troubleshoot",
            "mcp":          "mcp",
        },
    )

    # ── 不需要二次路由的節點直接結束 ──────────────────────────────
    workflow.add_edge("chat",  END)
    workflow.add_edge("robot", END)
    workflow.add_edge("mcp",   END)

    # ── 可能觸發二次路由的節點 ────────────────────────────────────
    # sop / safety / troubleshoot 執行後進入 redirect_check
    for node in ("sop", "safety", "troubleshoot"):
        workflow.add_conditional_edges(
            node,
            redirect_check,
            {
                "sop":          "sop",
                "safety":       "safety",
                "troubleshoot": "troubleshoot",
                "__end__":      END,
            },
        )

    return workflow.compile()


# 全域工作流程實例
mas_graph = create_workflow()


def visualize_graph():
    """視覺化工作流程（需要 graphviz）"""
    try:
        from IPython.display import Image, display
        display(Image(mas_graph.get_graph().draw_mermaid_png()))
    except ImportError:
        print("""
```mermaid
graph TD
    START((Start)) --> Router[Hybrid Router]
    Router -->|chat| Chat[Chat Agent]
    Router -->|sop| SOP[SOP Agent]
    Router -->|safety| Safety[Safety Agent]
    Router -->|robot| Robot[Robot Agent]
    Router -->|troubleshoot| Troubleshoot[Troubleshoot Agent]
    Router -->|mcp| MCP[MCP Agent]
    Chat --> END((End))
    Robot --> END
    MCP --> END
    SOP --> RedirectCheck{Redirect?}
    Safety --> RedirectCheck
    Troubleshoot --> RedirectCheck
    RedirectCheck -->|sop| SOP
    RedirectCheck -->|safety| Safety
    RedirectCheck -->|troubleshoot| Troubleshoot
    RedirectCheck -->|end| END
```
        """)
