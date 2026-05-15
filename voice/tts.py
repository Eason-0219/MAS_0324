# voice/tts.py
"""
文字轉語音 (Text-to-Speech) 模組
支援引擎：
  1. ElevenLabs API (高品質，需付費 API Key)
  2. Edge TTS (免費，品質也不錯)

新增 synthesize_to_bytes() 方法，用於 WebSocket 串流回傳音訊
"""

import os
import io
import time
import asyncio
import tempfile
from typing import Optional, AsyncGenerator
from dataclasses import dataclass

try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import VoiceSettings
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

from config.settings import settings


@dataclass
class TTSResult:
    """TTS 結果"""
    audio_data: Optional[bytes]
    audio_path: Optional[str]
    latency_ms: float
    success: bool
    error: Optional[str] = None


class ElevenLabsTTS:
    """
    ElevenLabs 文字轉語音服務
    """
    VOICE_CONFIG = {
        "zh": {"voice_id": "21m00Tcm4TlvDq8ikWAM", "stability": 0.5, "similarity_boost": 0.75},
        "en": {"voice_id": "21m00Tcm4TlvDq8ikWAM", "stability": 0.5, "similarity_boost": 0.75},
    }

    def __init__(self):
        self.api_key = settings.elevenlabs_api_key
        self.voice_id = getattr(settings, 'elevenlabs_voice_id', '21m00Tcm4TlvDq8ikWAM')
        self.client = None
        self._pygame_initialized = False

    def initialize(self) -> bool:
        if not ELEVENLABS_AVAILABLE:
            return False
        if not self.api_key or self.api_key == "your-elevenlabs-api-key":
            return False
        try:
            if self.client is None:
                self.client = ElevenLabs(api_key=self.api_key)
            if PYGAME_AVAILABLE and not self._pygame_initialized:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                self._pygame_initialized = True
            return True
        except Exception as e:
            print(f"❌ ElevenLabs 初始化失敗: {e}")
            return False

    def synthesize_to_bytes(self, text: str, language: str = "zh") -> TTSResult:
        """合成語音並回傳 MP3 bytes（用於 WebSocket 回傳）"""
        if not self.initialize():
            return TTSResult(None, None, 0, False, "ElevenLabs 初始化失敗")

        start_time = time.perf_counter()
        try:
            config = self.VOICE_CONFIG.get(language, self.VOICE_CONFIG["zh"])
            audio_stream = self.client.text_to_speech.convert(
                text=text,
                voice_id=self.voice_id,
                model_id="eleven_flash_v2_5",
                voice_settings=VoiceSettings(
                    stability=config["stability"],
                    similarity_boost=config["similarity_boost"]
                ),
                output_format="mp3_44100_128"
            )

            audio_bytes = b""
            for chunk in audio_stream:
                if chunk:
                    audio_bytes += chunk

            latency = (time.perf_counter() - start_time) * 1000
            return TTSResult(audio_bytes, None, latency, True)

        except Exception as e:
            return TTSResult(None, None, 0, False, str(e))

    def speak(self, text: str, language: str = "zh") -> bool:
        """合成並直接播放 (Blocking, 流式寫入)"""
        start_time = time.perf_counter()
        
        if not self.initialize():
            return False
            
        if not text:
            return False

        temp_filename = f"temp_tts_{int(time.time())}.mp3"
        
        try:
            config = self.VOICE_CONFIG.get(language, self.VOICE_CONFIG["zh"])
            
            audio_stream = self.client.text_to_speech.convert(
                text=text,
                voice_id=self.voice_id,
                model_id="eleven_flash_v2_5",
                voice_settings=VoiceSettings(
                    stability=config["stability"],
                    similarity_boost=config["similarity_boost"]
                ),
                output_format="mp3_44100_128"
            )

            with open(temp_filename, "wb") as f:
                for chunk in audio_stream:
                    if chunk:
                        f.write(chunk)

            if PYGAME_AVAILABLE and self._pygame_initialized:
                pygame.mixer.music.load(temp_filename)
                pygame.mixer.music.play()
                
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
                
                pygame.mixer.music.unload()
                return True
            else:
                return True

        except Exception as e:
            print(f"❌ TTS 播放失敗: {e}")
            return False
            
        finally:
            if os.path.exists(temp_filename):
                try:
                    time.sleep(0.1) 
                    os.remove(temp_filename)
                except Exception:
                    pass


