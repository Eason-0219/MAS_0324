# voice/wake_listener.py
"""
喚醒詞偵測 + 持續監聽模組

策略：背景執行緒持續錄音（每 N 秒一個片段）
      → Whisper 轉錄 → 檢查是否包含喚醒詞
      → 命中後播放提示音 + VAD 錄音 → 送入 MAS 處理

此方案完全基於 whisper + sounddevice，無需額外套件，
且 100% 支援中文自訂喚醒詞「嘿 CoinAI」。
"""

import time
import threading
import numpy as np
from typing import Optional, Callable

try:
    import sounddevice as sd
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

try:
    import whisper as _whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

from config.settings import settings


class WakeWordDetector:
    """
    喚醒詞偵測器（Whisper 分段辨識方案）

    流程：
      背景執行緒持續錄音（每 check_interval 秒一段）
      → Whisper 轉錄 → 檢查是否包含喚醒詞
      → 命中 → 觸發 on_wake callback
    """

    # 喚醒詞的多種可能寫法（容錯）
    WAKE_ALIASES = [
        "嘿coinai", "嘿 coinai", "hey coinai", "heycoinai",
        "嘿coin", "嘿 coin", "嗨coinai", "嗨 coinai",
        "coinai", "coin ai",
    ]

    def __init__(
        self,
        wake_word: str = None,
        check_interval: float = None,
    ):
        self.wake_word = (wake_word or settings.wake_word).lower()
        self.check_interval = check_interval or settings.wake_word_check_interval
        self.sample_rate = 16000

        self._model = None          # Whisper 模型（延遲載入）
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._listening = False

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------

    def initialize(self) -> bool:
        """載入 Whisper 模型（tiny 最快，適合喚醒詞偵測）"""
        if not WHISPER_AVAILABLE:
            print("❌ openai-whisper 未安裝，請執行: pip install openai-whisper")
            return False
        if not AUDIO_AVAILABLE:
            print("❌ sounddevice 未安裝，請執行: pip install sounddevice")
            return False
        if self._model is not None:
            return True
        try:
            print("📥 載入 Whisper tiny 模型（喚醒詞偵測用）...")
            self._model = _whisper.load_model("tiny")
            print(f"✅ 喚醒詞偵測器就緒，喚醒詞：「{settings.wake_word}」")
            return True
        except Exception as e:
            print(f"❌ Whisper 載入失敗: {e}")
            return False

    def start(self, on_wake: Callable[[], None]):
        """
        啟動背景監聽

        Args:
            on_wake: 偵測到喚醒詞後的 callback（在背景執行緒中呼叫）
        """
        if self._listening:
            print("⚠️ 喚醒詞監聽已在執行中")
            return

        if not self.initialize():
            return

        self._stop_event.clear()
        self._listening = True
        self._thread = threading.Thread(
            target=self._listen_loop,
            args=(on_wake,),
            daemon=True,
            name="WakeWordListener",
        )
        self._thread.start()
        print(f"👂 喚醒詞監聽中... 說「{settings.wake_word}」來啟動")

    def stop(self):
        """停止監聽"""
        self._stop_event.set()
        self._listening = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self.check_interval + 1.0)
        print("⏹️ 喚醒詞監聽已停止")

    def is_listening(self) -> bool:
        return self._listening

    # ------------------------------------------------------------------
    # 內部邏輯
    # ------------------------------------------------------------------

    def _listen_loop(self, on_wake: Callable):
        """背景監聽主迴圈"""
        try:
            while not self._stop_event.is_set():
                # 錄製一個短片段
                audio = self._record_chunk(self.check_interval)
                if audio is None:
                    continue

                # 快速轉錄
                text = self._transcribe_quick(audio)
                if text and self._check_wake_word(text):
                    print(f"\n✨ 喚醒詞偵測到！(辨識：「{text.strip()}」)")
                    # 暫停錄音，讓 on_wake callback 獨佔麥克風
                    self._paused = True
                    try:
                        on_wake()
                    except Exception as e:
                        print(f"⚠️ 喚醒 callback 錯誤: {e}")
                    finally:
                        self._paused = False

        except Exception as e:
            print(f"❌ 喚醒詞監聽迴圈錯誤: {e}")
        finally:
            self._listening = False

    def _record_chunk(self, duration: float) -> Optional[np.ndarray]:
        """錄製固定長度音訊片段"""
        try:
            audio = sd.rec(
                int(duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
            )
            # 分段等待，讓 stop_event 可以中斷
            import time as _t
            steps = int(duration / 0.1)
            for _ in range(steps):
                if self._stop_event.is_set():
                    sd.stop()
                    return None
                _t.sleep(0.1)
            sd.wait()
            return audio.flatten()
        except Exception as e:
            print(f"⚠️ 錄音片段失敗: {e}")
            return None

    def _transcribe_quick(self, audio: np.ndarray) -> str:
        """快速轉錄（tiny 模型，無語言限制）"""
        if self._model is None:
            return ""
        try:
            result = self._model.transcribe(
                audio,
                fp16=False,
                language=None,      # 自動偵測，支援中英混合
                temperature=0,
                condition_on_previous_text=False,
            )
            return result.get("text", "").strip()
        except Exception:
            return ""

    def _check_wake_word(self, text: str) -> bool:
        """檢查轉錄文字是否包含喚醒詞（容錯匹配）"""
        normalized = text.lower().replace(" ", "")
        # 檢查主喚醒詞
        if self.wake_word.replace(" ", "") in normalized:
            return True
        # 檢查別名
        for alias in self.WAKE_ALIASES:
            if alias.replace(" ", "") in normalized:
                return True
        return False


# 全域實例
wake_listener = WakeWordDetector()
