"""
地址資料驗證器模組
專門用於驗證地址資料檔案的內容
"""
import pandas as pd
import logging
from typing import Dict, List, Optional
from .base_validator import BaseValidator


class AddressValidator(BaseValidator):
    """
    地址資料驗證器
    用於檢查地址資料檔案的內容正確性
    """
    
    def __init__(self):
        """初始化地址驗證器"""
        super().__init__()
    
    def validate(self, data: Dict[str, pd.DataFrame], strict: bool = False) -> bool:
        """
        驗證地址檔案的資料內容

        Args:
            data (Dict[str, pd.DataFrame]): 包含各類型資料框架的字典
            strict (bool, optional): 嚴格模式 - 若為True則任何驗證失敗都會拋出例外。預設為False。

        Returns:
            bool: 驗證是否通過
        """
        # 重置驗證結果
        self.validation_errors = []
        self.validation_warnings = []
        self.invalid_address_ids = set()
        
        if 'address' not in data or data['address'] is None:
            self.validation_warnings.append("缺少地址檔案")
            return False
            
        address_df = data['address']
        section_df = data.get('section')
        
        # 1. MapVersion一致性檢查
        map_versions = address_df['MapVersion'].unique()
        if len(map_versions) > 1:
            self.validation_errors.append(f"地址檔案中存在多個 MapVersion: {map_versions}")
        
        # 2. AddressId唯一性檢查
        duplicated_ids = address_df[address_df['AddressId'].duplicated()]['AddressId'].tolist()
        if duplicated_ids:
            self.validation_errors.append("地址檔案中存在重複的 AddressId")
            for addr_id in duplicated_ids:
                self.add_invalid_address(addr_id,"vehicle")
        
        # 3. TagId唯一性檢查
        # 先過濾掉 NaN 值再檢查重複
        valid_tag_ids = address_df.dropna(subset=['TagId'])
        duplicated_tag_ids = valid_tag_ids[valid_tag_ids['TagId'].duplicated()]['TagId'].tolist()
        duplicated_tag_address_ids = valid_tag_ids[valid_tag_ids['TagId'].duplicated()]['AddressId'].tolist()
        if duplicated_tag_ids:
            self.validation_errors.append(f"地址檔案中存在重複的 TagId: {duplicated_tag_ids}")
            for addr_id in duplicated_tag_address_ids:
                self.add_invalid_address(addr_id,"vehicle")
            
        # 4. (X, Y)唯一性檢查
        address_df['coordinate'] = list(zip(address_df['X'], address_df['Y']))
        duplicated_coords = address_df[address_df['coordinate'].duplicated()]
        if not duplicated_coords.empty:
            self.validation_errors.append("地址檔案中存在重複的 (X, Y) 座標")
            for addr_id in duplicated_coords['AddressId'].tolist():
                self.add_invalid_address(addr_id,"vehicle")
        del address_df['coordinate']
        
        # 5. StorageStationId唯一性檢查及AllowCargoPosition檢查
        # 先過濾掉 NaN 值再檢查重複
        storage_address_df = address_df.dropna(subset=['StorageStationId'])
        if not storage_address_df.empty:
            # 找出重複的 StorageStationId 值
            duplicated_storage_station_values = storage_address_df[storage_address_df['StorageStationId'].duplicated(keep=False)]['StorageStationId'].unique().tolist()
            # 找出包含重複 StorageStationId 的地址ID
            duplicated_storage_ids = storage_address_df[storage_address_df['StorageStationId'].duplicated()]['AddressId'].tolist()
            
            if duplicated_storage_ids:
                self.validation_errors.append(f"地址檔案中存在重複的 StorageStationId: {duplicated_storage_station_values}")
                for addr_id in duplicated_storage_ids:
                    self.add_invalid_address(addr_id, "cargo")
            
            # 檢查StorageStationId的AllowCargoPosition是否為空
            for index, row in address_df.iterrows():
                if pd.notna(row['StorageStationId']) and (pd.isna(row['AllowCargoPosition']) or 
                                                        self._parse_angle_string(row['AllowCargoPosition']) == []):
                    self.validation_errors.append(f"StorageStationId: {row['StorageStationId']} 的 AllowCargoPosition 為空或格式不正確")
                    self.add_invalid_address(row['AddressId'], "cargo")

        # 6. 檢查地址的AllowCargoPosition與section的相容性
        if section_df is not None:
            for index, row in address_df.iterrows():
                if row['IsChargeStation'] == True:
                    continue
                allowed_cargo_positions_addr = self._parse_angle_string(row['AllowCargoPosition'])
                
                # 如果AllowCargoPosition不是四個角度都允許(0,90,180,270)，則檢查與該地址相連的section
                if allowed_cargo_positions_addr and len(allowed_cargo_positions_addr) < 4:
                    address_id = row['AddressId']
                    
                    # 找出所有與該地址相連的section
                    related_sections = section_df[
                        (section_df['FromAddressId'] == address_id) | 
                        (section_df['ToAddressId'] == address_id)
                    ]

                    # 檢查地址的AllowCargoPosition是否至少有一個角度被任意相鄰的section支援
                    for angle in allowed_cargo_positions_addr:
                        if not any(angle in self._parse_angle_string(section_row['AllowCargoPosition']) for _, section_row in related_sections.iterrows()):
                            self.validation_warnings.append(
                                f"地址 {address_id} 的 AllowCargoPosition 中的角度 {angle} 無法被任何相連的路段支援，車輛無法載著貨物至此站點"
                            )
                            self.add_invalid_address(address_id,"cargo")
        
        # 7. IsChargeStation為true時，(ChargerX, ChargerY)不為0且唯一
        charge_stations = address_df[address_df['IsChargeStation'] == True]
        if not charge_stations.empty:
            # 檢查充電站是否有有效的充電器坐標
            for index, row in charge_stations.iterrows():
                if row['ChargerX'] == 0 and row['ChargerY'] == 0:
                    self.validation_errors.append(f"充電站 {row['AddressId']} 的充電器坐標為 (0, 0)")
                    self.add_invalid_address(row['AddressId'],"vehicle")
              # 檢查充電器坐標是否唯一
            # 使用 copy() 建立實際複製，避免 SettingWithCopyWarning
            charge_stations = charge_stations.copy()
            charge_stations.loc[:, 'charger_coordinate'] = list(zip(charge_stations['ChargerX'], charge_stations['ChargerY']))
            duplicate_charger_coords = charge_stations[charge_stations['charger_coordinate'].duplicated()]
            if not duplicate_charger_coords.empty:
                self.validation_errors.append("存在重複的充電器坐標")
                for addr_id in duplicate_charger_coords['AddressId'].tolist():
                    self.add_invalid_address(addr_id)
        
        # 8. 同一個地址，只能有一種功能: 充電站、儲位站，不可共存
        for index, row in address_df.iterrows():
            if row['IsChargeStation'] == True and pd.notna(row['StorageStationId']):
                self.validation_errors.append(f"地址 {row['AddressId']} 同時被標記為充電站和儲位站")
                self.add_invalid_address(row['AddressId'],"vehicle")
        
        # 驗證結果摘要
        if self.validation_errors:
            logging.error(f"地址資料驗證失敗：{len(self.validation_errors)} 個錯誤")
            if strict:
                raise ValueError(f"地址資料驗證失敗：{self.validation_errors}")
            return False
        
        return True