class EdgeTTS:
    """
    Edge TTS — 微軟免費語音合成引擎

    優點：免費、品質不錯、支援中日英多語
    """

    VOICE_MAP = {
        "zh": "zh-TW-HsiaoChenNeural",    # 台灣中文女聲
        "zh-CN": "zh-CN-XiaoyiNeural",     # 大陸中文女聲
        "en": "en-US-JennyNeural",         # 英文女聲
        "ja": "ja-JP-NanamiNeural",        # 日文女聲
    }

    async def synthesize_to_bytes(self, text: str, language: str = "zh") -> TTSResult:
        """合成語音並回傳 MP3 bytes"""
        if not EDGE_TTS_AVAILABLE:
            return TTSResult(None, None, 0, False, "edge-tts 未安裝")

        start_time = time.perf_counter()
        try:
            voice = self.VOICE_MAP.get(language, self.VOICE_MAP["zh"])
            communicate = edge_tts.Communicate(text, voice)

            audio_bytes = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]

            latency = (time.perf_counter() - start_time) * 1000
            if audio_bytes:
                return TTSResult(audio_bytes, None, latency, True)
            return TTSResult(None, None, latency, False, "無音訊輸出")

        except Exception as e:
            return TTSResult(None, None, 0, False, str(e))

    async def synthesize_stream(self, text: str, language: str = "zh") -> AsyncGenerator[bytes, None]:
        """串流合成 — 逐 chunk yield（用於即時播放）"""
        if not EDGE_TTS_AVAILABLE:
            return

        voice = self.VOICE_MAP.get(language, self.VOICE_MAP["zh"])
        communicate = edge_tts.Communicate(text, voice)

        async for chunk in communicate.stream():
            if chunk["type"] == "audio" and chunk["data"]:
                yield chunk["data"]


class TTSService:
    """
    TTS 統一服務 — 優先 ElevenLabs，降級 Edge TTS
    """

    def __init__(self):
        self.elevenlabs = ElevenLabsTTS()
        self.edge = EdgeTTS()
        self._engine = None  # "elevenlabs" | "edge" | None

    @property
    def engine(self):
        return self._engine

    def get_engine(self) -> str:
        """判斷可用引擎"""
        if self._engine:
            return self._engine

        if EDGE_TTS_AVAILABLE:
            self._engine = "edge"
            print("🔊 TTS 引擎: Edge TTS")
        elif self.elevenlabs.initialize():
            self._engine = "elevenlabs"
            print("🔊 TTS 引擎: ElevenLabs")
        else:
            self._engine = "none"
            print("⚠️ 無可用 TTS 引擎")

        return self._engine

    async def synthesize(self, text: str, language: str = "zh") -> TTSResult:
        """合成語音 — 自動選擇引擎"""
        engine = self.get_engine()

        if engine == "elevenlabs":
            # ElevenLabs 是同步呼叫，需要包在 executor 裡避免阻塞
            import asyncio
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self.elevenlabs.synthesize_to_bytes, text, language
            )
        elif engine == "edge":
            return await self.edge.synthesize_to_bytes(text, language)
        else:
            return TTSResult(None, None, 0, False, "無可用 TTS 引擎 (pip install edge-tts)")

    async def synthesize_stream(self, text: str, language: str = "zh") -> AsyncGenerator[bytes, None]:
        """串流合成"""
        engine = self.get_engine()

        if engine == "elevenlabs":
            import asyncio
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.elevenlabs.synthesize_to_bytes, text, language)
            
            if result.success and result.audio_data:
                # ElevenLabs 不支援真正的串流，分 chunk 回傳
                chunk_size = 4096
                for i in range(0, len(result.audio_data), chunk_size):
                    yield result.audio_data[i:i + chunk_size]
            else:
                print(f"⚠️ ElevenLabs TTS 合成失敗: {result.error}")
        elif engine == "edge":
            async for chunk in self.edge.synthesize_stream(text, language):
                yield chunk

    def speak(self, text: str, language: str = "zh") -> bool:
        """CLI 播放（向後相容）"""
        return self.elevenlabs.speak(text, language)


# 全域實例
tts_service = TTSService()