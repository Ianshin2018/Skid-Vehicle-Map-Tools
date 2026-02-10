"""
路段資料驗證器模組
專門用於驗證路段資料檔案的內容
"""
import pandas as pd
import math
import logging
from typing import Dict, List, Optional
from .base_validator import BaseValidator


class SectionValidator(BaseValidator):
    """
    路段資料驗證器
    用於檢查路段資料檔案的內容正確性
    """
    
    def __init__(self):
        """初始化路段驗證器"""
        super().__init__()
    
    def validate(self, data: Dict[str, pd.DataFrame], strict: bool = False) -> bool:
        """
        驗證路段檔案的資料內容

        Args:
            data (Dict[str, pd.DataFrame]): 包含各類型資料框架的字典
            strict (bool, optional): 嚴格模式 - 若為True則任何驗證失敗都會拋出例外。預設為False。

        Returns:
            bool: 驗證是否通過
        """
        # 重置驗證結果
        self.validation_errors = []
        self.validation_warnings = []
        self.invalid_section_ids = set()
        self.invalid_address_ids = set()
        
        if 'section' not in data or data['section'] is None:
            self.validation_warnings.append("缺少路段檔案")
            return False
            
        section_df = data['section']
        address_df = data.get('address')

        # 1. MapVersion一致性檢查
        map_versions = section_df['MapVersion'].unique()
        if len(map_versions) > 1:
            self.validation_errors.append(f"路段檔案中存在多個 MapVersion: {map_versions}")

        # 2. SectionId唯一性檢查
        duplicated_ids = section_df[section_df['SectionId'].duplicated()]['SectionId'].tolist()
        if duplicated_ids:
            self.validation_errors.append("路段檔案中存在重複的 SectionId")
            for section_id in duplicated_ids:
                self.add_invalid_section(section_id,"vehicle")
        
        # 3. FromAddressId與ToAddressId檢查 - 檢查是否存在且不相同
        if address_df is not None:
            valid_address_ids = set(address_df['AddressId'].tolist())
            
            # 檢查FromAddressId是否有效
            for index, row in section_df.iterrows():
                section_id = row['SectionId']
                from_addr = row['FromAddressId']
                to_addr = row['ToAddressId']
                
                # 檢查FromAddressId是否存在於地址檔案中
                if from_addr not in valid_address_ids:
                    self.validation_errors.append(f"路段 {section_id} 的 FromAddressId {from_addr} 不存在於地址檔案中")
                    self.add_invalid_section(section_id,"vehicle")
                
                # 檢查ToAddressId是否存在於地址檔案中
                if to_addr not in valid_address_ids:
                    self.validation_errors.append(f"路段 {section_id} 的 ToAddressId {to_addr} 不存在於地址檔案中")
                    self.add_invalid_section(section_id,"vehicle")
                
                # 檢查FromAddressId與ToAddressId是否相同
                if from_addr == to_addr:
                    self.validation_errors.append(f"路段 {section_id} 的 FromAddressId 和 ToAddressId 相同: {from_addr}")
                    self.add_invalid_section(section_id,"vehicle")
                    self.add_invalid_address(from_addr,"vehicle")
        
        # 4. 檢查路段的AllowCargoPosition與地址的相容性
        if address_df is not None:
            for index, row in section_df.iterrows():
                allowed_cargo_positions_section = self._parse_angle_string(row['AllowCargoPosition'])
                section_id = row['SectionId']
                
                # 獲取起點與終點地址的數據
                from_addr_id = row['FromAddressId']
                to_addr_id = row['ToAddressId']
                
                from_addr_data = address_df[address_df['AddressId'] == from_addr_id]
                to_addr_data = address_df[address_df['AddressId'] == to_addr_id]
                
                # 檢查起點地址的AllowCargoPosition與section相容
                # if not from_addr_data.empty:
                #     allowed_cargo_positions_from = self._parse_angle_string(from_addr_data.iloc[0]['AllowCargoPosition'])
                #     if allowed_cargo_positions_section and allowed_cargo_positions_from:
                #         if not any(angle in allowed_cargo_positions_from for angle in allowed_cargo_positions_section):
                #             self.validation_warnings.append(
                #                 f"路段 {section_id} 的 AllowCargoPosition {row['AllowCargoPosition']} 與起點地址 {from_addr_id} 的 {from_addr_data.iloc[0]['AllowCargoPosition']} 不相容"
                #             )
                #             self.add_invalid_section(section_id)
                #             self.add_invalid_address(from_addr_id)
                
                # 檢查終點地址的AllowCargoPosition與section相容
                if not to_addr_data.empty:
                    allowed_cargo_positions_to = self._parse_angle_string(to_addr_data.iloc[0]['AllowCargoPosition'])
                    if allowed_cargo_positions_section and allowed_cargo_positions_to:
                        if not any(angle in allowed_cargo_positions_to for angle in allowed_cargo_positions_section):
                            self.validation_warnings.append(
                                f"路段 {section_id} 的 AllowCargoPosition {row['AllowCargoPosition']} 與終點地址 {to_addr_id} 的 {to_addr_data.iloc[0]['AllowCargoPosition']} 不相容"
                            )
                            self.add_invalid_section(section_id,"cargo")
                            self.add_invalid_address(to_addr_id,"cargo")
        
        # 驗證結果摘要
        if self.validation_errors:
            logging.error(f"路段資料驗證失敗：{len(self.validation_errors)} 個錯誤")
            if strict:
                raise ValueError(f"路段資料驗證失敗：{self.validation_errors}")
            return False
        
        return True
