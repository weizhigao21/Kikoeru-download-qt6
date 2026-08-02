import requests
import json
import threading
import logging
import time
from typing import Optional, Callable
from collections import OrderedDict

logger = logging.getLogger('translator')


class TranslatorService:
    """AI 翻译服务 - 使用 OpenAI 兼容 API"""

    _MAX_CACHE_SIZE = 500

    def __init__(self):
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        # 初始化配置属性，避免 update_config 未调用时 _translate_thread 访问 _base_url 抛 AttributeError
        self._api_key = ""
        self._base_url = ""
        self._model = ""
        self._thinking_enabled = True
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json"
        })

    def _safe_callback(self, callback: Callable[[Optional[str]], None], result: Optional[str]):
        """安全调用回调，捕获异常并记录日志。

        _translate_thread 中 7 处 callback 调用都有 try/except 包裹（约 4 行 × 7 = 28 行重复），
        提取为公共方法消除重复。
        """
        try:
            callback(result)
        except Exception:
            logger.exception("翻译回调异常")

    def update_config(self, api_key: str, base_url: str, model: str, thinking_enabled: bool = True):
        """更新 API 配置"""
        self._api_key = api_key
        self._base_url = base_url.rstrip('/')
        for suffix in ('/chat/completions', '/chat/completions/'):
            if self._base_url.lower().endswith(suffix):
                self._base_url = self._base_url[:-len(suffix)]
                break
        self._base_url = self._base_url.rstrip('/')
        self._model = model
        self._thinking_enabled = thinking_enabled
        # 仅更新 Authorization，保留 session 其他配置（避免丢失 thinking 等自定义头）
        with self._lock:
            self._session.headers.update({
                "Authorization": f"Bearer {api_key}"
            })

    def translate(self, text: str, callback: Callable[[Optional[str]], None], timeout: Optional[int] = None):
        """
        异步翻译文本

        Args:
            text: 要翻译的文本
            callback: 翻译完成回调，参数为翻译结果或 None（失败时）
            timeout: 翻译超时时间（秒）。None 时根据思考模式自动选择
                     （思考模式 90 秒，普通模式 30 秒）
        """
        if timeout is None:
            timeout = 90 if getattr(self, '_thinking_enabled', True) else 30
        # 空文本直接回调 None，不启动翻译线程
        if not text or not text.strip():
            self._safe_callback(callback, None)
            return

        # 缓存命中：直接回调缓存结果，不启动翻译线程
        with self._lock:
            if text in self._cache:
                cached = self._cache[text]
                if cached and cached.strip():
                    self._cache.move_to_end(text)
                    self._safe_callback(callback, cached)
                    return
                else:
                    del self._cache[text]

        # 缓存未命中：启动翻译线程
        threading.Thread(
            target=self._translate_thread,
            args=(text, callback, timeout),
            daemon=True
        ).start()

    def _translate_thread(self, text: str, callback: Callable[[Optional[str]], None], timeout: int = 30):
        """翻译线程，带超时保护"""
        start_time = time.time()
        try:
            if not self._api_key:
                logger.error("未配置 API Key")
                self._safe_callback(callback, None)
                return

            url = f"{self._base_url}/chat/completions"
            thinking_enabled = self._thinking_enabled
            payload = {
                "model": self._model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的日语翻译助手。请将用户输入的日语文本翻译成简体中文。只返回翻译结果，不要添加任何解释或额外内容。如果输入不是日语，请原样返回。"
                    },
                    {
                        "role": "user",
                        "content": f"请翻译以下文本：\n{text}"
                    }
                ],
                "max_tokens": 1024 if thinking_enabled else 500
            }
            if thinking_enabled:
                # DeepSeek 思考模式：开启思考并限制推理强度；该模式下不支持 temperature
                payload["thinking"] = {"type": "enabled"}
                payload["reasoning_effort"] = "high"
            else:
                payload["temperature"] = 0.3

            response = self._session.post(
                url,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()

            result = response.json()
            translated = result["choices"][0]["message"]["content"].strip()

            if not translated:
                logger.warning("翻译返回空结果")
                self._safe_callback(callback, None)
                return

            with self._lock:
                self._cache[text] = translated
                self._cache.move_to_end(text)
                while len(self._cache) > self._MAX_CACHE_SIZE:
                    self._cache.popitem(last=False)

            elapsed = time.time() - start_time
            logger.debug("翻译完成，耗时 %.2f 秒: %s...", elapsed, text[:30])
            self._safe_callback(callback, translated)

        except requests.exceptions.Timeout:
            elapsed = time.time() - start_time
            logger.error("翻译请求超时 (%.1fs)", elapsed)
            self._safe_callback(callback, None)
        except requests.exceptions.RequestException as e:
            elapsed = time.time() - start_time
            logger.error("翻译请求失败 (%.1fs): %s", elapsed, e)
            # 重建 session：仅清空连接池，保留原有 headers（避免丢失 thinking 等配置）
            with self._lock:
                self._session.close()
                self._session = requests.Session()
                self._session.headers.update({
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}"
                })
            self._safe_callback(callback, None)
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error("解析翻译结果失败: %s", e)
            self._safe_callback(callback, None)
        except Exception:
            logger.exception("翻译异常")
            self._safe_callback(callback, None)

    def invalidate(self, text: str):
        """清除指定文本的翻译缓存"""
        with self._lock:
            self._cache.pop(text, None)

    def clear_cache(self):
        """清除翻译缓存"""
        with self._lock:
            self._cache.clear()

    def get_cached(self, text: str) -> Optional[str]:
        """获取缓存的翻译结果"""
        with self._lock:
            if text in self._cache:
                self._cache.move_to_end(text)
                return self._cache[text]
            return None


_translator: Optional[TranslatorService] = None
_translator_lock = threading.Lock()


def get_translator() -> TranslatorService:
    """获取全局翻译服务实例（线程安全单例）。

    加锁保护单例创建：多线程同时首次调用（如启动时多个 list_card 并发翻译）
    会创建多个实例，最后一个胜出，前几个的缓存丢失。
    """
    global _translator
    if _translator is None:
        with _translator_lock:
            if _translator is None:
                _translator = TranslatorService()
    return _translator

