# api/server.py
"""
FastAPI 後端 — MAS Web UI 入口

端點：
  POST /api/chat          — 文字對話
  WS   /ws/chat           — WebSocket 即時對話（串流狀態）
  GET  /api/status        — 系統狀態
  GET  /api/stats         — 統計資料
  POST /api/voice/upload  — 上傳音訊檔轉錄
"""

import time
import json
import asyncio
import threading
import pathlib
from typing import Dict, Any, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

from config.settings import settings
from graph.workflow import mas_graph
from graph.state import MASState
from tools.robot_control import robot_controller
from voice.tts import tts_service
from memory.graphiti_service import memory_service

app = FastAPI(title="MAS API", version="1.0.0")

# CORS — 允許 Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 喚醒詞設定持久化 ─────────────────────────────────────────────────────
_WAKE_CFG_PATH = pathlib.Path(__file__).parent.parent / "data" / "wake_config.json"

def _load_wake_config() -> dict:
    """從檔案讀取喚醒詞設定，不存在則用預設值"""
    try:
        if _WAKE_CFG_PATH.exists():
            return json.loads(_WAKE_CFG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"wake_word": settings.wake_word, "tts_enabled": True}

def _save_wake_config(cfg: dict):
    """把喚醒詞設定寫入檔案"""
    try:
        _WAKE_CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _WAKE_CFG_PATH.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        print(f"⚠️ 喚醒詞設定儲存失敗: {e}")

# ── 喚醒詞狀態（全域）────────────────────────────────────────────────────
_persisted = _load_wake_config()
_wake_settings: Dict[str, Any] = {
    "wake_word": _persisted.get("wake_word", settings.wake_word),
    "tts_enabled": _persisted.get("tts_enabled", True),
    "listening": False,
}
_wake_clients: Set[WebSocket] = set()   # 訂閱喚醒事件的 WS 連線
_event_loop = None  # FastAPI 主 event loop（startup 時存入）


async def _broadcast_wake(payload: dict):
    """廣播喚醒事件給所有訂閱的前端"""
    dead = set()
    for ws in _wake_clients:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.add(ws)
    _wake_clients.difference_update(dead)


def _push_wake_event(payload: dict):
    """從背景執行緒安全地推送事件（用 FastAPI 主 event loop）"""
    global _event_loop
    try:
        if _event_loop and _event_loop.is_running():
            asyncio.run_coroutine_threadsafe(_broadcast_wake(payload), _event_loop)
    except Exception:
        pass


async def _broadcast_wake_bytes(data: bytes):
    """廣播二進位音訊到所有 wake clients"""
    dead = set()
    for ws in _wake_clients:
        try:
            await ws.send_bytes(data)
        except Exception:
            dead.add(ws)
    _wake_clients.difference_update(dead)


def _push_wake_bytes(data: bytes):
    """從背景執行緒安全地推送二進位音訊"""
    global _event_loop
    try:
        if _event_loop and _event_loop.is_running():
            asyncio.run_coroutine_threadsafe(_broadcast_wake_bytes(data), _event_loop)
    except Exception:
        pass


