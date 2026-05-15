# utils/language.py
"""
語言處理模組

功能：
1. 語言偵測 - 使用 langid 自動識別輸入語言
2. 簡繁轉換 - 確保輸出為繁體中文
3. 多語言提示詞 - 根據語言生成對應提示
"""

import re
from typing import Optional, Tuple

try:
    import langid
    LANGID_AVAILABLE = True
except ImportError:
    LANGID_AVAILABLE = False
    print("⚠️ langid 未安裝，將使用簡化版語言偵測")

try:
    from opencc import OpenCC
    OPENCC_AVAILABLE = True
except ImportError:
    OPENCC_AVAILABLE = False
    print("⚠️ opencc 未安裝，簡繁轉換功能將受限")


class LanguageProcessor:
    """
    語言處理器
    
    支援的語言：
    - zh: 中文 (繁體/簡體)
    - en: 英文
    - vi: 越南文
    - id: 印尼文
    """
    
    # 語言名稱對照
    LANGUAGE_NAMES = {
        "zh": "中文",
        "zh-tw": "繁體中文",
        "zh-cn": "簡體中文",
        "en": "English",
        "vi": "Tiếng Việt",
        "id": "Bahasa Indonesia",
    }
    
    # 支援的語言列表
    SUPPORTED_LANGUAGES = {"zh", "en", "vi", "id"}
    
    def __init__(self):
        # 簡體轉繁體轉換器
        self.s2t_converter = None
        if OPENCC_AVAILABLE:
            try:
                self.s2t_converter = OpenCC('s2t')
            except Exception as e:
                print(f"⚠️ OpenCC 初始化失敗: {e}")
        
        # 設定 langid 只偵測支援的語言
        if LANGID_AVAILABLE:
            langid.set_languages(['zh', 'en', 'vi', 'id'])
    
    def detect_language(self, text: str) -> Tuple[str, float]:
        """
        使用 langid 偵測文字語言
        
        Args:
            text: 輸入文字
        
        Returns:
            (語言代碼, 信心度)
        """
        if not text or not text.strip():
            return "zh", 0.5
        
        # 使用 langid
        if LANGID_AVAILABLE:
            try:
                lang, confidence = langid.classify(text)
                
                # 標準化語言代碼
                if lang.startswith("zh"):
                    lang = "zh"
                
                # 確保是支援的語言
                if lang not in self.SUPPORTED_LANGUAGES:
                    lang = "en"  # 不支援的語言預設英文
                
                return lang, confidence
            except Exception:
                pass
        
        # 備用方案：簡單規則
        return self._simple_detect(text)
    
    def _simple_detect(self, text: str) -> Tuple[str, float]:
        """簡單的語言偵測（備用）"""
        # 中文字符
        chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
        # 越南文特殊字符
        vietnamese_pattern = re.compile(r'[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]', re.IGNORECASE)
        
        chinese_count = len(chinese_pattern.findall(text))
        vietnamese_count = len(vietnamese_pattern.findall(text))
        total_chars = len(text)
        
        if total_chars == 0:
            return "zh", 0.5
        
        if chinese_count / total_chars > 0.3:
            return "zh", 0.8
        
        if vietnamese_count / total_chars > 0.1:
            return "vi", 0.7
        
        # 印尼文關鍵字
        indonesian_keywords = ["apa", "bagaimana", "tolong", "saya", "ini", "itu", "dan", "atau"]
        text_lower = text.lower()
        if any(kw in text_lower for kw in indonesian_keywords):
            return "id", 0.6
        
        # 預設英文
        if re.search(r'[a-zA-Z]', text):
            return "en", 0.6
        
        return "zh", 0.5
    
    def get_language_instruction(self, language: str) -> str:
        """
        取得強制語言指示（用於 Prompt）
        
        Args:
            language: 語言代碼
        
        Returns:
            強制語言指示
        """
        instructions = {
            "zh": "⚠️ 你必須使用繁體中文回覆，不可使用其他語言。",
            "en": "⚠️ You MUST respond in English only. Do NOT use any other language.",
            "vi": "⚠️ Bạn PHẢI trả lời bằng tiếng Việt. KHÔNG được sử dụng ngôn ngữ khác.",
            "id": "⚠️ Anda HARUS menjawab dalam Bahasa Indonesia. JANGAN gunakan bahasa lain.",
        }
        return instructions.get(language, instructions["zh"])
    
    def get_response_instruction(self, language: str) -> str:
        """
        取得回應語言指示（簡短版）
        
        Args:
            language: 語言代碼
        
        Returns:
            回應語言指示文字
        """
        instructions = {
            "zh": "請使用繁體中文回答。",
            "en": "Please respond in English.",
            "vi": "Vui lòng trả lời bằng tiếng Việt.",
            "id": "Silakan jawab dalam Bahasa Indonesia.",
        }
        return instructions.get(language, instructions["zh"])
    
    def to_traditional_chinese(self, text: str) -> str:
        """將簡體中文轉換為繁體中文"""
        if not text:
            return text
        
        if self.s2t_converter:
            try:
                return self.s2t_converter.convert(text)
            except Exception:
                pass
        
        return self._simple_s2t(text)
    
    def _simple_s2t(self, text: str) -> str:
        """簡單的簡繁轉換（備用）"""
        s2t_map = {
            '机': '機', '时': '時', '间': '間', '这': '這',
            '里': '裡', '着': '著', '过': '過', '进': '進',
            '动': '動', '执': '執', '认': '認', '为': '為',
            '会': '會', '该': '該', '请': '請', '问': '問',
            '确': '確', '设': '設', '关': '關', '开': '開',
            '发': '發', '电': '電', '脑': '腦', '视': '視',
            '频': '頻', '显': '顯', '组': '組', '装': '裝',
            '产': '產', '线': '線', '员': '員', '让': '讓',
            '说': '說', '话': '話', '听': '聽', '见': '見',
            '错': '錯', '误': '誤', '处': '處', '备': '備',
            '维': '維', '护': '護', '检': '檢', '测': '測',
            '试': '試', '验': '驗', '调': '調', '运': '運',
            '状': '狀', '态': '態', '连': '連', '断': '斷',
            '续': '續', '继': '繼', '经': '經', '历': '歷',
            '记': '記', '录': '錄', '忆': '憶',
        }
        
        result = text
        for simplified, traditional in s2t_map.items():
            result = result.replace(simplified, traditional)
        return result
    
    def process_response(self, response: str, detected_language: str) -> str:
        """
        處理 LLM 回應
        
        - 如果是中文，轉換為繁體
        - 其他語言保持原樣
        
        Args:
            response: LLM 回應
            detected_language: 偵測到的輸入語言
        
        Returns:
            處理後的回應
        """
        if not response:
            return response
        
        # 中文回應轉繁體
        if detected_language == "zh":
            return self.to_traditional_chinese(response)
        
        return response


# 全域語言處理器實例
language_processor = LanguageProcessor()
