# 注意：这里只保留轻量的 config 常量导出。
# 不要在此顶层导入 api_client/database/download 等业务模块——
# 它们（requests/PIL/下载器）只有在 import src 时被连带加载，
# 会显著拖慢打包后的启动速度。使用方请从具体子模块导入
# （如 from src.database.database import DatabaseManager）。
from . import config
from .config import (
    _APP_ROOT, VERSION, SETTINGS_DIR, CONFIG_PATH,
    MEMORY_CACHE_SIZE,
    ARIA2_RPC_URL, CONFIG_DIR, CACHE_DIR,
    DB_PATH, DOWNLOAD_HISTORY_DB_PATH, ICON_PATH,
    DOWNLOAD_DIR, ARIA2_DIR, DB_DIR
)
