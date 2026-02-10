"""
基礎驗證器模組
提供所有驗證器的共同功能
"""
import pandas as pd
import logging
from typing import Dict, List, Optional, Set


class BaseValidator:
    """
    基礎驗證器類別
    提供所有驗證器的共同功能和屬性
    """
    
    def __init__(self):
        """
        初始化基礎驗證器
        """
        self.validation_errors = []
        self.validation_warnings = []
        self.invalid_vehicle_address_ids = set()  # 儲存異常的addressId
        self.invalid_vehicle_section_ids = set()  # 儲存異常的sectionId
        self.invalid_cargo_address_ids = set()  # 儲存異常的addressId
        self.invalid_cargo_section_ids = set()  # 儲存異常的sectionId
    
    def _parse_angle_string(self, angle_string: str) -> List[int]:
        """
        將斜線分隔的角度字串轉換為角度列表

        Args:
            angle_string (str): 格式如 "0/90/180/270" 的角度字串

        Returns:
            List[int]: 角度列表，如 [0, 90, 180, 270]
        """
        if pd.isna(angle_string):
            return []
        
        try:
            angles = [int(angle) for angle in str(angle_string).split('/')]
            # 檢查所有角度是否都是有效值 (0, 90, 180, 270)
            valid_angles = [0, 90, 180, 270]
            for angle in angles:
                if angle not in valid_angles:
                    return []  # 返回空列表表示無效
            return angles
        except ValueError:
            return []
    
    def add_invalid_address(self, address_id, type):
        """
        添加異常的地址ID

        Args:
            address_id: 異常的addressId
            type: 地址類型 (vehicle 或 cargo)
        """
        if type == "vehicle":
            self.invalid_vehicle_address_ids.add(address_id)
        elif type == "cargo":
            self.invalid_cargo_address_ids.add(address_id)
    
    def add_invalid_section(self, section_id, type):
        """
        添加異常的路段ID

        Args:
            section_id: 異常的sectionId
            type: 路段類型 (vehicle 或 cargo)
        """
        if type == "vehicle":
            self.invalid_vehicle_section_ids.add(section_id)
        elif type == "cargo":
            self.invalid_cargo_section_ids.add(section_id)
    
    def get_invalid_ids(self):
        """
        獲取所有異常的ID

        Returns:
            tuple: (異常地址ID集合, 異常路段ID集合)
        """
        return (self.invalid_vehicle_address_ids, self.invalid_vehicle_section_ids, 
                self.invalid_cargo_address_ids, self.invalid_cargo_section_ids)
    
    def validate(self, data: Dict[str, pd.DataFrame], strict: bool = False) -> bool:
        """
        執行驗證檢查

        Args:
            data (Dict[str, pd.DataFrame]): 要驗證的資料
            strict (bool, optional): 嚴格模式 - 若為True則任何驗證失敗都會拋出例外。預設為False。

        Returns:
            bool: 驗證是否通過
        """
        # 子類別必須實作此方法
        raise NotImplementedError("子類別必須實作 validate 方法")
    
    def get_validation_summary(self) -> Dict:
        """
        獲取驗證結果摘要

        Returns:
            Dict: 包含驗證結果的字典
        """
        return {
            "errors": self.validation_errors,
            "warnings": self.validation_warnings,
            "is_valid": len(self.validation_errors) == 0
        }
