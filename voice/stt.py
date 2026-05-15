# voice/stt.py
"""
語音轉文字 (Speech-to-Text) 模組
支援 SenseVoice（推薦）和 Whisper（降級）
"""

import os
import tempfile
import time
from typing import Optional
from dataclasses import dataclass

# 嘗試導入音訊處理套件
try:
    import sounddevice as sd
    import numpy as np
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("⚠️ sounddevice/numpy 未安裝，語音輸入功能將無法使用")
    print("   請執行: pip install sounddevice numpy")

# 嘗試載入 SenseVoice (優先)
try:
    from funasr import AutoModel as FunASRModel
    SENSEVOICE_AVAILABLE = True
except ImportError:
    SENSEVOICE_AVAILABLE = False

# 嘗試載入 Whisper (降級)
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

from config.settings import settings
from utils.language import language_processor


@dataclass
class STTResult:
    """STT 結果"""
    text: str
    language: str
    confidence: float
    latency_ms: float
    engine: str  # "sensevoice" or "whisper"


class SenseVoiceSTT:
    """
    SenseVoice 語音轉文字（推薦引擎）
    
    比 Whisper-Large 快 15x，中文辨識精準度更高。
    使用非自回歸架構，支援中/英/日/韓/粵。
    """
    
    def __init__(self):
        self.model = None
        self.sample_rate = 16000
    
    def load_model(self) -> bool:
        if not SENSEVOICE_AVAILABLE:
            print("❌ funasr 套件未安裝，請執行: pip install funasr")
            return False
        try:
            print("📥 正在載入 SenseVoice-Small 模型...")
            # 優先使用本地模型，備援 ModelScope 下載
            import os
            local_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'SenseVoiceSmall')
            model_path = local_path if os.path.exists(local_path) else "iic/SenseVoiceSmall"
            self.model = FunASRModel(
                model=model_path,
                device="cpu",
                disable_update=True,
            )
            print("✅ SenseVoice 模型載入完成")
            return True
        except Exception as e:
            print(f"❌ SenseVoice 載入失敗: {e}")
            return False
    
    def transcribe(self, audio: np.ndarray) -> Optional[STTResult]:
        if self.model is None:
            if not self.load_model():
                return None
        
        start_time = time.perf_counter()
        
        try:
            # 寫入暫存檔（funasr 需要檔案路徑）
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                import soundfile as sf
                sf.write(f.name, audio, self.sample_rate)
                temp_path = f.name
            
            result = self.model.generate(
                input=temp_path,
                language="auto",  # 自動偵測
                use_itn=True,     # 反向文字正規化
            )
            
            os.unlink(temp_path)
            
            latency = (time.perf_counter() - start_time) * 1000
            
            if result and len(result) > 0:
                text = result[0].get("text", "").strip()
                text = self._clean_text(text)
                # SenseVoice 輸出為簡體，轉換為繁體
                text = language_processor.to_traditional_chinese(text)
                # 修正語音辨識常見錯誤詞彙
                text = self._correct_vocab(text)
                return STTResult(
                    text=text,
                    language="auto",
                    confidence=0.95,
                    latency_ms=latency,
                    engine="sensevoice"
                )
            return None
            
        except Exception as e:
            print(f"❌ SenseVoice 轉錄失敗: {e}")
            return None
    
    def _clean_text(self, text: str) -> str:
        """清理 SenseVoice 輸出（移除情緒/事件標籤）"""
        import re
        # 移除 <|....|> 風格的標籤
        text = re.sub(r'<\|[^>]*\|>', '', text)
        return text.strip()

    def _correct_vocab(self, text: str) -> str:
        """修正語音辨識常見錯誤詞彙"""
        corrections = {
            "元速": "原速",
            "元素": "原速",
            "原素": "原速",
        }
        for wrong, correct in corrections.items():
            text = text.replace(wrong, correct)
        return text


class WhisperSTT:
    """Whisper 語音轉文字（降級引擎）"""
    
    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.whisper_model
        self.model = None
        self.sample_rate = 16000
        
    def load_model(self) -> bool:
        if not WHISPER_AVAILABLE:
            print("❌ Whisper 套件未安裝")
            return False
        try:
            print(f"📥 正在載入 Whisper {self.model_name} 模型...")
            self.model = whisper.load_model(self.model_name)
            print(f"✅ Whisper 模型載入完成")
            return True
        except Exception as e:
            print(f"❌ Whisper 載入失敗: {e}")
            return False
    
    def transcribe(self, audio: np.ndarray) -> Optional[STTResult]:
        if self.model is None:
            if not self.load_model():
                return None
        
        start_time = time.perf_counter()
        
        try:
            result = self.model.transcribe(
                audio,
                fp16=False,
                language=None,       # 自動偵測語言
                initial_prompt="顯示卡組裝、機械手臂、SOP、伸出、夾取、放置、安全須知。Robot arm, assembly, SOP, safety.",
            )
            
            latency = (time.perf_counter() - start_time) * 1000
            
            return STTResult(
                text=result["text"].strip(),
                language=result.get("language", "zh"),
                confidence=1.0,
                latency_ms=latency,
                engine="whisper"
            )
        except Exception as e:
            print(f"❌ Whisper 轉錄失敗: {e}")
            return None


