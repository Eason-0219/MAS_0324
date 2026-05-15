# tools/robot_control.py
"""
機器人控制工具 - 控制機械手臂執行動作
支援 Modbus TCP 通訊
包含三組身高設定檔 (A/B/C) 人因工程設計
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from config.settings import settings

# ============================================================
# Modbus 客戶端
# ============================================================

try:
    from pymodbus.client import ModbusTcpClient
    MODBUS_AVAILABLE = True
except ImportError:
    MODBUS_AVAILABLE = False
    print("⚠️ pymodbus 未安裝，將使用 Mock 模式")


class MockModbusTcpClient:
    """Mock Modbus TCP 客戶端（測試用）"""
    
    def __init__(self, host: str, port: int = 502):
        self.host = host
        self.port = port
        self._connected = False
        self._registers = {}
        print(f"🔧 MockModbusTcpClient initialized for {host}:{port}")
    
    def connect(self) -> bool:
        print(f"🔧 MockModbusTcpClient: Connecting to {self.host}:{self.port}...")
        self._connected = True
        print(f"✅ MockModbusTcpClient: Connected")
        return True
    
    def is_socket_open(self) -> bool:
        return self._connected
    
    def write_register(self, address: int, value: int, **kwargs) -> bool:
        if not self._connected:
            print(f"⚠️ MockModbusTcpClient: Not connected")
            return False
        
        self._registers[address] = value
        print(f"🔧 MockModbus: write_register(address={address}, value={value})")
        return True
    
    def read_holding_registers(self, address: int, count: int, **kwargs):
        if not self._connected:
            return None
        
        class MockResponse:
            def __init__(self, registers):
                self.registers = registers
        
        values = [self._registers.get(address + i, 0) for i in range(count)]
        return MockResponse(values)
    
    def close(self):
        self._connected = False
        print("🔧 MockModbusTcpClient: Closed")


# ============================================================
# 機械手臂動作定義
# ============================================================

class RobotAction(Enum):
    """機械手臂動作類型"""
    EXTEND = "extend"           # 伸出 (機械手臂伸出)
    GRIP = "grip"               # 夾取 (夾取散熱風扇)
    RELEASE = "release"         # 放置 (放置散熱風扇)
    ADJUST_SPEED = "adjust_speed"  # 調整速度


class RobotSpeed(Enum):
    """機械手臂速度"""
    SLOW = "slow"      # 慢速運行手臂
    MEDIUM = "medium"  # 原速運行手臂
    FAST = "fast"      # 全速運行手臂


@dataclass
class RobotState:
    """機械手臂狀態"""
    is_extended: bool = False
    is_gripping: bool = False
    current_speed: RobotSpeed = RobotSpeed.MEDIUM
    position: str = "home"


# ============================================================
# 三組身高設定檔（人因工程）
# ============================================================

# 設定檔 A: 身高 > 180cm
ACTION_MAP_A = {
    "夾取散熱風扇": 1,
    "grip": 1,
    "機械手臂伸出": 4,  # 較高位置
    "extend": 4,
    "放置散熱風扇": 5,
    "release": 5,
}

# 設定檔 B: 身高 170-180cm
ACTION_MAP_B = {
    "夾取散熱風扇": 1,
    "grip": 1,
    "機械手臂伸出": 3,  # 中等位置
    "extend": 3,
    "放置散熱風扇": 5,
    "release": 5,
}

# 設定檔 C: 身高 < 170cm
ACTION_MAP_C = {
    "夾取散熱風扇": 1,
    "grip": 1,
    "機械手臂伸出": 2,  # 較低位置
    "extend": 2,
    "放置散熱風扇": 5,
    "release": 5,
}

# 速度設定（所有設定檔共用）
SPEED_MAP = {
    "全速運行手臂": 1,
    "fast": 1,
    "原速運行手臂": 2,
    "medium": 2,
    "慢速運行手臂": 3,
    "slow": 3,
}

# 可用動作列表（給 LLM 參考）
AVAILABLE_ACTIONS = ["夾取散熱風扇", "機械手臂伸出", "放置散熱風扇", "原速運行手臂", "全速運行手臂", "慢速運行手臂"]


def get_action_map_by_profile(profile: str) -> Dict[str, int]:
    """根據設定檔取得動作映射表"""
    if profile == "A":
        return ACTION_MAP_A
    elif profile == "B":
        return ACTION_MAP_B
    else:
        return ACTION_MAP_C


class RobotController:
    """
    機械手臂控制器
    
    支援 Modbus TCP 通訊協議
    包含三組身高設定檔 (A/B/C)
    """
    
    # Modbus 寄存器地址
    ACTION_REGISTER = 1024   # 動作寄存器
    SPEED_REGISTER = 1025    # 速度寄存器
    
    def __init__(self):
        self.mock_mode = settings.modbus_mock
        self.host = settings.modbus_host
        self.port = settings.modbus_port
        self.client = None
        self.state = RobotState()
        self.current_profile = "B"  # 預設中等身高
        
        # 動作描述
        self.action_descriptions = {
            RobotAction.EXTEND: "機械手臂伸出",
            RobotAction.GRIP: "夾取主機板",
            RobotAction.RELEASE: "放置主機板",
            RobotAction.ADJUST_SPEED: "調整速度"
        }
        
        self.speed_descriptions = {
            RobotSpeed.SLOW: "慢速",
            RobotSpeed.MEDIUM: "中速",
            RobotSpeed.FAST: "快速"
        }
    
    def set_height_profile(self, profile: str):
        """設定身高設定檔"""
        if profile in ["A", "B", "C"]:
            self.current_profile = profile
            print(f"🤖 機械手臂設定檔切換為: {profile}")
    
    def set_height(self, height: float):
        """根據身高自動設定設定檔"""
        if height > 180:
            self.current_profile = "A"
        elif height >= 170:
            self.current_profile = "B"
        else:
            self.current_profile = "C"
        print(f"🤖 根據身高 {height}cm，設定檔切換為: {self.current_profile}")
    
    def get_action_map(self) -> Dict[str, int]:
        """取得當前設定檔的動作映射表"""
        return get_action_map_by_profile(self.current_profile)
    
    def connect(self) -> bool:
        """連接 Modbus 設備"""
        try:
            if self.mock_mode or not MODBUS_AVAILABLE:
                self.client = MockModbusTcpClient(self.host, self.port)
            else:
                self.client = ModbusTcpClient(self.host, port=self.port)
            
            if self.client.connect():
                # 初始化：寫入速度寄存器
                self.client.write_register(self.SPEED_REGISTER, 2)
                return True
            return False
            
        except Exception as e:
            print(f"❌ Modbus 連接失敗: {e}")
            return False
    
    def execute(self, action: str, speed: Optional[str] = None) -> Dict[str, Any]:
        """
        執行機械手臂動作
        
        Args:
            action: 動作類型 (extend, retract, grip, release, adjust_speed)
            speed: 速度設定 (slow, medium, fast)
        
        Returns:
            執行結果，包含 Modbus 寫入資訊
        """
        # 確保已連接
        if self.client is None or not self.client.is_socket_open():
            if not self.connect():
                return {
                    "success": False,
                    "message": "❌ Modbus 連接失敗，無法執行動作",
                    "modbus": None
                }
            # 修正：如果 action 是 None，嘗試從 speed 判斷 (針對 Qwen 路由不精確的情況)
        if not action and speed:
            if "慢速" in speed or "slow" in speed:
                action = "慢速運行機械手臂"
            elif "全速" in speed or "fast" in speed:
                action = "全速運行機械手臂"
            elif "原速" in speed or "medium" in speed:
                action = "原速運行機械手臂"

        # 修正：如果還是沒有 action，回傳錯誤
        if not action:
            return {
                "success": False,
                "message": "❌ 錯誤: 未指定動作 (Action is None)",
                "modbus": None
            }
        
        result = {
            "success": True,
            "action": action,
            "profile": self.current_profile,
            "message": "",
            "state": None,
            "modbus": {
                "register": None,
                "value": None,
            }
        }
        
        try:
            # 檢查是否為有效動作
            action_map = self.get_action_map()
            
            if action in ["extend", "機械手臂伸出"]:
                return self._execute_extend(result, action_map)
            
            elif action in ["grip", "夾取散熱風扇"]:
                return self._execute_grip(result, action_map)
            
            elif action in ["release", "放置散熱風扇"]:
                return self._execute_release(result, action_map)
           
            # 🔴 修改這裡：放寬判斷條件
            # 原本是: elif action_str in ["adjust_speed", "調整速度"] or "運行手臂" in action_str:
            # 改為偵測 "運行" 或 "速度" 關鍵字，這樣 "運行機械手臂"、"調整速度" 都能抓到
            elif action in ["adjust_speed", "調整速度"] or "運行" in action or "速度" in action:
                
                # 如果 action 本身包含描述 (如 "慢速運行機械手臂")，把它當作 target_speed 傳入
                # 這樣 _execute_adjust_speed 裡面的模糊比對就能抓到 "慢速"
                target_speed = action if ("運行" in action or "速度" in action) else speed
                return self._execute_adjust_speed(result, target_speed)

            else:
                result["success"] = False
                result["message"] = f"❌ 未知的動作類型: {action}。可用動作: {', '.join(AVAILABLE_ACTIONS)}"
                return result
                
        except Exception as e:
            result["success"] = False
            result["message"] = f"❌ 執行錯誤: {e}"
            return result
    
    def _execute_extend(self, result: Dict, action_map: Dict) -> Dict:
        """執行伸出動作"""
        # if self.state.is_extended:
        #     result["message"] = "機械手臂已經伸出，無需重複操作。"
        #     return result
        
        # 根據設定檔取得對應值
        value = action_map.get("extend", action_map.get("機械手臂伸出", 3))
        success = self.client.write_register(self.ACTION_REGISTER, value)
        
        if success:
            self.state.is_extended = True
            self.state.position = "extended"
            result["message"] = f"✅ 機械手臂已伸出至組裝位置。(設定檔: {self.current_profile}, 值: {value})"
            result["modbus"] = {"register": self.ACTION_REGISTER, "value": value}
        else:
            result["success"] = False
            result["message"] = "❌ Modbus 寫入失敗"
        
        result["state"] = self._get_state_dict()
        return result
    
    def _execute_grip(self, result: Dict, action_map: Dict) -> Dict:
        """執行夾取動作"""
        # if self.state.is_gripping:
        #     result["message"] = "機械手臂已經夾取物件，無需重複操作。"
        #     return result
        
        value = action_map.get("grip", action_map.get("夾取散熱風扇", 1))
        success = self.client.write_register(self.ACTION_REGISTER, value)
        
        if success:
            self.state.is_gripping = True
            result["message"] = "✅ 已夾取主機板。"
            result["modbus"] = {"register": self.ACTION_REGISTER, "value": value}
        else:
            result["success"] = False
            result["message"] = "❌ Modbus 寫入失敗"
        
        result["state"] = self._get_state_dict()
        return result
    
    def _execute_release(self, result: Dict, action_map: Dict) -> Dict:
        """執行放置動作"""
        # if not self.state.is_gripping:
        #     result["message"] = "機械手臂未夾取物件，無法放置。"
        #     result["success"] = False
        #     return result
        
        value = action_map.get("release", action_map.get("放置散熱風扇", 5))
        success = self.client.write_register(self.ACTION_REGISTER, value)
        
        if success:
            self.state.is_gripping = False
            result["message"] = "✅ 已放置主機板。"
            result["modbus"] = {"register": self.ACTION_REGISTER, "value": value}
        else:
            result["success"] = False
            result["message"] = "❌ Modbus 寫入失敗"
        
        result["state"] = self._get_state_dict()
        return result
    
    def _execute_adjust_speed(self, result: Dict, speed: Optional[str]) -> Dict:
        """執行速度調整"""
        if not speed:
            speed = "medium"
        
        # 支援中文速度名稱
        value = SPEED_MAP.get(speed, 2)
        success = self.client.write_register(self.SPEED_REGISTER, value)
        
        if success:
            # 更新狀態
            speed_enum = None
            if speed in ["fast", "全速運行手臂"]:
                speed_enum = RobotSpeed.FAST
            elif speed in ["slow", "慢速運行手臂"]:
                speed_enum = RobotSpeed.SLOW
            else:
                speed_enum = RobotSpeed.MEDIUM
            
            old_speed = self.state.current_speed
            self.state.current_speed = speed_enum
            result["message"] = f"✅ 速度已從「{self.speed_descriptions[old_speed]}」調整為「{self.speed_descriptions[speed_enum]}」。"
            result["modbus"] = {"register": self.SPEED_REGISTER, "value": value}
        else:
            result["success"] = False
            result["message"] = "❌ Modbus 寫入失敗"
        
        result["state"] = self._get_state_dict()
        return result
    
    def _get_state_dict(self) -> Dict[str, Any]:
        """獲取狀態字典"""
        return {
            "is_extended": self.state.is_extended,
            "is_gripping": self.state.is_gripping,
            "current_speed": self.state.current_speed.value,
            "position": self.state.position,
            "profile": self.current_profile
        }
    
    def get_status(self) -> str:
        """獲取機械手臂狀態描述"""
        status_parts = [f"設定檔: {self.current_profile}"]
        
        if self.state.is_extended:
            status_parts.append("已伸出")

        if self.state.is_gripping:
            status_parts.append("夾取中")
        
        status_parts.append(f"速度: {self.speed_descriptions[self.state.current_speed]}")
        
        return "，".join(status_parts)
    
    def get_available_actions(self) -> List[str]:
        """取得可用動作列表"""
        return AVAILABLE_ACTIONS
    
    def close(self):
        """關閉連接"""
        if self.client:
            self.client.close()


# 全域機器人控制器實例
robot_controller = RobotController()