def _start_wake_listener():
    """在背景執行緒啟動喚醒詞監聽"""
    try:
        from voice.wake_listener import WakeWordDetector
        from voice.vad import VADDetector
        from voice.stt import stt_service
        from voice.tts import tts_service

        detector = WakeWordDetector(wake_word=_wake_settings["wake_word"])
        if not detector.initialize():
            print("⚠️ 喚醒詞偵測器初始化失敗（缺少 whisper/sounddevice）")
            return

        _wake_settings["listening"] = True
        _push_wake_event({"type": "wake_status", "listening": True})

        def on_wake():
            print("🔔 on_wake() 觸發，已通知前端...")
            _push_wake_event({"type": "wake_activated"})
            
            # --- 舊版直接在後端錄音與對話的邏輯 (已註解以配合VoiceOrb跳轉) ---
            """
            # 等 wake_listener 當前 chunk 結束，避免搶麥克風
            import time as _t
            _t.sleep(0.5)

            # VAD 錄音
            vad = VADDetector()
            print("🎙️ 開始 VAD 錄音...")
            audio = vad.record_until_silence(
                max_duration=settings.wake_word_max_record,
                silence_timeout=5.0,
                on_speech_start=lambda: (print("🗣️ 偵測到語音開始"), _push_wake_event({"type": "wake_listening"})),
                on_speech_end=lambda: (print("🔇 偵測到靜音結束"), _push_wake_event({"type": "wake_processing"})),
            )

            if audio is None:
                print("⚠️ VAD 未捕捉到語音，退出")
                _push_wake_event({"type": "wake_idle"})
                return

            print(f"✅ VAD 錄音完成，音訊長度: {len(audio)} samples")

            # STT
            if stt_service.engine is None:
                stt_service.initialize()
            result = stt_service.transcribe(audio)
            if not result or not result.text.strip():
                print("⚠️ STT 未識別到文字")
                _push_wake_event({"type": "wake_idle"})
                return

            transcript = result.text.strip()
            print(f"📝 STT 識別結果: {transcript}")
            _push_wake_event({"type": "wake_transcript", "text": transcript})

            # MAS
            try:
                mas_result = _run_mas(transcript)
                _push_wake_event({"type": "wake_response", **mas_result})

                # TTS
                if _wake_settings.get("tts_enabled", True):
                    try:
                        # 合成 TTS 並推送到所有前端 WebSocket 播放
                        tts_result = tts_service.elevenlabs.synthesize_to_bytes(
                            mas_result["response"],
                            language=mas_result.get("detected_language", "zh")
                        )
                        if tts_result.success and tts_result.audio_data:
                            # 先通知前端 TTS 開始
                            _push_wake_event({"type": "wake_tts_start"})
                            # 推送音訊 bytes（分塊）
                            chunk_size = 4096
                            audio = tts_result.audio_data
                            for i in range(0, len(audio), chunk_size):
                                _push_wake_bytes(audio[i:i + chunk_size])
                            _push_wake_event({"type": "wake_tts_end"})
                    except Exception as e:
                        print(f"⚠️ TTS 失敗: {e}")
            except Exception as e:
                _push_wake_event({"type": "wake_error", "message": str(e)})

            _push_wake_event({"type": "wake_idle"})
            """
            print("▶️ 已通知前端喚醒，交由前端 VoiceOrb 進行持續對答。")

        # 若喚醒詞改變，重啟 detector
        _wake_settings["_detector"] = detector
        detector.start(on_wake)

    except Exception as e:
        print(f"❌ 喚醒詞監聽啟動失敗: {e}")
        _wake_settings["listening"] = False

# ── 跨請求共享的 context 狀態 ─────────────────────────────────────────────
_context_state: Dict[str, Any] = {
    "checklist_active": False,
    "current_checklist_index": 0,
    "checklist_items": None,
    "awaiting_name_height": False,
    "operator_name": None,
    "operator_height": None,
    "height_profile": None,
}

# 統計
_stats: Dict[str, Any] = {
    "total_requests": 0,
    "latency_records": [],
    "agent_stats": {},
    "language_stats": {},
}


# ── Pydantic 模型 ─────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    response: str
    route: str
    model_used: str
    latency_ms: float
    tool_name: Optional[str] = None
    modbus_result: Optional[Dict] = None
    detected_language: str = "zh"
    redirect_reason: Optional[str] = None


# ── 核心處理函數 ──────────────────────────────────────────────────────────

