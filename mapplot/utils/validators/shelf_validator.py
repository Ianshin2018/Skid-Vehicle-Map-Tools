"""
貨架資料驗證器模組
專門用於驗證貨架資料檔案的內容
"""
import pandas as pd
from typing import Dict
from .base_validator import BaseValidator


class ShelfValidator(BaseValidator):
    """
    貨架資料驗證器
    用於檢查貨架資料檔案的內容正確性
    """
    
    def __init__(self):
        """初始化貨架驗證器"""
        super().__init__()
    
    def validate(self, data: Dict[str, pd.DataFrame], strict: bool = False) -> bool:
        """
        驗證貨架檔案的資料內容

        Args:
            data (Dict[str, pd.DataFrame]): 包含各類型資料框架的字典
            strict (bool, optional): 嚴格模式 - 若為True則任何驗證失敗都會拋出例外。預設為False。

        Returns:
            bool: 驗證是否通過
        """
        # 重置驗證結果
        self.validation_errors = []
        self.validation_warnings = []
        
        if 'shelf' not in data or data['shelf'] is None:
            self.validation_warnings.append("缺少貨架檔案")
            return False
            
        shelf_df = data['shelf']
        address_df = data.get('address')

        # 1. MapVersion一致性檢查
        map_versions = shelf_df['MapVersion'].unique()
        if len(map_versions) > 1:
            self.validation_errors.append(f"貨架檔案中存在多個 MapVersion: {map_versions}")

        # 2. ShelfId唯一性檢查
        if shelf_df['ShelfId'].duplicated().any():
            self.validation_errors.append("貨架檔案中存在重複的 ShelfId")

        # 3. AddressId唯一性檢查
        if shelf_df['AddressId'].duplicated().any():
            self.validation_errors.append("貨架檔案中存在重複的 AddressId")
            
        # 4. 檢查與地址資料的關係
        if address_df is not None:
            self._validate_with_address_data(shelf_df, address_df)
        
        # 回傳驗證結果
        return len(self.validation_errors) == 0
    
    def _validate_with_address_data(self, shelf_df, address_df):
        """
        檢查與地址資料的關係

        Args:
            shelf_df (pd.DataFrame): 貨架資料框架
            address_df (pd.DataFrame): 地址資料框架
        """
        # 建立 address 中 AddressId 到 StorageStationId 的映射
        address_storage_map = address_df.set_index('AddressId')['StorageStationId'].dropna().to_dict()
        
        for index, row in shelf_df.iterrows():
            address_id = row['AddressId']
            shelf_id = row['ShelfId']
            
            # 檢查 address 檔案中是否有此 AddressId
            if address_id not in address_df['AddressId'].values:
                self.validation_warnings.append(f"Shelf 檔案中的 AddressId: {address_id} 在 Address 檔案中不存在")
                self.add_invalid_address(address_id,"cargo")
                continue
            
            # 檢查 StorageStationId 是否存在且與 ShelfId 一致
            if address_id in address_storage_map:
                storage_id = address_storage_map[address_id]
                if storage_id != shelf_id:
                    self.validation_warnings.append(f"AddressId: {address_id} 的 StorageStationId: {storage_id} 與 ShelfId: {shelf_id} 不一致")
                    self.add_invalid_address(address_id,"cargo")
            else:
                self.validation_warnings.append(f"Address 檔案中 AddressId: {address_id} 沒有對應的 StorageStationId，但在 Shelf 檔案中存在")
                self.add_invalid_address(address_id,"cargo")
