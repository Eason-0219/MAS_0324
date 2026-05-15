# test_system.py
"""MAS 系統測試"""

import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from config.settings import settings
from graph.router import hybrid_router
from graph.workflow import mas_graph
from tools.robot_control import robot_controller
from utils.language import language_processor

console = Console()


def test_router():
    """測試混合路由器"""
    console.print("\n[bold]🔀 測試混合路由器[/bold]\n")
    
    test_cases = [
        # 機械手臂（原有 + 擴充）
        ("伸出機械手臂", "robot", "rule"),
        ("調慢速度", "robot", "rule"),
        ("把機械手臂加快", "robot", "rule"),
        ("機械手臂太快了", "robot", "rule"),
        ("收回手臂", "robot", "rule"),
        # SOP 查詢（新增）
        ("下一步該做什麼", "sop", "rule"),
        ("第三步是什麼", "sop", "rule"),
        ("整個組裝流程", "sop", "rule"),
        # MCP 查詢（新增）
        ("現在幾點", "mcp", "rule"),
        ("今天星期幾", "mcp", "rule"),
        ("台北天氣", "mcp", "rule"),
        ("東京天氣怎麼樣", "mcp", "rule"),
        ("搜尋以太幣最新消息", "mcp", "rule"),
        # Safety
        ("我要進產線了", "safety", "rule"),
        # Troubleshoot（需 LLM 路由）
        ("當我組裝到第8步時螺絲掉了該怎麼辦", "troubleshoot", None),
        # Chat（LLM 路由）
        ("你好", "chat", None),
    ]
    
    table = Table(title="路由測試")
    table.add_column("輸入", width=40)
    table.add_column("預期", style="yellow")
    table.add_column("實際", style="green")
    table.add_column("方法")
    table.add_column("延遲")
    table.add_column("✓")
    
    for user_input, expected, expected_method in test_cases:
        result = hybrid_router.route(user_input, debug=False)
        passed = result["route"] == expected
        table.add_row(
            user_input[:38],
            expected,
            result["route"],
            result["method"],
            f"{result['latency_ms']:.0f}ms",
            "✅" if passed else "❌"
        )
    
    console.print(table)


def test_language():
    """測試多語言偵測"""
    console.print("\n[bold]🌐 測試語言偵測[/bold]\n")
    
    tests = [
        ("伸出機械手臂", "zh"),
        ("Extend the robot arm", "en"),
        ("Kéo dài cánh tay robot", "vi"),
        ("Perpanjang lengan robot", "id"),
    ]
    
    for text, expected in tests:
        lang, conf = language_processor.detect_language(text)
        status = "✅" if lang == expected else "❌"
        console.print(f"  {status} '{text[:30]}' → {lang} ({conf:.1%})")


def test_workflow():
    """測試 LangGraph 工作流程"""
    console.print("\n[bold]🔄 測試工作流程[/bold]\n")
    
    tests = [
        "伸出機械手臂",
        "當我做到第5步時螺絲掉了怎麼辦",
        "開工前要注意什麼",
    ]
    
    for user_input in tests:
        console.print(f"[cyan]輸入:[/cyan] {user_input}")
        start = time.perf_counter()
        state = mas_graph.invoke({"user_input": user_input})
        latency = (time.perf_counter() - start) * 1000
        
        console.print(f"[green]路由:[/green] {state.get('route_decision')}")
        console.print(f"[green]回應:[/green] {state.get('agent_response', '')[:80]}...")
        console.print(f"[dim]延遲: {latency:.0f}ms[/dim]\n")


def main():
    console.print(Panel.fit(
        f"[bold]MAS 系統測試[/bold]\n"
        f"Router: {settings.ollama_router_model}\n"
        f"Executor: {settings.ollama_executor_model}",
        title="🧪 測試"
    ))
    
    robot_controller.connect()
    
    test_router()
    test_language()
    test_workflow()
    
    console.print("\n[bold green]✅ 測試完成[/bold green]")


if __name__ == "__main__":
    main()