def _run_mas(user_input: str) -> Dict[str, Any]:
    """執行 MAS graph，回傳結果 dict"""
    global _context_state

    start = time.perf_counter()

    initial_state: MASState = {
        "user_input": user_input,
        "conversation_history": [],
        "start_time": start,
        **_context_state,
    }

    final_state = mas_graph.invoke(initial_state)

    # 更新跨請求狀態
    _context_state["checklist_active"] = final_state.get("checklist_active", False)
    _context_state["current_checklist_index"] = final_state.get("current_checklist_index", 0)
    _context_state["checklist_items"] = final_state.get("checklist_items")
    _context_state["awaiting_name_height"] = final_state.get("awaiting_name_height", False)
    if final_state.get("operator_name"):
        _context_state["operator_name"] = final_state["operator_name"]
    if final_state.get("operator_height"):
        _context_state["operator_height"] = final_state["operator_height"]
    if final_state.get("height_profile"):
        _context_state["height_profile"] = final_state["height_profile"]

    latency = (time.perf_counter() - start) * 1000

    # 更新統計
    _stats["total_requests"] += 1
    _stats["latency_records"].append(latency)
    route = final_state.get("route_decision", "chat")
    _stats["agent_stats"][route] = _stats["agent_stats"].get(route, 0) + 1
    lang = final_state.get("detected_language", "zh")
    _stats["language_stats"][lang] = _stats["language_stats"].get(lang, 0) + 1

    # 儲存記憶
    response = final_state.get("agent_response", "")
    memory_service.add_to_history(
        user_input=user_input,
        assistant_response=response[:500],
        tool_used=final_state.get("tool_name"),
        tool_args=final_state.get("tool_args"),
    )

    return {
        "response": response,
        "route": route,
        "model_used": final_state.get("model_used", "unknown"),
        "latency_ms": latency,
        "tool_name": final_state.get("tool_name"),
        "modbus_result": final_state.get("modbus_result"),
        "detected_language": lang,
        "redirect_reason": final_state.get("redirect_reason"),
    }


# ── REST 端點 ─────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    global _event_loop
    _event_loop = asyncio.get_running_loop()  # 存住 FastAPI 的 loop（Python 3.10+ 必須用 get_running_loop）
    memory_service.connect()
    memory_service.start_session()
    robot_controller.connect()
    # 背景執行緒啟動喚醒詞監聽
    t = threading.Thread(target=_start_wake_listener, daemon=True, name="WakeListener")
    t.start()


@app.on_event("shutdown")
async def shutdown():
    memory_service.close()
    robot_controller.close()


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """文字對話端點"""
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, _run_mas, req.message
        )
        return ChatResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
async def status():
    """系統狀態"""
    return {
        "status": "ok",
        "robot": robot_controller.get_status(),
        "context": {
            "checklist_active": _context_state["checklist_active"],
            "operator_name": _context_state["operator_name"],
            "operator_height": _context_state["operator_height"],
            "height_profile": _context_state["height_profile"],
        },
        "model": settings.openai_model,
        "router_model": settings.ollama_router_model,
    }


@app.get("/api/stats")
async def stats():
    """統計資料"""
    records = _stats["latency_records"]
    avg_latency = sum(records) / len(records) if records else 0
    return {
        "total_requests": _stats["total_requests"],
        "avg_latency_ms": round(avg_latency, 1),
        "agent_stats": _stats["agent_stats"],
        "language_stats": _stats["language_stats"],
    }


@app.post("/api/voice/upload")
async def voice_upload(file: UploadFile = File(...)):
    """上傳音訊檔並轉錄"""
    try:
        import tempfile, numpy as np
        import soundfile as sf

        contents = await file.read()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        audio, sr = sf.read(tmp_path)
        os.unlink(tmp_path)

        # 重採樣到 16kHz（如需要）
        if sr != 16000:
            import scipy.signal as signal
            samples = int(len(audio) * 16000 / sr)
            audio = signal.resample(audio, samples)

        from voice.stt import stt_service
        if stt_service.engine is None:
            stt_service.initialize()

        result = stt_service.transcribe(audio.astype(np.float32))
        if result:
            return {"text": result.text, "engine": result.engine, "latency_ms": result.latency_ms}
        return {"text": "", "engine": "none", "latency_ms": 0}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/stats/reset")
async def reset_stats():
    _stats["total_requests"] = 0
    _stats["latency_records"].clear()
    _stats["agent_stats"].clear()
    _stats["language_stats"].clear()
    return {"ok": True}