class STTService:
    """
    統一 STT 服務
    
    支援雙軌備援：優先使用 SenseVoice，若失敗或結果為空，自動降級使用 Whisper。
    """
    
    def __init__(self):
        self.engine = None  # 用於標示是否已初始化
        self.engine_name = "none"
        self.sample_rate = 16000
        self.sensevoice = None
        self.whisper = None
    
    def initialize(self) -> bool:
        """初始化可用引擎，優先 SenseVoice，併初始化 Whisper 作為備援"""
        success = False
        
        # 優先 SenseVoice
        if SENSEVOICE_AVAILABLE:
            sv = SenseVoiceSTT()
            if sv.load_model():
                self.sensevoice = sv
                success = True
                self.engine_name = "sensevoice+whisper"
        
        # 備援 Whisper
        if WHISPER_AVAILABLE:
            ws = WhisperSTT()
            if ws.load_model():
                self.whisper = ws
                success = True
                if self.engine_name == "none":
                    self.engine_name = "whisper"
        
        if success:
            self.engine = "hybrid"  # 標示已經初始化完成
            return True
        
        print("❌ 無可用 STT 引擎。請安裝: pip install funasr 或 pip install openai-whisper")
        return False
    
    def record_audio(self, duration: float = 10.0) -> Optional[np.ndarray]:
        """錄製音訊"""
        if not AUDIO_AVAILABLE:
            return None
        try:
            print(f"🎤 開始錄音 ({duration}秒)...")
            audio = sd.rec(
                int(duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1, dtype='float32'
            )
            sd.wait()
            print("✅ 錄音完成")
            return audio.flatten()
        except Exception as e:
            print(f"❌ 錄音失敗: {e}")
            return None
    
    def record_until_enter(self) -> Optional[np.ndarray]:
        """
        錄音直到按下 Enter 鍵
        用於 CLI 'v' 指令模式
        """
        if not AUDIO_AVAILABLE:
            return None
        
        import threading
        
        chunks = []
        recording = True
        
        def _record():
            nonlocal recording
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1, dtype='float32',
                blocksize=int(self.sample_rate * 0.1)  # 100ms chunks
            )
            stream.start()
            while recording:
                data, _ = stream.read(int(self.sample_rate * 0.1))
                chunks.append(data.flatten())
            stream.stop()
            stream.close()
        
        thread = threading.Thread(target=_record, daemon=True)
        thread.start()
        
        print("🔴 錄音中... 按 Enter 停止")
        try:
            input()
        except EOFError:
            pass
        
        recording = False
        thread.join(timeout=1.0)
        
        if chunks:
            return np.concatenate(chunks)
        return None
    
    def transcribe(self, audio: np.ndarray) -> Optional[STTResult]:
        """轉錄音訊 (具備 SenseVoice -> Whisper 備援機制)"""
        if self.engine is None:
            if not self.initialize():
                return None
                
        # 1. 嘗試優先使用 SenseVoice
        if self.sensevoice is not None:
            result = self.sensevoice.transcribe(audio)
            if result and result.text and result.text.strip():
                result.text = self._correct_vocab(result.text)
                return result
            else:
                print("⚠️ SenseVoice 辨識結果為空或失敗，降級使用 Whisper...")
                
        # 2. 備援使用 Whisper
        if self.whisper is not None:
            result = self.whisper.transcribe(audio)
            if result and result.text and result.text.strip():
                result.text = self._correct_vocab(result.text)
                return result
                
        return None

    def _correct_vocab(self, text: str) -> str:
        """修正語音辨識常見錯誤詞彙"""
        corrections = {
            "元速": "原速",
            "元素": "原速",
            "原素": "原速",
        }
        for wrong, correct in corrections.items():
            text = text.replace(wrong, correct)
        return text
    
    def listen_and_transcribe(self, duration: float = 10.0) -> Optional[STTResult]:
        """錄音並轉錄（一站式）"""
        audio = self.record_audio(duration)
        if audio is None:
            return None
        return self.transcribe(audio)
    
    def listen_until_enter_and_transcribe(self) -> Optional[STTResult]:
        """按 Enter 停止錄音並轉錄（CLI v 模式）"""
        audio = self.record_until_enter()
        if audio is None:
            return None
        return self.transcribe(audio)


# 全域 STT 服務實例
stt_service = STTService()
