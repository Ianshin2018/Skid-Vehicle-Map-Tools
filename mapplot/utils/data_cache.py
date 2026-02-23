"""
数据缓存模块
提供地图数据的缓存功能，避免重复加载和验证
"""
import os
import pandas as pd
import logging
import threading
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class MapDataCache:
    """
    地图数据缓存类
    线程安全，支持多楼层共享数据
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """单例模式，确保全局只有一个缓存实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        # 缓存存储
        self._data_cache: Dict[str, pd.DataFrame] = {}  # 原始 CSV 数据
        self._validation_cache: Dict[str, Dict] = {}     # 验证结果
        self._folder_to_floor: Dict[str, str] = {}       # 文件夹路径到楼层的映射
        
        # 缓存锁（针对每个文件夹）
        self._cache_locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        
        logger.info("MapDataCache 初始化完成（单例模式）")

    def _get_cache_lock(self, folder_path: str) -> threading.Lock:
        """获取指定文件夹的缓存锁"""
        with self._global_lock:
            if folder_path not in self._cache_locks:
                self._cache_locks[folder_path] = threading.Lock()
            return self._cache_locks[folder_path]

    def get_folder_key(self, folder_path: str) -> str:
        """
        从文件夹路径生成缓存键
        使用绝对路径确保一致性
        """
        return os.path.abspath(folder_path)

    def load_csv_data(self, folder_path: str) -> Tuple[Optional[Dict[str, pd.DataFrame]], Optional[Dict]]:
        """
        加载并缓存 CSV 数据
        
        Args:
            folder_path: 数据文件夹路径
            
        Returns:
            tuple: (数据字典, 验证结果字典) 或 (None, None) 如果加载失败
        """
        folder_key = self.get_folder_key(folder_path)
        cache_lock = self._get_cache_lock(folder_path)
        
        with cache_lock:
            # 检查是否已有缓存
            if folder_key in self._data_cache:
                logger.info(f"使用缓存数据: {folder_path}")
                return self._data_cache[folder_key], self._validation_cache.get(folder_key)

            # 加载数据
            try:
                data = self._load_csv_files(folder_path)
                if data is None:
                    return None, None
                    
                # 缓存数据
                self._data_cache[folder_key] = data
                
                logger.info(f"已缓存新数据: {folder_path}")
                return data, None
                
            except Exception as e:
                logger.error(f"加载数据失败: {folder_path}, 错误: {e}")
                return None, None

    def _load_csv_files(self, folder_path: str) -> Optional[Dict[str, pd.DataFrame]]:
        """加载 CSV 文件"""
        # 检查必要文件
        required_files = ['Address.csv', 'Section.csv', 'Port.csv', 'Shelf.csv']
        for filename in required_files:
            file_path = os.path.join(folder_path, filename)
            if not os.path.exists(file_path):
                logger.error(f"缺少必要文件: {file_path}")
                return None

        # 使用快速加载选项
        data = {}
        try:
            # Address.csv - 经常需要数值计算，使用适当的类型
            data['address'] = pd.read_csv(
                os.path.join(folder_path, 'Address.csv'),
                dtype={'AddressId': str}
            )
            
            # Section.csv
            data['section'] = pd.read_csv(
                os.path.join(folder_path, 'Section.csv'),
                dtype={'SectionId': str, 'FromAddressId': str, 'ToAddressId': str}
            )
            
            # Port.csv 和 Shelf.csv - 主要用于显示，不需要特殊处理
            data['port'] = pd.read_csv(
                os.path.join(folder_path, 'Port.csv'),
                dtype={'PortId': str}
            )
            
            data['shelf'] = pd.read_csv(
                os.path.join(folder_path, 'Shelf.csv'),
                dtype={'ShelfId': str}
            )
            
            logger.info(f"CSV 文件加载完成: {folder_path}")
            return data
            
        except Exception as e:
            logger.error(f"CSV 加载错误: {e}")
            return None

    def get_cached_data(self, folder_path: str) -> Optional[Dict[str, pd.DataFrame]]:
        """获取缓存的数据（不加载）"""
        folder_key = self.get_folder_key(folder_path)
        return self._data_cache.get(folder_key)

    def set_validation_result(self, folder_path: str, validation_result: Dict):
        """缓存验证结果"""
        folder_key = self.get_folder_key(folder_path)
        cache_lock = self._get_cache_lock(folder_path)
        
        with cache_lock:
            self._validation_cache[folder_key] = validation_result

    def get_validation_result(self, folder_path: str) -> Optional[Dict]:
        """获取验证结果"""
        folder_key = self.get_folder_key(folder_path)
        return self._validation_cache.get(folder_key)

    def has_cache(self, folder_path: str) -> bool:
        """检查是否有缓存"""
        folder_key = self.get_folder_key(folder_path)
        return folder_key in self._data_cache

    def clear_cache(self, folder_path: str = None):
        """
        清除缓存
        
        Args:
            folder_path: 如果指定，只清除该文件夹的缓存；否则清除所有
        """
        if folder_path:
            folder_key = self.get_folder_key(folder_path)
            cache_lock = self._get_cache_lock(folder_key)
            with cache_lock:
                self._data_cache.pop(folder_key, None)
                self._validation_cache.pop(folder_key, None)
                logger.info(f"已清除缓存: {folder_path}")
        else:
            with self._global_lock:
                self._data_cache.clear()
                self._validation_cache.clear()
                logger.info("已清除所有缓存")

    def preload_floor_data(self, floor_configs: list) -> Dict[str, Dict]:
        """
        并行预加载多个楼层的数据
        
        Args:
            floor_configs: [(floor_label, folder_path), ...] 列表
            
        Returns:
            dict: {floor_label: {success: bool, data: dict, error: str}}
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = {}
        
        def load_single_floor(label, path):
            data, validation = self.load_csv_data(path)
            return label, {
                'success': data is not None,
                'data': data,
                'folder_path': path
            }
        
        # 使用线程池并行加载（最多同时 3 个）
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(load_single_floor, label, path): (label, path)
                for label, path in floor_configs
            }
            
            for future in as_completed(futures):
                try:
                    label, result = future.result()
                    results[label] = result
                    logger.info(f"楼层 {label} 预加载 {'成功' if result['success'] else '失败'}")
                except Exception as e:
                    label, path = futures[future]
                    logger.error(f"楼层 {label} 预加载异常: {e}")
                    results[label] = {
                        'success': False,
                        'error': str(e),
                        'folder_path': path
                    }
        
        return results


# 全局缓存实例
_global_cache: Optional[MapDataCache] = None


def get_data_cache() -> MapDataCache:
    """获取全局数据缓存实例"""
    global _global_cache
    if _global_cache is None:
        _global_cache = MapDataCache()
    return _global_cache
