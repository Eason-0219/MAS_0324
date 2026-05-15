# voice/vad.py
"""
語音活動偵測 (Voice Activity Detection)
支援串流模式：逐 chunk 分析，維護狀態機

狀態機：
  IDLE → (偵測到語音) → SPEECH → (靜音 > threshold) → IDLE
"""

import time as _time
import threading
import numpy as np
from typing import Optional, Callable
from enum import Enum
from dataclasses import dataclass, field

try:
    import sounddevice as sd
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

try:
    import webrtcvad
    WEBRTCVAD_AVAILABLE = True
except ImportError:
    WEBRTCVAD_AVAILABLE = False

from config.settings import settings


class VADState(Enum):
    IDLE = "idle"           # 等待語音
    SPEECH = "speech"       # 語音進行中
    TRAILING = "trailing"   # 語音可能結束（靜音計時中）


class VADEvent(Enum):
    NONE = "none"
    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"


@dataclass
class VADResult:
    """單次 chunk 的 VAD 結果"""
    is_speech: bool
    event: VADEvent = VADEvent.NONE
    speech_duration_ms: float = 0
    silence_duration_ms: float = 0


class VADDetector:
    """
    串流式 VAD 偵測器

    使用方式：
        vad = VADDetector()
        for chunk in audio_stream:
            result = vad.process_chunk(chunk, sample_rate=16000)
            if result.event == VADEvent.SPEECH_END:
                # 語音結束，可以送去 STT
    """

    def __init__(
        self,
        silence_threshold_ms: float = None,
        speech_threshold_ms: float = 300,
        energy_threshold: float = 0.015,
        aggressiveness: int = 3,
    ):
        self.silence_threshold_ms = silence_threshold_ms or (
            getattr(settings, 'vad_silence_duration', 1.5) * 1000
        )
        self.speech_threshold_ms = speech_threshold_ms
        self.energy_threshold = energy_threshold

        # 狀態機
        self.state = VADState.IDLE
        self._speech_start_ms = 0
        self._silence_start_ms = 0
        self._total_ms = 0

        # WebRTC VAD
        self._webrtc_vad = None
        if WEBRTCVAD_AVAILABLE:
            try:
                self._webrtc_vad = webrtcvad.Vad(aggressiveness)
            except Exception:
                pass

    def reset(self):
        """重置狀態機"""
        self.state = VADState.IDLE
        self._speech_start_ms = 0
        self._silence_start_ms = 0
        self._total_ms = 0

    def process_chunk(
        self,
        audio_chunk: bytes,
        sample_rate: int = 16000,
        sample_width: int = 2,
    ) -> VADResult:
        """
        處理單一音訊 chunk

        Args:
            audio_chunk: PCM 音訊 bytes (16-bit signed, mono)
            sample_rate: 取樣率 (16000)
            sample_width: 每個 sample 的 bytes 數 (2 = 16-bit)

        Returns:
            VADResult 包含是否有語音和事件
        """
        chunk_duration_ms = len(audio_chunk) / (sample_rate * sample_width) * 1000
        self._total_ms += chunk_duration_ms

        is_speech = self._detect_speech(audio_chunk, sample_rate)

        event = VADEvent.NONE
        speech_dur = 0
        silence_dur = 0

        if self.state == VADState.IDLE:
            if is_speech:
                self._speech_start_ms = self._total_ms
                self.state = VADState.SPEECH
                # 等累積到 speech_threshold 才算正式開始
            silence_dur = self._total_ms - self._silence_start_ms if self._silence_start_ms else 0

        elif self.state == VADState.SPEECH:
            speech_dur = self._total_ms - self._speech_start_ms
            if speech_dur > 15000.0:  # Force end if speaking > 15 seconds
                event = VADEvent.SPEECH_END
                self.state = VADState.IDLE
                self._speech_start_ms = 0
                self._silence_start_ms = self._total_ms
            elif not is_speech:
                self._silence_start_ms = self._total_ms
                self.state = VADState.TRAILING
            elif speech_dur >= self.speech_threshold_ms and event == VADEvent.NONE:
                # 持續說話達到閾值 → 確認語音開始
                event = VADEvent.SPEECH_START

        elif self.state == VADState.TRAILING:
            speech_dur = self._total_ms - self._speech_start_ms
            silence_dur = self._total_ms - self._silence_start_ms

            if is_speech:
                # 又偵測到語音 → 回到 SPEECH
                self.state = VADState.SPEECH
                self._silence_start_ms = 0
            elif silence_dur >= self.silence_threshold_ms:
                # 靜音超過閾值 → 語音結束
                event = VADEvent.SPEECH_END
                self.state = VADState.IDLE
                self._speech_start_ms = 0
                self._silence_start_ms = self._total_ms

        return VADResult(
            is_speech=is_speech,
            event=event,
            speech_duration_ms=speech_dur,
            silence_duration_ms=silence_dur,
        )

    def _detect_speech(self, audio_chunk: bytes, sample_rate: int) -> bool:
        """偵測單一 chunk 是否包含語音"""
        # 優先用 WebRTC VAD
        if self._webrtc_vad and len(audio_chunk) in [320, 640, 960]:
            # webrtcvad 需要 10ms/20ms/30ms 的 chunk (16kHz: 320/640/960 bytes)
            try:
                return self._webrtc_vad.is_speech(audio_chunk, sample_rate)
            except Exception:
                pass

        # 降級：能量偵測
        try:
            audio_np = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
            energy = np.sqrt(np.mean(audio_np ** 2))
            return energy > self.energy_threshold
        except Exception:
            return False

    def record_until_silence(
        self,
        max_duration: float = 15.0,
        silence_timeout: float = 5.0,
        sample_rate: int = 16000,
        on_speech_start: Optional[Callable] = None,
        on_speech_end: Optional[Callable] = None,
    ) -> Optional[np.ndarray]:
        """
        錄音直到偵測到靜音（或超過最大時間）。
        喚醒後呼叫此方法錄取用戶說的話。

        Args:
            max_duration:   最長錄音秒數（超過強制結束）
            silence_timeout: 靜音幾秒後結束（預設 5 秒）
            sample_rate:    取樣率
            on_speech_start: 偵測到語音開始時的 callback
            on_speech_end:   偵測到靜音結束時的 callback

        Returns:
            numpy float32 音訊陣列，或 None（無音訊/不可用）
        """
        if not AUDIO_AVAILABLE:
            print("❌ sounddevice 未安裝，無法錄音")
            return None

        chunks = []
        speech_started = False
        silence_start = None
        start_time = _time.time()

        # 能量偵測閾值（簡單備援，不依賴 webrtcvad）
        energy_threshold = self.energy_threshold

        stop_event = threading.Event()

        def _record_loop():
            nonlocal speech_started, silence_start
            chunk_size = int(sample_rate * 0.1)  # 100ms chunks
            max_energy_seen = 0.0

            try:
                with sd.InputStream(
                    samplerate=sample_rate,
                    channels=1,
                    dtype="float32",
                    blocksize=chunk_size,
                ) as stream:
                    print(f"🎙️ VAD 串流已開啟 (閾值={energy_threshold:.4f})")
                    while not stop_event.is_set():
                        data, _ = stream.read(chunk_size)
                        chunk = data.flatten()
                        chunks.append(chunk.copy())

                        # 能量偵測
                        energy = float(np.sqrt(np.mean(chunk ** 2)))
                        if energy > max_energy_seen:
                            max_energy_seen = energy
                            print(f"   📊 新最高能量: {energy:.4f}")

                        is_speech = energy > energy_threshold

                        if is_speech:
                            if not speech_started:
                                speech_started = True
                                silence_start = None
                                if on_speech_start:
                                    try:
                                        on_speech_start()
                                    except Exception:
                                        pass
                            else:
                                silence_start = None  # 重置靜音計時
                        else:
                            if speech_started and silence_start is None:
                                silence_start = _time.time()

            except Exception as e:
                print(f"⚠️ 錄音串流錯誤: {e}")
                import traceback; traceback.print_exc()

        thread = threading.Thread(target=_record_loop, daemon=True)
        thread.start()

        # 主執行緒監控停止條件
        while True:
            _time.sleep(0.1)
            elapsed = _time.time() - start_time

            # 超過最大時間
            if elapsed >= max_duration:
                break

            # 靜音超過 silence_timeout（且已有語音）
            if speech_started and silence_start is not None:
                if _time.time() - silence_start >= silence_timeout:
                    if on_speech_end:
                        try:
                            on_speech_end()
                        except Exception:
                            pass
                    break

            # 5 秒內完全沒有語音也退出
            if not speech_started and elapsed >= silence_timeout:
                break

        stop_event.set()
        thread.join(timeout=1.0)

        if not chunks:
            return None

        audio = np.concatenate(chunks)
        # 只回傳有語音的部分（去掉純靜音開頭）
        return audio if speech_started else None


# 全域實例
vad_detector = VADDetector()
