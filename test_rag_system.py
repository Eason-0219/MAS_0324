# test_rag_system.py
"""
測試 RAG 系統和進產線核對清單功能
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

from rich.console import Console
from rich.panel import Panel

console = Console()


def test_faiss_import():
    """測試 FAISS 套件"""
    console.print("\n[bold cyan]測試 1: FAISS 套件導入[/bold cyan]")
    try:
        import faiss
        console.print("[green]✓ FAISS 套件已安裝[/green]")
        return True
    except ImportError as e:
        console.print(f"[red]✗ FAISS 套件未安裝: {e}[/red]")
        console.print("[yellow]請執行: pip install faiss-cpu[/yellow]")
        return False


def test_vector_retriever():
    """測試向量檢索器"""
    console.print("\n[bold cyan]測試 2: 向量檢索器[/bold cyan]")
    try:
        from rag.vector_retriever import vector_retriever

        if vector_retriever.index is None:
            console.print("[yellow]! 向量索引不存在，正在構建...[/yellow]")
            console.print("[yellow]  這需要 Ollama BGE-M3 模型（約1-2分鐘）[/yellow]")

        console.print("[green]✓ 向量檢索器已載入[/green]")
        return True
    except Exception as e:
        console.print(f"[red]✗ 向量檢索器載入失敗: {e}[/red]")
        return False


def test_rag_tools():
    """測試 RAG Tools"""
    console.print("\n[bold cyan]測試 3: RAG Tools[/bold cyan]")

    try:
        from tools.sop_query_rag import sop_query_tool
        from tools.safety_query_rag import safety_query_tool
        from tools.troubleshoot_rag import troubleshoot_tool

        console.print("[green]✓ SOP Query Tool (RAG 混合模式)[/green]")
        console.print(f"  - RAG 啟用: {sop_query_tool.rag_enabled}")

        console.print("[green]✓ Safety Query Tool (RAG + 核對清單)[/green]")
        console.print(f"  - RAG 啟用: {safety_query_tool.rag_enabled}")
        console.print(f"  - 核對清單項目: {len(safety_query_tool.ENTRY_CHECKLIST)} 個")

        console.print("[green]✓ Troubleshoot Tool (純 RAG)[/green]")
        console.print(f"  - RAG 啟用: {troubleshoot_tool.rag_enabled}")

        return True
    except Exception as e:
        console.print(f"[red]✗ RAG Tools 載入失敗: {e}[/red]")
        import traceback
        traceback.print_exc()
        return False


def test_safety_checklist():
    """測試進產線核對清單"""
    console.print("\n[bold cyan]測試 4: 進產線核對清單[/bold cyan]")

    try:
        from tools.safety_query_rag import safety_query_tool

        # 重置
        safety_query_tool.reset_checklist()

        # 開始核對
        result = safety_query_tool.start_entry_checklist()
        console.print("[green]✓ 核對清單已啟動[/green]")
        console.print(f"  總項目: {result['total_items']}")
        console.print(f"  當前項目: {result['current_item']['id']}")

        # 模擬回答「是」
        result = safety_query_tool.process_checklist_response("是")
        console.print("[green]✓ 處理「是」回應成功[/green]")

        # 模擬回答「否」
        result = safety_query_tool.process_checklist_response("否")
        console.print("[green]✓ 處理「否」回應成功[/green]")
        console.print(f"  回應包含警告: {'未完成項目' in result['message']}")

        # 重置
        safety_query_tool.reset_checklist()

        return True
    except Exception as e:
        console.print(f"[red]✗ 核對清單測試失敗: {e}[/red]")
        import traceback
        traceback.print_exc()
        return False


def test_graph_nodes():
    """測試 Graph Nodes 導入"""
    console.print("\n[bold cyan]測試 5: Graph Nodes[/bold cyan]")

    try:
        from graph.nodes import graph_nodes
        console.print("[green]✓ Graph Nodes 已載入[/green]")
        console.print(f"  - GPT 客戶端: {'可用' if graph_nodes.gpt_client else '不可用'}[/green]")
        return True
    except Exception as e:
        console.print(f"[red]✗ Graph Nodes 載入失敗: {e}[/red]")
        import traceback
        traceback.print_exc()
        return False


def main():
    """執行所有測試"""
    console.print(Panel.fit(
        "[bold]MAS RAG 系統測試[/bold]\n"
        "測試 FAISS 向量檢索 + 進產線核對清單",
        title="測試開始"
    ))

    results = []

    # 執行測試
    results.append(("FAISS 套件", test_faiss_import()))
    results.append(("向量檢索器", test_vector_retriever()))
    results.append(("RAG Tools", test_rag_tools()))
    results.append(("進產線核對清單", test_safety_checklist()))
    results.append(("Graph Nodes", test_graph_nodes()))

    # 總結
    console.print("\n" + "=" * 60)
    passed = sum(1 for _, result in results if result)
    total = len(results)

    console.print(f"\n[bold]測試結果: {passed}/{total} 通過[/bold]")

    for name, result in results:
        status = "[green]✓[/green]" if result else "[red]✗[/red]"
        console.print(f"  {status} {name}")

    if passed == total:
        console.print("\n[bold green]✅ 所有測試通過！[/bold green]")
        console.print("\n[cyan]下一步：執行 python main.py 啟動系統[/cyan]")
        return 0
    else:
        console.print("\n[bold yellow]⚠️ 部分測試失敗[/bold yellow]")
        console.print("\n[yellow]建議：[/yellow]")
        console.print("1. 確保已安裝 faiss-cpu: pip install faiss-cpu")
        console.print("2. 確保 Ollama 已運行並下載 bge-m3 模型: ollama pull bge-m3")
        return 1


if __name__ == "__main__":
    sys.exit(main())
