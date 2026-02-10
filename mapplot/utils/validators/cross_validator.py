"""
檔案交叉驗證器模組
協調多個驗證器進行檔案間的交叉檢查
"""
import logging
import pandas as pd
from typing import Dict, List, Optional, Tuple, Set
from .address_validator import AddressValidator
from .section_validator import SectionValidator
from .port_validator import PortValidator
from .shelf_validator import ShelfValidator
from .base_validator import BaseValidator


class FileCrossValidator(BaseValidator):
    """
    檔案交叉驗證器
    用於檢查多個檔案的內容並進行交叉驗證
    """
    
    def __init__(self, file_data: Dict[str, pd.DataFrame]):
        """
        初始化檔案交叉驗證器

        Args:
            file_data (Dict[str, pd.DataFrame]): 包含各類型資料框架的字典，格式為 {'file_type': dataframe}
                支援的檔案類型: 'address', 'section', 'port', 'shelf'
        """
        super().__init__()
        self.file_data = file_data
        self.validators = {
            'address': AddressValidator(),
            'section': SectionValidator(),
            'port': PortValidator(),
            'shelf': ShelfValidator()
        }
    
    def validate(self, data: Dict[str, pd.DataFrame] = None, strict: bool = False) -> bool:
        """
        執行所有驗證檢查

        Args:
            data (Dict[str, pd.DataFrame], optional): 若提供，則使用此資料而不是初始化時提供的資料
            strict (bool, optional): 嚴格模式 - 若為True則任何驗證失敗都會拋出例外。預設為False。

        Returns:
            bool: 所有檢查是否通過
        """
        # 使用提供的資料或初始化時設定的資料
        data_to_validate = data if data is not None else self.file_data
        
        # 重置驗證結果
        self.validation_errors = []
        self.validation_warnings = []
        
        # 1. 逐一執行各類型資料的驗證
        for file_type, validator in self.validators.items():
            if file_type in data_to_validate and data_to_validate[file_type] is not None:
                valid = validator.validate(data_to_validate, strict=False)
                invalid_ids = validator.get_invalid_ids()
                # 收集驗證結果
                self.validation_errors.extend(validator.validation_errors)
                self.validation_warnings.extend(validator.validation_warnings)
                if invalid_ids[0]:
                    for address_id in invalid_ids[0]:
                        self.add_invalid_address(address_id,"vehicle")
                if invalid_ids[1]:
                    for section_id in invalid_ids[1]:
                        self.add_invalid_section(section_id,"vehicle")
                if invalid_ids[2]:
                    for address_id in invalid_ids[2]:
                        self.add_invalid_address(address_id,"cargo")
                if invalid_ids[3]:
                    for section_id in invalid_ids[3]:
                        self.add_invalid_section(section_id,"cargo")        


        # 2. 執行檔案之間的交叉檢查
        self._perform_cross_validation(data_to_validate)
        
        # 如果存在錯誤且嚴格模式啟用，則拋出例外
        if self.validation_errors and strict:
            raise ValueError("檔案驗證失敗")
        
        # 返回是否全部通過驗證
        return len(self.validation_errors) == 0
    
    def _perform_cross_validation(self, data: Dict[str, pd.DataFrame]) -> None:
        """
        執行檔案之間的交叉檢查
        檢查不同檔案之間的資料關聯是否一致

        Args:
            data (Dict[str, pd.DataFrame]): 要驗證的資料
        """
        address_df = data.get('address')
        section_df = data.get('section')
        port_df = data.get('port')
        shelf_df = data.get('shelf')

        # 1. 檢查四個檔案中的 MapVersion 是否一致
        self._validate_map_versions(data)
        
        # 2. 檢查地址與存儲站點之間的一致性
        self._validate_storage_consistency(address_df, port_df, shelf_df)
        self._validate_section_reverse(address_df, section_df)
    
    def _validate_map_versions(self, data: Dict[str, pd.DataFrame]) -> None:
        """
        檢查不同檔案中的 MapVersion 是否一致

        Args:
            data (Dict[str, pd.DataFrame]): 要驗證的資料
        """
        map_versions = {}
        for file_type in ['address', 'section', 'port', 'shelf']:
            df = data.get(file_type)
            if df is not None and 'MapVersion' in df.columns and len(df) > 0:
                map_versions[file_type] = df['MapVersion'].iloc[0]  # 假設每個檔案只有一個 MapVersion

        if len(set(map_versions.values())) > 1:
            self.validation_warnings.append(f"不同檔案之間的 MapVersion 不一致: {map_versions}")
    
    def _validate_storage_consistency(self, address_df, port_df, shelf_df):
        """
        檢查地址、埠口和貨架之間的一致性

        Args:
            address_df (pd.DataFrame): 地址資料框架
            port_df (pd.DataFrame): 埠口資料框架
            shelf_df (pd.DataFrame): 貨架資料框架
        """
        if address_df is None:
            return
        
        # 建立 address 中 AddressId 到 StorageStationId 的映射
        address_storage_map = address_df.set_index('AddressId')['StorageStationId'].dropna().to_dict()
        
        # 收集所有在 port 和 shelf 檔案中出現的 AddressId
        mapped_addresses = set()
        
        # 檢查是否有 Address 檔案中有 StorageStationId 但在 Port/Shelf 檔案中找不到對應的紀錄
        for address_id, storage_id in address_storage_map.items():
            found = False
            if port_df is not None:
                port_matches = port_df[port_df['AddressId'] == address_id]
                if not port_matches.empty:
                    found = True
                    mapped_addresses.add(address_id)
            
            if not found and shelf_df is not None:
                shelf_matches = shelf_df[shelf_df['AddressId'] == address_id]
                if not shelf_matches.empty:
                    found = True
                    mapped_addresses.add(address_id)
            
            if not found:
                self.validation_warnings.append(f"Address 檔案中 AddressId: {address_id} 有 StorageStationId: {storage_id}，但在 Port/Shelf 檔案中找不到對應的紀錄")
        
        # 檢查 address 檔案裡的 StorageStationId 數量是否與 port/shelf 檔案的 AddressId 總數一致
        address_storage_count = len(address_storage_map)
        total_mapped_count = len(mapped_addresses)
        
        if address_storage_count != total_mapped_count:
            self.validation_warnings.append(
                f"Address 檔案中的 StorageStationId 數量 ({address_storage_count}) 與 Port/Shelf 檔案中的 AddressId 總數 ({total_mapped_count}) 不一致"
            )

    def _validate_section_reverse(self, address_df: pd.DataFrame, section_df: pd.DataFrame):
        if section_df is None or address_df is None:
            return
        
        address_pickup_map = address_df.set_index('AddressId')['IsPickupStation'].fillna(False).to_dict()

        for index, row in section_df.iterrows():
            from_addr = row.get('FromAddress')
            to_addr = row.get('ToAddress')
            if pd.isna(from_addr) or pd.isna(to_addr):
                continue
            
            reverse_section = section_df[
                (section_df['FromAddress'] == to_addr) &
                (section_df['ToAddress'] == from_addr)
            ]

            # 如果沒有反向路段，且兩個位址都不是 PickupStation，則給出警告
            if reverse_section.empty:
                from_pickup = address_pickup_map.get(from_addr, False)
                to_pickup = address_pickup_map.get(to_addr, False)
                if not from_pickup and not to_pickup:
                    self.validation_warnings.append(f"Section {from_addr} -> {to_addr} 缺少反向路段，而且兩個位址都不是 PickupStation。")


def validate_files(file_data: Dict[str, pd.DataFrame], strict: bool = False) -> Dict:
    """
    便捷函式，用於驗證多個檔案並獲取驗證結果

    Args:
        file_data (Dict[str, pd.DataFrame]): 包含各類型資料框架的字典，格式為 {'file_type': dataframe}
        strict (bool, optional): 嚴格模式 - 若為True則任何驗證失敗都會拋出例外。預設為False。

    Returns:
        Dict: 包含驗證結果的字典
    """
    validator = FileCrossValidator(file_data)
    validator.validate(strict=strict)
    return validator.get_validation_summary()
