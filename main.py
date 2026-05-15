# main.py
"""
MAS - 顯示卡組裝多代理系統
支援：LangGraph + 混合路由 + 多語言 + 語音 + MCP
"""
import atexit # <--- 新增這個
import os     # <--- 新增這個
import time
from typing import Tuple, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from config.settings import settings
from graph.workflow import mas_graph
from graph.state import MASState
from tools.robot_control import robot_controller
from memory.graphiti_service import memory_service
from utils.language import language_processor



console = Console()

def cleanup_index():
    """程式結束時自動刪除索引"""
    import pathlib
    index_path = pathlib.Path(__file__).parent / "data" / "faiss_index.pkl"
    if index_path.exists():
        try:
            index_path.unlink()
            print(f"\n🧹 [系統清理] 已刪除暫存索引: {index_path}")
        except Exception as e:
            print(f"\n⚠️ 清理索引失敗: {e}")

class MASAssistant:
    """MAS 智慧助手 - 完整版"""
    
    def __init__(self, debug: bool = True, voice_mode: bool = False):
        self.debug = debug
        self.voice_mode = voice_mode
        self.running = False
        
        # 語音服務（延遲載入）
        self.stt = None
        self.tts = None
        
        # 統計
        self.latency_records = []
        self.route_stats = {"rule": 0, "compound": 0, "llm": 0}
        self.agent_stats = {}
        self.language_stats = {}

        # 🌟 新增：跨回合狀態暫存區 (Context Persistence)
        self.context_state = {
            "checklist_active": False,
            "current_checklist_index": 0,
            "checklist_items": None,
            "awaiting_name_height": False,
            "operator_name": None,
            "operator_height": None,
            "height_profile": None
        }
    
    def initialize(self):
        """初始化系統"""
        console.print(Panel.fit(
            "[bold blue]🚀 MAS - 顯示卡組裝多代理系統[/bold blue]\n"
            "[dim]Qwen 路由 + gpt-5-mini + 長期記憶[/dim]\n\n"
            f"路由: Qwen 0.6B (本地)\n"
            f"複雜任務: {settings.openai_model}\n"
            f"記憶體: Neo4j\n"
            f"語音: {'ON' if self.voice_mode else 'OFF'}",
            title="系統啟動"
        ))
        
        # 連接服務
        console.print("\n[yellow]正在連接服務...[/yellow]")
        memory_service.connect()
        memory_service.start_session()
        robot_controller.connect()
        
        # 載入語音服務
        if self.voice_mode:
            self._init_voice()
        
        console.print("[green]✅ 系統初始化完成[/green]\n")
    
    def _init_voice(self):
        """初始化語音服務"""
        try:
            from voice.stt import stt_service
            self.stt = stt_service
            if not self.stt.engine:
                self.stt.initialize()
            console.print(f"[green]✅ STT 引擎: {self.stt.engine_name}[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠️ STT 載入失敗: {e}[/yellow]")
        
        try:
            from voice.tts import tts_service
            self.tts = tts_service
            console.print("[green]✅ TTS 服務已載入[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠️ TTS 載入失敗: {e}[/yellow]")
    
    def chat(self, user_input: str) -> Tuple[str, float, Dict[str, Any]]:
        """處理用戶輸入"""
        start_time = time.perf_counter()
        
        # 1. 建立初始狀態，並注入上一回合的 Context
        initial_state: MASState = {
            "user_input": user_input,
            "conversation_history": [], # 這裡可以整合 memory service 的短期記憶，目前先留空讓 Graph 處理
            "start_time": start_time,
            
            # 🌟 注入跨回合狀態
            "checklist_active": self.context_state["checklist_active"],
            "current_checklist_index": self.context_state["current_checklist_index"],
            "checklist_items": self.context_state["checklist_items"],
            "awaiting_name_height": self.context_state["awaiting_name_height"],
            "operator_name": self.context_state["operator_name"],
            "operator_height": self.context_state["operator_height"],
            "height_profile": self.context_state["height_profile"]
        }
        
        if self.debug:
            console.print(f"\n[dim]{'='*60}[/dim]")
            console.print(f"[bold]👤 用戶:[/bold] {user_input}")
            # 除錯顯示當前狀態
            if initial_state["checklist_active"]:
                console.print(f"[magenta]🔒 Checklist 狀態鎖定中 (Index: {initial_state['current_checklist_index']})[/magenta]")
            console.print(f"[dim]{'='*60}[/dim]")
        
        try:
            # 執行 Graph
            final_state = mas_graph.invoke(initial_state)
            
            # 🌟 2. 更新跨回合狀態 (將結果存回 self.context_state)
            self.context_state["checklist_active"] = final_state.get("checklist_active", False)
            self.context_state["current_checklist_index"] = final_state.get("current_checklist_index", 0)
            self.context_state["checklist_items"] = final_state.get("checklist_items")
            self.context_state["awaiting_name_height"] = final_state.get("awaiting_name_height", False)
            
            # 如果有更新操作員資訊，也存下來
            if final_state.get("operator_name"):
                self.context_state["operator_name"] = final_state.get("operator_name")
            if final_state.get("operator_height"):
                self.context_state["operator_height"] = final_state.get("operator_height")
            if final_state.get("height_profile"):
                self.context_state["height_profile"] = final_state.get("height_profile")

        except Exception as e:
            console.print(f"[red]❌ 錯誤: {e}[/red]")
            import traceback
            traceback.print_exc()
            return f"抱歉，發生錯誤: {e}", 0, {}
        
        total_latency = (time.perf_counter() - start_time) * 1000
        self.latency_records.append(total_latency)
        
        # 更新統計
        route = final_state.get("route_decision", "chat")
        method = "rule" if final_state.get("matched_keywords") else "llm"
        # 修正：state_lock 也算是一種規則
        if final_state.get("model_used") == "state_lock":
            method = "state_lock"
        elif "複合" in str(final_state.get("matched_keywords", [])):
            method = "compound"
        
        self.route_stats[method] = self.route_stats.get(method, 0) + 1
        self.agent_stats[route] = self.agent_stats.get(route, 0) + 1
        
        detected_lang = final_state.get("detected_language", "zh")
        self.language_stats[detected_lang] = self.language_stats.get(detected_lang, 0) + 1
        
        # 保存記憶
        response = final_state.get("agent_response", "")
        memory_service.add_to_history(
            user_input=user_input,
            assistant_response=response[:500] if response else "",
            tool_used=final_state.get("tool_name"),
            tool_args=final_state.get("tool_args")
        )
        
        return response, total_latency, final_state
    
    def print_response(self, result: str, latency: float, state: Dict[str, Any]):
        """輸出回應"""
        route = state.get("route_decision", "chat")
        tool_name = state.get("tool_name")
        model = state.get("model_used", "unknown")
        detected_lang = state.get("detected_language", "zh")
        modbus = state.get("modbus_result")
        needs_gpt = state.get("needs_gpt", False)
        
        # 語言資訊
        lang_name = {"zh": "中文", "en": "English", "vi": "Tiếng Việt", "id": "Bahasa"}.get(detected_lang, detected_lang)
        
        # 模型資訊
        if model == "local":
            model_info = "🏠 本地處理"
        elif model == "gpt-5-mini":
            model_info = "☁️ gpt-5-mini"
        elif "qwen" in model.lower():
            model_info = f"🔀 {model}"
        else:
            model_info = model
        
        console.print(f"\n[dim]🌐 {lang_name} | 🎯 {route} | {model_info}[/dim]")
        
        if tool_name:
            console.print(f"[dim]🔧 工具: {tool_name}[/dim]")
        if modbus:
            console.print(f"[dim]📡 Modbus: Reg={modbus.get('register')}, Val={modbus.get('value')}[/dim]")
        
        console.print(Panel(
            Markdown(result) if result else "[dim]無回應[/dim]",
            title="🤖 From COIN",
            border_style="green"
        ))
        
        console.print(f"[dim]⏱️ {latency:.1f}ms[/dim]\n")
        
        # 語音輸出
        if self.voice_mode and self.tts and result:
            self.tts.speak(result, detected_lang)
    
    def print_stats(self):
        """顯示統計"""
        if not self.latency_records:
            console.print("[yellow]尚無統計[/yellow]")
            return
        
        avg = sum(self.latency_records) / len(self.latency_records)
        
        table = Table(title="📊 系統統計")
        table.add_column("指標", style="cyan")
        table.add_column("數值", style="green")
        
        table.add_row("總請求數", str(len(self.latency_records)))
        table.add_row("平均延遲", f"{avg:.1f} ms")
        table.add_row("---", "---")
        table.add_row("規則路由", str(self.route_stats.get("rule", 0)))
        table.add_row("複合路由", str(self.route_stats.get("compound", 0)))
        table.add_row("LLM 路由", str(self.route_stats.get("llm", 0)))
        
        console.print(table)
        
        if self.language_stats:
            lang_table = Table(title="🌐 語言統計")
            lang_table.add_column("語言", style="cyan")
            lang_table.add_column("次數", style="green")
            for lang, count in self.language_stats.items():
                lang_table.add_row(lang, str(count))
            console.print(lang_table)
    
    def print_help(self):
        """顯示說明"""
        help_text = """
[bold]指令:[/bold]
  [cyan]quit/q[/cyan] - 退出  [cyan]stats[/cyan] - 統計  [cyan]clear[/cyan] - 清除
  [cyan]help[/cyan] - 說明  [cyan]status[/cyan] - 機械手臂狀態
  [cyan]memory[/cyan] - 記憶體統計

[bold]語音:[/bold]
  [cyan]v[/cyan] - 單次語音輸入 (按 Enter 停止)
  [cyan]voice wake[/cyan] - 啟動喚醒詞持續監聽（說「嘿 CoinAI」觸發）
  [cyan]voice stop[/cyan] - 停止喚醒詞監聽
  [cyan]voice off[/cyan] - 停止語音模式
  [cyan]voice on[/cyan] - 啟用語音模式 (預設5秒錄音)

[bold]支援功能:[/bold]
  🤖 機器人控制: 伸出手臂、夾取、調整速度
  📋 SOP 查詢: 第三步是什麼、整個流程
  🛡️ 安全須知: 進產線、開工前注意事項
  🔧 問題排解: 螺絲掉了怎麼辦
  🌐 MCP 查詢: 現在幾點、今天天氣、搜尋內容
  🧠 長期記憶: 自動記住用戶姓名和偏好

[bold]多語言支援:[/bold]
  中文(繁體)、English、Tiếng Việt、Bahasa Indonesia
        """
        console.print(Panel(help_text, title="📖 使用說明"))
    
    def run(self):
        """主迴圈"""
        self.initialize()
        self.running = True
        self.print_help()
        
        while self.running:
            try:
                # 語音或文字輸入
                if self.voice_mode and self.stt:
                    console.print("[yellow]🎤 請說話 (5秒)...[/yellow]")
                    result = self.stt.listen_and_transcribe(5.0)
                    if result:
                        user_input = result.text
                        console.print(f"[dim]📝 識別: {user_input}[/dim]")
                    else:
                        continue
                else:
                    user_input = console.input("\n[bold blue]👤 請輸入:[/bold blue] ").strip()
                
                # 指令處理
                cmd = user_input.lower()
                if cmd in ['quit', 'exit', 'q']:
                    self.print_stats()
                    console.print("[yellow]👋 再見！[/yellow]")
                    break
                elif cmd == 'stats':
                    self.print_stats()
                    continue
                elif cmd == 'clear':
                    self.latency_records.clear()
                    self.route_stats = {"rule": 0, "compound": 0, "llm": 0}
                    self.agent_stats = {}
                    self.language_stats = {}
                    console.print("[green]🗑️ 已清除[/green]")
                    continue
                elif cmd == 'help':
                    self.print_help()
                    continue
                elif cmd == 'status':
                    console.print(f"[cyan]🤖 {robot_controller.get_status()}[/cyan]")
                    continue
                elif cmd == 'memory':
                    stats = memory_service.get_stats()
                    info_lines = [
                        f"連接狀態: {'✅ Neo4j' if stats['connected'] else '📦 本地模式'}",
                        f"當前用戶: {stats.get('current_user', 'default')}",
                        f"本次對話: {stats.get('session_messages', 0)} 則",
                        f"用戶記憶: {stats.get('user_facts', 0)} 條",
                        f"總對話數: {stats.get('total_episodes', 0)}",
                    ]
                    
                    # 顯示記憶內容
                    if stats.get('facts_preview'):
                        info_lines.append("\n📝 已記憶的資訊:")
                        for fact in stats['facts_preview']:
                            info_lines.append(f"  [{fact['type']}] {fact['value']}")
                    
                    console.print(Panel(
                        "\n".join(info_lines),
                        title="🧠 記憶體統計"
                    ))
                    continue
                elif cmd == 'voice on':
                    self.voice_mode = True
                    self._init_voice()
                    continue
                elif cmd == 'voice off':
                    self.voice_mode = False
                    # 停止喚醒詞監聽
                    try:
                        from voice.wake_listener import wake_listener
                        if wake_listener.is_listening():
                            wake_listener.stop()
                    except Exception:
                        pass
                    console.print("[yellow]🔇 語音模式已關閉[/yellow]")
                    continue
                elif cmd in ('voice listen', 'voice wake'):
                    # 啟動喚醒詞持續監聽
                    self._start_wake_listen()
                    continue
                elif cmd == 'voice stop':
                    # 停止喚醒詞監聽
                    try:
                        from voice.wake_listener import wake_listener
                        if wake_listener.is_listening():
                            wake_listener.stop()
                        else:
                            console.print("[yellow]⚠️ 喚醒詞監聽未啟動[/yellow]")
                    except Exception as e:
                        console.print(f"[red]❌ {e}[/red]")
                    continue
                elif cmd == 'v':
                    # 單次語音輸入
                    user_input = self._voice_single_input()
                    if not user_input:
                        continue
                elif cmd == 'debug on':
                    self.debug = True
                    continue
                elif cmd == 'debug off':
                    self.debug = False
                    continue
                elif not user_input:
                    continue
                
                # 處理輸入
                result, latency, state = self.chat(user_input)
                self.print_response(result, latency, state)
                
            except KeyboardInterrupt:
                console.print("\n[yellow]👋 再見！[/yellow]")
                break
            except Exception as e:
                console.print(f"[red]❌ 錯誤: {e}[/red]")
        
        # 清理
        try:
            from voice.wake_listener import wake_listener
            if wake_listener.is_listening():
                wake_listener.stop()
        except Exception:
            pass
        memory_service.close()
        robot_controller.close()
    
    def _voice_single_input(self) -> str:
        """單次語音輸入：按 Enter 停止錄音，轉文字"""
        if self.stt is None:
            self._init_voice()
        if self.stt is None:
            console.print("[red]❌ STT 服務未載入[/red]")
            return ""
        
        result = self.stt.listen_until_enter_and_transcribe()
        if result and result.text:
            console.print(f"[dim]📝 識別 ({result.engine}, {result.latency_ms:.0f}ms): {result.text}[/dim]")
            return result.text
        else:
            console.print("[yellow]⚠️ 未識別到語音[/yellow]")
            return ""
    
    def _start_wake_listen(self):
        """啟動喚醒詞持續監聽（Whisper 分段辨識方案）"""
        try:
            from voice.wake_listener import wake_listener
            from voice.vad import vad_detector
        except ImportError as e:
            console.print(f"[red]❌ 套件未安裝: {e}[/red]")
            return

        if self.stt is None:
            self._init_voice()

        def on_wake():
            """喚醒詞觸發後的回呼（在背景執行緒中執行）"""
            console.print("\n[bold green]🔔 喚醒！請開始說話...[/bold green]")

            # 用 VAD 錄音直到靜音
            audio = vad_detector.record_until_silence(
                max_duration=settings.wake_word_max_record,
                on_speech_start=lambda: console.print("[blue]🎙️ 聆聽中...[/blue]"),
                on_speech_end=lambda: console.print("[dim]✅ 偵測到靜音，處理中...[/dim]"),
            )

            if audio is not None and self.stt:
                result = self.stt.transcribe(audio)
                if result and result.text:
                    console.print(f"[dim]📝 識別 ({result.engine}): {result.text}[/dim]")
                    response, latency, state = self.chat(result.text)
                    self.print_response(response, latency, state)
                else:
                    console.print("[yellow]⚠️ 未識別到語音[/yellow]")
            else:
                console.print("[yellow]⚠️ 未捕捉到音訊[/yellow]")

        wake_listener.start(on_wake)
        console.print(
            f"[green]👂 持續監聽已啟動，說「{settings.wake_word}」來喚醒。"
            " 輸入 'voice stop' 停止[/green]"
        )


def main():
    """主程式"""
    import argparse
    parser = argparse.ArgumentParser(description="MAS 多代理系統")
    parser.add_argument("--voice", action="store_true", help="啟用語音模式")
    parser.add_argument("--debug", action="store_true", default=True, help="除錯模式")
    args = parser.parse_args()
    
    assistant = MASAssistant(debug=args.debug, voice_mode=args.voice)
    assistant.run()


if __name__ == "__main__":
    # 註冊清理函數，無論是正常退出還是按 Ctrl+C，都會執行
    atexit.register(cleanup_index)
    
    main()