"""
資料驗證工具模組
提供資料檢查與驗證功能
"""
import logging
import pandas as pd
from .config import EXPECTED_COLUMNS


def validate_dataframe_columns(df, file_type, strict=True):
    """
    驗證資料框架是否包含所有預期的欄位

    Args:
        df (pandas.DataFrame): 要驗證的資料框架
        file_type (str): 檔案類型 ('address', 'section', 'port', 'shelf')
        strict (bool, optional): 嚴格模式 - 若為True則缺少欄位時會拋出例外，若為False則僅記錄警告。預設為True。

    Returns:
        bool: 驗證是否通過

    Raises:
        ValueError: 當嚴格模式下缺少必要欄位時
        KeyError: 當指定的file_type不在設定中時
    """
    if file_type not in EXPECTED_COLUMNS:
        raise KeyError(f"未知的檔案類型: {file_type}。支援的類型為: {', '.join(EXPECTED_COLUMNS.keys())}")

    expected_columns = EXPECTED_COLUMNS[file_type]
    
    # 檢查是否有缺少的欄位
    missing_cols = [col for col in expected_columns if col not in df.columns]
    
    # 檢查是否有額外的欄位
    extra_cols = [col for col in df.columns if col not in expected_columns]
    
    # 處理缺少的欄位
    if missing_cols:
        error_msg = f"{file_type.capitalize()}檔案缺少以下必要欄位: {', '.join(missing_cols)}"
        logging.error(error_msg)
        
        if strict:
            raise ValueError(error_msg)
        return False
    
    # 記錄額外的欄位
    # if extra_cols:
    #     warning_msg = f"{file_type.capitalize()}檔案包含以下未預期的欄位: {', '.join(extra_cols)}"
    #     logging.warning(warning_msg)
    
    return True


def validate_all_data_files(data_files, strict=False):
    """
    一次驗證多個資料檔案

    Args:
        data_files (dict): 包含各類型資料框架的字典，格式為 {'file_type': dataframe}
        strict (bool, optional): 嚴格模式 - 若為True則缺少欄位時會拋出例外，若為False則僅記錄警告。預設為True。

    Returns:
        bool: 所有檔案驗證是否通過
    """
    all_valid = True
    valid_file_types = list(EXPECTED_COLUMNS.keys())
    
    for file_type, df in data_files.items():
        # 只驗證已定義在 EXPECTED_COLUMNS 中的檔案類型
        if df is not None and file_type in valid_file_types:
            try:
                file_valid = validate_dataframe_columns(df, file_type, strict)
                all_valid = all_valid and file_valid
            except Exception as e:
                import traceback
                tb = traceback.extract_tb(e.__traceback__)
                filename, line, func, text = tb[-1]
                logging.error(f"資料驗證錯誤: {str(e)} | 檔案: {filename} | 行數: {line} | 類型: {type(e).__name__}")
                all_valid = False
                if strict:
                    raise
    if not all_valid: raise RuntimeError("validate all data files failed")
    return all_valid
