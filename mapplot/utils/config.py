"""
配置模組
提供應用程式的各種配置設定
"""

# 預期的資料欄位設定
EXPECTED_COLUMNS = {
    # 地址檔案的預期欄位
    'address': [
        'MapVersion','AddressId', 'TagId', 'X', 'Y', 'Theta', 'OffsetX', 'OffsetY', 'OffsetTheta','IsChargeStation', 
        'StorageStationId', 'ChargerX', 'ChargerY', 'ChargerTheta', 'KnownObstacle', 'AllowVehiclePosition',  'AllowCargoPosition', 'IsPickupStation', 'IsNarrowStation'
    ],
    
    # 路段檔案的預期欄位
    'section': [
         'MapVersion','SectionId','FromAddressId', 'ToAddressId',  'SectionPosition', 'VehicleSpeedUnload', 'VehicleSpeedLoaded','AllowVehiclePosition', 'AllowCargoPosition', 'VehicleSpeedEnforce'
    ],
    
    # 埠口檔案的預期欄位
    'port': [
        'MapVersion','PortId', 'AddressId','VerticalRange', 'HorizontalRange'
    ],
    
    # 貨架檔案的預期欄位
    'shelf': [
        'MapVersion','ShelfId', 'AddressId','VerticalRange', 'HorizontalRange'
    ]
}