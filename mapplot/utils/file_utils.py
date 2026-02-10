"""
文件處理工具模組
提供檔案和資料處理的函式
"""
import os
import pandas as pd
import logging
from .data_validator import validate_dataframe_columns, validate_all_data_files
from .validators.cross_validator import FileCrossValidator


def validate_data_folder(folder_path):
    """
    驗證資料夾中是否包含所有必要的檔案
    
    Args:
        folder_path (str): 資料夾路徑
        
    Returns:
        tuple: (是否有效, 缺少的檔案清單)
    """
    required_files = {
        "Address.csv": "地址檔案",
        "Section.csv": "路段檔案",
        "Port.csv": "埠口檔案",
        "Shelf.csv": "貨架檔案"
    }
    
    missing_files = []
    for filename, description in required_files.items():
        if not os.path.exists(os.path.join(folder_path, filename)):
            missing_files.append(f"{description} ({filename})")
    
    return len(missing_files) == 0, missing_files


def load_map_data(folder_path):
    """
    載入地圖資料
    
    Args:
        folder_path (str): 地圖資料所在的資料夾路徑
        
    Returns:
        dict: 包含各種地圖檔案路徑的字典
    """
    is_valid, missing_files = validate_data_folder(folder_path)
    if not is_valid:
        raise FileNotFoundError(f"在所選資料夾中找不到以下必要檔案：{', '.join(missing_files)}")
    
    # 建立檔案路徑字典
    map_files = {
        'address': os.path.join(folder_path, "Address.csv"),
        'section': os.path.join(folder_path, "Section.csv"),
        'port': os.path.join(folder_path, "Port.csv"),
        'shelf': os.path.join(folder_path, "Shelf.csv"),
        'save_path': folder_path
    }
    
    logging.info(f"成功載入地圖資料，位於：{folder_path}")
    return map_files

def get_invalid_ids_from_validators(validators):
    """
    從驗證器物件中獲取所有無效的 ID
    
    Args:
        validators (dict): 包含各種驗證器物件的字典
        
    Returns:
        tuple: (無效地址ID集合, 無效路段ID集合)
    """
    invalid_address_ids = set()
    invalid_section_ids = set()
    
    # 從地址驗證器收集異常 ID
    if 'address_validator' in validators and validators['address_validator'] is not None:
        address_validator = validators['address_validator']
        if hasattr(address_validator, 'invalid_address_ids'):
            invalid_address_ids.update(address_validator.invalid_address_ids)
    
    # 從路段驗證器收集異常 ID
    if 'section_validator' in validators and validators['section_validator'] is not None:
        section_validator = validators['section_validator']
        if hasattr(section_validator, 'invalid_address_ids'):
            invalid_address_ids.update(section_validator.invalid_address_ids)
        if hasattr(section_validator, 'invalid_section_ids'):
            invalid_section_ids.update(section_validator.invalid_section_ids)
    
    # 從交叉驗證器收集異常 ID
    if 'cross_validator' in validators and validators['cross_validator'] is not None:
        cross_validator = validators['cross_validator']
        if hasattr(cross_validator, 'get_invalid_ids'):
            add_ids, sec_ids = cross_validator.get_invalid_ids()
            invalid_address_ids.update(add_ids)
            invalid_section_ids.update(sec_ids)
    
    return invalid_address_ids, invalid_section_ids

