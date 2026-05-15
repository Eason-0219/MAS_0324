# tools/sop_query.py
"""
SOP 查詢工具 - 查詢標準作業程序
"""

from typing import Dict, Any, Optional, List
from pathlib import Path


class SOPQueryTool:
    """
    SOP 查詢工具
    
    提供標準作業程序的查詢功能，包括：
    - 查詢所有步驟
    - 查詢單一步驟
    - 查詢步驟範圍
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        
        # SOP 步驟定義（從 sop.md 載入）
        self.sop_steps: Dict[int, str] = {
            1: "將主機板與背板放至鎖螺絲機上鎖上螺絲",
            2: "檢查主機板是否鎖完（若是，則進到第三步驟；若否，回到第一步驟）",
            3: "從鎖螺絲機上拿起鎖好的主機板置於置物台",
            4: "拿下一組主機板與背板至鎖螺絲機上鎖螺絲",
            5: "拿取置物台上的主機板於準備區等待機械手臂伸出至組裝位置",
            6: "將主機板壓扣至機械手臂所抓取之散熱風扇上",
            7: "拿起螺絲起子",
            8: "拿取彈簧螺絲",
            9: "鎖付主機板和散熱風扇",
            10: "檢查是否鎖完所有彈簧螺絲（共有六顆彈簧螺絲）（若是，則進到第十一步驟；若否，則回到第八步驟）",
            11: "放回螺絲起子",
            12: "請決定是否停止組裝（若是，則組裝結束；若否，則回到第二步驟）",
        }
        
        self.total_steps = len(self.sop_steps)
    
    def query(
        self, 
        query_type: str, 
        step_number: Optional[int] = None,
        start_step: Optional[int] = None,
        end_step: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        查詢 SOP
        
        Args:
            query_type: 查詢類型 (all_steps, single_step, step_range)
            step_number: 步驟編號（用於 single_step）
            start_step: 起始步驟（用於 step_range）
            end_step: 結束步驟（用於 step_range）
        
        Returns:
            查詢結果
        """
        if query_type == "all_steps":
            return self._get_all_steps()
        
        elif query_type == "single_step":
            if step_number is None:
                return {
                    "success": False,
                    "message": "請指定步驟編號"
                }
            return self._get_single_step(step_number)
        
        elif query_type == "step_range":
            if start_step is None or end_step is None:
                return {
                    "success": False,
                    "message": "請指定起始和結束步驟編號"
                }
            return self._get_step_range(start_step, end_step)
        
        else:
            return {
                "success": False,
                "message": f"未知的查詢類型: {query_type}"
            }
    
    def _get_all_steps(self) -> Dict[str, Any]:
        """獲取所有步驟"""
        steps_text = self._format_steps(list(self.sop_steps.keys()))
        
        return {
            "success": True,
            "query_type": "all_steps",
            "total_steps": self.total_steps,
            "message": f"📋 **顯示卡組裝標準作業程序（共 {self.total_steps} 步驟）**\n\n{steps_text}"
        }
    
    def _get_single_step(self, step_number: int) -> Dict[str, Any]:
        """獲取單一步驟"""
        if step_number < 1 or step_number > self.total_steps:
            return {
                "success": False,
                "message": f"步驟編號必須在 1 到 {self.total_steps} 之間，您輸入的是 {step_number}"
            }
        
        step_content = self.sop_steps[step_number]
        
        # 提供上下文（前後步驟提示）
        context = []
        if step_number > 1:
            context.append(f"上一步（第{step_number-1}步）：{self.sop_steps[step_number-1]}")
        if step_number < self.total_steps:
            context.append(f"下一步（第{step_number+1}步）：{self.sop_steps[step_number+1]}")
        
        message = f"📌 **第 {step_number} 步驟**\n{step_content}"
        if context:
            message += f"\n\n💡 **相關步驟**\n" + "\n".join(context)
        
        return {
            "success": True,
            "query_type": "single_step",
            "step_number": step_number,
            "content": step_content,
            "message": message
        }
    
    def _get_step_range(self, start: int, end: int) -> Dict[str, Any]:
        """獲取步驟範圍"""
        # 驗證範圍
        start = max(1, min(start, self.total_steps))
        end = max(1, min(end, self.total_steps))
        
        if start > end:
            start, end = end, start
        
        step_numbers = list(range(start, end + 1))
        steps_text = self._format_steps(step_numbers)
        
        return {
            "success": True,
            "query_type": "step_range",
            "start_step": start,
            "end_step": end,
            "count": len(step_numbers),
            "message": f"📋 **步驟 {start} 到 {end}（共 {len(step_numbers)} 步）**\n\n{steps_text}"
        }
    
    def _format_steps(self, step_numbers: List[int]) -> str:
        """格式化步驟列表"""
        lines = []
        for num in step_numbers:
            if num in self.sop_steps:
                lines.append(f"**第{num}步驟**：{self.sop_steps[num]}")
        return "\n\n".join(lines)
    
    def get_current_step_hint(self, last_step: Optional[int] = None) -> str:
        """根據上一個步驟提供下一步提示"""
        if last_step is None:
            return "請從第一步開始：" + self.sop_steps[1]
        
        next_step = last_step + 1
        if next_step > self.total_steps:
            return "您已完成所有步驟！"
        
        return f"下一步是第{next_step}步：{self.sop_steps[next_step]}"


# 全域 SOP 查詢工具實例
sop_query_tool = SOPQueryTool()
