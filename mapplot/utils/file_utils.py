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


def quick_validate_columns(data, strict=False):
    """
    快速驗證數據框欄位（輕量級驗證）
    
    這個函數執行基本的欄位檢查，比完整驗證更快。
    適用於預加載場景。
    
    Args:
        data (dict): 包含 DataFrame 的字典
        strict (bool): 嚴格模式
        
    Returns:
        tuple: (errors list, warnings list)
    """
    errors = []
    warnings = []
    
    # 定義必要的欄位
    required_columns = {
        'address': ['AddressId', 'X', 'Y'],
        'section': ['SectionId', 'FromAddressId', 'ToAddressId'],
        'port': ['PortId'],
        'shelf': ['ShelfId']
    }
    
    # 檢查每個數據類型
    for data_type, columns in required_columns.items():
        if data_type not in data or data[data_type] is None:
            errors.append(f"缺少 {data_type} 數據")
            continue
            
        df = data[data_type]
        if df.empty:
            warnings.append(f"{data_type} 數據為空")
            continue
            
        # 檢查必要欄位
        missing_cols = [col for col in columns if col not in df.columns]
        if missing_cols:
            errors.append(f"{data_type} 缺少必要欄位: {', '.join(missing_cols)}")
    
    return errors, warnings


def load_and_validate_map_data(folder_path, strict=False, use_cache=True, lightweight=True):
    """
    載入並驗證地圖資料
    
    Args:
        folder_path (str): 地圖資料所在的資料夾路徑
        strict (bool, optional): 嚴格模式 - 若為True則缺少欄位時會拋出例外，若為False則僅記錄警告。預設為True。
        use_cache (bool): 是否使用數據緩存。默認 True。
        lightweight (bool): 是否使用輕量級驗證（只驗證欄位，不做交叉驗證）。默認 True。
        
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
            if lightweight:
                # 輕量級驗證：只檢查必要欄位
                errors, warnings = quick_validate_columns(data, strict)
                data['validation_errors'].extend(errors)
                data['validation_warnings'].extend(warnings)
                
                # 輕量級模式下，設定空的無效 ID 集合
                data['invalid_vehicle_address_ids'] = set()
                data['invalid_vehicle_section_ids'] = set()
                data['invalid_cargo_address_ids'] = set()
                data['invalid_cargo_section_ids'] = set()
                
                if errors:
                    logging.warning(f"輕量級驗證發現 {len(errors)} 個錯誤")
                if warnings:
                    logging.warning(f"輕量級驗證發現 {len(warnings)} 個警告")
                    
            else:
                # 完整驗證（原有邏輯）
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
                
                logging.info("所有資料檔案已成功載入並通過欄位和交叉驗證")
            
            # 如果是嚴格模式且有錯誤，則拋出例外
            if strict and data['validation_errors']:
                error_message = "檔案交叉驗證失敗，發現以下問題:\n" + "\n".join(data['validation_errors'])
                logging.error(error_message)
                raise ValueError(error_message)
            
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