# ── 喚醒詞設定 API ────────────────────────────────────────────────────────

class WakeSettingsRequest(BaseModel):
    wake_word: Optional[str] = None
    tts_enabled: Optional[bool] = None


@app.get("/api/wake/settings")
async def get_wake_settings():
    return {
        "wake_word": _wake_settings["wake_word"],
        "tts_enabled": _wake_settings["tts_enabled"],
        "listening": _wake_settings["listening"],
    }


@app.post("/api/wake/settings")
async def update_wake_settings(req: WakeSettingsRequest):
    """更新喚醒詞設定，若喚醒詞改變則重啟監聽"""
    changed = False

    if req.tts_enabled is not None:
        _wake_settings["tts_enabled"] = req.tts_enabled

    if req.wake_word is not None and req.wake_word.strip():
        new_word = req.wake_word.strip()
        if new_word != _wake_settings["wake_word"]:
            _wake_settings["wake_word"] = new_word
            changed = True

    # 持久化儲存
    _save_wake_config({
        "wake_word": _wake_settings["wake_word"],
        "tts_enabled": _wake_settings["tts_enabled"],
    })

    if changed:
        # 停止舊的 detector
        old = _wake_settings.get("_detector")
        if old:
            try:
                old.stop()
            except Exception:
                pass
        _wake_settings["listening"] = False
        # 重啟
        t = threading.Thread(target=_start_wake_listener, daemon=True, name="WakeListener")
        t.start()

    return {
        "wake_word": _wake_settings["wake_word"],
        "tts_enabled": _wake_settings["tts_enabled"],
        "listening": _wake_settings["listening"],
        "restarted": changed,
    }


# ── 喚醒詞 WebSocket ──────────────────────────────────────────────────────

@app.websocket("/ws/wake")
async def ws_wake(websocket: WebSocket):
    """前端訂閱喚醒詞事件推送"""
    await websocket.accept()
    _wake_clients.add(websocket)
    # 立即推送當前狀態
    await websocket.send_json({
        "type": "wake_status",
        "listening": _wake_settings["listening"],
        "wake_word": _wake_settings["wake_word"],
    })
    try:
        while True:
            await websocket.receive_text()  # 保持連線
    except WebSocketDisconnect:
        _wake_clients.discard(websocket)


# ── 語音模式 WebSocket ───────────────────────────────────────────────────

_active_voice_ws = None