def load_and_validate_map_data(folder_path, strict=False):
    """
    載入並驗證地圖資料
    
    Args:
        folder_path (str): 地圖資料所在的資料夾路徑
        strict (bool, optional): 嚴格模式 - 若為True則缺少欄位時會拋出例外，若為False則僅記錄警告。預設為True。
        
    Returns:
        dict: 包含各種地圖資料的字典，格式為 {'file_type': dataframe}，
              並添加 'validation_errors' 和 'validation_warnings' 列表
        
    Raises:
        FileNotFoundError: 當找不到必要的檔案時
        ValueError: 當資料欄位不符合預期且strict=True時
    """
    # 先檢查檔案是否存在
    map_files = load_map_data(folder_path)
    # 載入所有CSV檔案
    data = {}
    try:
        data['address'] = pd.read_csv(map_files['address'])
        data['section'] = pd.read_csv(map_files['section'])
        data['port'] = pd.read_csv(map_files['port'])
        data['shelf'] = pd.read_csv(map_files['shelf'])
        
        # 建立驗證結果列表
        data['validation_errors'] = []
        data['validation_warnings'] = []
        
        try:
            # 先驗證所有資料檔案的欄位
            validate_all_data_files(data, strict)
              # 使用檔案交叉驗證器進行更深入的檢查
            cross_validator = FileCrossValidator(data)
            cross_validator.validate(strict=False)  # 先用非嚴格模式收集所有錯誤
              # 收集驗證器中的錯誤和警告
            validation_summary = cross_validator.get_validation_summary()
            data['validation_errors'] = validation_summary["errors"].copy()
            data['validation_warnings'] = validation_summary["warnings"].copy()
            
            # 收集異常的 ID 列表
            invalid_vehicle_address_ids, invalid_vehicle_section_ids, invalid_cargo_address_ids, invalid_cargo_section_ids = cross_validator.get_invalid_ids()
            data['invalid_vehicle_address_ids'] = invalid_vehicle_address_ids
            data['invalid_vehicle_section_ids'] = invalid_vehicle_section_ids
            data['invalid_cargo_address_ids'] = invalid_cargo_address_ids
            data['invalid_cargo_section_ids'] = invalid_cargo_section_ids
            logging.info(f"驗證過程中針對站點共發現 {len(invalid_vehicle_address_ids)} 個異常地址和 {len(invalid_vehicle_section_ids)} 個異常路段")
            logging.info(f"驗證過程中共針對貨物發現 {len(invalid_cargo_address_ids)} 個異常地址和 {len(invalid_cargo_section_ids)} 個異常路段")
            
            # 保存驗證器實例，以便後續可能的處理
            # data['validators'] = {
            #     'cross_validator': cross_validator,
            #     'address_validator': cross_validator.address_validator if hasattr(cross_validator, 'address_validator') else None,
            #     'section_validator': cross_validator.section_validator if hasattr(cross_validator, 'section_validator') else None,
            #     'port_validator': cross_validator.port_validator if hasattr(cross_validator, 'port_validator') else None,
            #     'shelf_validator': cross_validator.shelf_validator if hasattr(cross_validator, 'shelf_validator') else None
            # }
                        # 使用新函式收集所有無效 ID
            # invalid_address_ids, invalid_section_ids = get_invalid_ids_from_validators(data['validators'])
            # data['invalid_address_ids'] = invalid_address_ids
            # data['invalid_section_ids'] = invalid_section_ids
            # logging.info(f"驗證過程中共發現 {len(invalid_address_ids)} 個異常地址和 {len(invalid_section_ids)} 個異常路段")
            
            # 如果是嚴格模式且有錯誤，則拋出例外
            if strict and data['validation_errors']:
                error_message = "檔案交叉驗證失敗，發現以下問題:\n" + "\n".join(data['validation_errors'])
                logging.error(error_message)
                raise ValueError(error_message)
            
            logging.info("所有資料檔案已成功載入並通過欄位和交叉驗證")
            
        except Exception as e:
            # 將例外訊息也添加到驗證錯誤中
            if str(e) not in data['validation_errors']:
                data['validation_errors'].append(str(e))
            if strict:
                raise
        
        # 新增save_path到資料字典，方便後續使用
        data['save_path'] = folder_path
        
        return data
        
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        filename, line, func, text = tb[-1]
        logging.error(f"載入或驗證資料時發生錯誤: {str(e)} | 檔案: {filename} | 行數: {line} | 類型: {type(e).__name__}")
        raise