@app.websocket("/ws/voice")
async def ws_voice(websocket: WebSocket):
    """
    即時語音互動 WebSocket
    """
    global _active_voice_ws
    import numpy as np
    from voice.vad import VADDetector, VADEvent
    from voice.stt import stt_service

    if _active_voice_ws is not None:
        print("⚠️ 阻擋重複的 /ws/voice 連線 (已有活躍連線)")
        try:
            await websocket.close(reason="Already active")
        except:
            pass
        return

    await websocket.accept()
    _active_voice_ws = websocket
    print("✅ /ws/voice 連線建立")

    # 停止喚醒詞監聽，釋放麥克風給瀏覽器用
    wake_detector = _wake_settings.get("_detector")
    if wake_detector:
        print("⏸️ 正在停止喚醒詞監聽以釋放麥克風...")
        await asyncio.get_event_loop().run_in_executor(None, wake_detector.stop)
        print("⏸️ 喚醒詞監聽已暫停（語音模式佔用麥克風）")

    # 初始化 STT（懶載入）
    if stt_service.engine is None:
        print("📥 /ws/voice: 初始化 STT...")
        await asyncio.get_event_loop().run_in_executor(None, stt_service.initialize)
        print(f"✅ /ws/voice: STT 引擎 = {stt_service.engine_name}")

    # VAD chunk size: 20ms @ 16kHz 16-bit = 640 bytes
    VAD_CHUNK = 640
    # 修改停頓觸發秒數為 2 秒 (2000ms)，並調高能量門檻防止底噪
    from voice.vad import VADState
    vad = VADDetector(silence_threshold_ms=2000, energy_threshold=0.015)
    audio_buffer: list[bytes] = []   # 完整語音段
    pcm_remainder = b""              # 未滿一個 VAD chunk 的殘餘
    is_interrupted = False
    processing = False               # 防止重複觸發
    total_bytes_received = 0
    chunk_count = 0
    last_activity_time = time.time()  # 用於5秒靜音判斷退出
    _tts_played_event = asyncio.Event()  # 前端播完 TTS 的通知

    async def send_state(state: str):
        try:
            await websocket.send_json({"type": "state", "state": state})
        except Exception:
            pass

    async def stream_tts(text: str, language: str):
        nonlocal is_interrupted, last_activity_time
        is_interrupted = False
        await send_state("speaking")
        try:
            async for chunk in tts_service.synthesize_stream(text, language):
                if is_interrupted:
                    break
                await websocket.send_bytes(chunk)
                last_activity_time = time.time()
            await websocket.send_json({"type": "tts_end"})
            # tts_played 由外層主迴圈收到後 set event
            # 這裡用 wait_for 等待，同時讓 asyncio event loop 可以處理其他事件
            _tts_played_event.clear()
            deadline = time.time() + 60.0
            while time.time() < deadline:
                try:
                    await asyncio.wait_for(
                        asyncio.shield(_tts_played_event.wait()), timeout=0.5
                    )
                    break  # 收到 tts_played
                except asyncio.TimeoutError:
                    last_activity_time = time.time()  # 持續更新，避免 timeout
        except Exception as e:
            print(f"⚠️ TTS 串流失敗: {e}")
        finally:
            last_activity_time = time.time()
            await send_state("listening")

    async def process_speech():
        """STT → MAS → TTS 流程"""
        nonlocal processing, last_activity_time
        processing = True
        try:
            await send_state("processing")
            raw_audio = b"".join(audio_buffer)
            audio_buffer.clear()
            vad.reset()

            print(f"🎙️ process_speech: 音訊長度 {len(raw_audio)} bytes ({len(raw_audio)/32000:.1f}s)")
            audio_np = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32) / 32768.0

            stt_result = await asyncio.get_event_loop().run_in_executor(
                None, stt_service.transcribe, audio_np
            )
            if not stt_result or not stt_result.text.strip():
                print("⚠️ STT 無結果")
                await send_state("listening")
                return

            transcript = stt_result.text.strip()
            print(f"📝 STT 結果: {transcript}")
            await websocket.send_json({"type": "transcript", "text": transcript})

            mas_result = await asyncio.get_event_loop().run_in_executor(
                None, _run_mas, transcript
            )
            await websocket.send_json({
                "type": "response",
                "text": mas_result["response"],
                "route": mas_result.get("route"),
                "model_used": mas_result.get("model_used"),
                "latency_ms": mas_result.get("latency_ms"),
                "tool_name": mas_result.get("tool_name"),
            })

            lang = mas_result.get("detected_language", "zh")
            await stream_tts(mas_result["response"], lang)
        except RuntimeError as e:
            if "Unexpected ASGI message" in str(e) or "websocket.send" in str(e):
                print("🔌 語音處理完成，但前端已斷開連線 (正常關閉)")
            else:
                print(f"⚠️ process_speech 執行時期錯誤: {e}")
        except Exception as e:
            print(f"⚠️ process_speech 錯誤: {e}")
            import traceback; traceback.print_exc()
            await send_state("listening")
        finally:
            last_activity_time = time.time()  # TTS完成後，重新開始計算5秒靜音
            processing = False

    try:
        await send_state("listening")
        last_activity_time = time.time()

        while True:
            # 靜音5秒退出語音模式判定
            if not processing and vad.state == VADState.IDLE:
                if time.time() - last_activity_time >= 5.0:
                    print("⏱️ 靜音達到5秒，自動跳出語音模式")
                    try:
                        await websocket.send_json({"type": "timeout"})
                    except Exception:
                        pass
                    break # 結束連接，觸發 finally 切回 wake listener

            try:
                # 設定短延遲 wait_for，讓外層可以不斷檢查 5 秒靜音
                data = await asyncio.wait_for(websocket.receive(), timeout=0.2)
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                print("🔌 /ws/voice 斷線")
                break
            except Exception as e:
                print(f"⚠️ /ws/voice receive 錯誤: {e}")
                break

            msg_type = data.get("type", "")

            if msg_type == "websocket.disconnect":
                print("🔌 /ws/voice disconnect")
                break
            # 文字指令（interrupt / tts_played）
            if msg_type == "websocket.receive" and data.get("text"):
                try:
                    cmd = json.loads(data["text"])
                    if cmd.get("type") == "interrupt":
                        is_interrupted = True
                    elif cmd.get("type") == "tts_played":
                        last_activity_time = time.time()  # 前端播完 TTS，重置靜音計時
                        _tts_played_event.set()
                except Exception:
                    pass
                continue

            # 二進位 PCM
            if msg_type == "websocket.receive" and data.get("bytes"):
                if processing:
                    continue

                raw = data["bytes"]
                total_bytes_received += len(raw)
                chunk_count += 1

                # 每 100 個 chunk 印一次統計（約 2 秒）
                if chunk_count % 100 == 0:
                    print(f"📊 /ws/voice: 已收 {chunk_count} chunks, {total_bytes_received} bytes")

                pcm_remainder += raw
                audio_buffer.append(raw)

                # 切成固定 640-byte chunks 餵給 VAD
                while len(pcm_remainder) >= VAD_CHUNK:
                    chunk = pcm_remainder[:VAD_CHUNK]
                    pcm_remainder = pcm_remainder[VAD_CHUNK:]
                    vad_result = vad.process_chunk(chunk, sample_rate=16000, sample_width=2)

                    # 只要VAD狀態不是IDLE(正在講話或尾聲)，就更新活動時間
                    if vad.state != VADState.IDLE:
                        last_activity_time = time.time()

                    # 印出能量（每 50 個 VAD chunk 印一次）
                    if chunk_count % 50 == 0:
                        audio_np_dbg = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
                        energy = float(np.sqrt(np.mean(audio_np_dbg ** 2)))
                        print(f"   🔊 VAD state={vad.state.value}, energy={energy:.4f}, event={vad_result.event.value}")

                    if vad_result.event == VADEvent.SPEECH_START:
                        print("🗣️ VAD: SPEECH_START")
                        await send_state("speech_detected")

                    elif vad_result.event == VADEvent.SPEECH_END:
                        print("🔇 VAD: SPEECH_END → 觸發 process_speech")
                        last_activity_time = time.time()
                        asyncio.ensure_future(process_speech())
                        break

    except Exception as e:
        print(f"⚠️ /ws/voice 錯誤: {e}")
        import traceback; traceback.print_exc()
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        if _active_voice_ws == websocket:
            _active_voice_ws = None
        # 語音模式結束，恢復喚醒詞監聽
        print("▶️ 語音模式結束，恢復喚醒詞監聽")
        t = threading.Thread(target=_start_wake_listener, daemon=True, name="WakeListener")
        t.start()


# ── WebSocket ─────────────────────────────────────────────────────────────

@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    """
    WebSocket 即時對話

    Client 送：{"message": "..."}
    Server 回：{"type": "thinking"} → {"type": "result", ...data}
    """
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            user_input = payload.get("message", "").strip()
            if not user_input:
                continue

            # 通知前端「處理中」
            await websocket.send_json({"type": "thinking", "message": user_input})

            # 在執行緒池執行（避免阻塞事件迴圈）
            result = await asyncio.get_event_loop().run_in_executor(
                None, _run_mas, user_input
            )

            await websocket.send_json({"type": "result", **result})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


# ── 靜態檔案（生產模式）────────────────────────────────────────────────────

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index = os.path.join(FRONTEND_DIST, "index.html")
        return FileResponse(index)
