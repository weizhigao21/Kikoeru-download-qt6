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
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json"
        })

    def update_config(self, api_key: str, base_url: str, model: str):
        """更新 API 配置"""
        self._api_key = api_key
        self._base_url = base_url.rstrip('/')
        for suffix in ('/chat/completions', '/chat/completions/'):
            if self._base_url.lower().endswith(suffix):
                self._base_url = self._base_url[:-len(suffix)]
                break
        self._base_url = self._base_url.rstrip('/')
        self._model = model
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}"
        })

    def translate(self, text: str, callback: Callable[[Optional[str]], None], timeout: int = 30):
        """
        异步翻译文本

        Args:
            text: 要翻译的文本
            callback: 翻译完成回调，参数为翻译结果或 None（失败时）
            timeout: 翻译超时时间（秒），默认 30 秒
        """
        if not text or not text.strip():
            try:
                callback(None)
            except Exception as e:
                logger.error(f"翻译回调异常: {e}")
            return

        with self._lock:
            if text in self._cache:
                cached = self._cache[text]
                if cached and cached.strip():
                    self._cache.move_to_end(text)
                    try:
                        callback(cached)
                    except Exception as e:
                        logger.error(f"翻译回调异常: {e}")
                    return
                else:
                    del self._cache[text]

        threading.Thread(
            target=self._translate_thread,
            args=(text, callback, timeout),
            daemon=True
        ).start()

    def _translate_thread(self, text: str, callback: Callable[[Optional[str]], None], timeout: int = 30):
        """翻译线程，带超时保护"""
        start_time = time.time()
        try:
            if not hasattr(self, '_api_key') or not self._api_key:
                logger.error("未配置 API Key")
                try:
                    callback(None)
                except Exception as e:
                    logger.error(f"翻译回调异常: {e}")
                return

            url = f"{self._base_url}/chat/completions"
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
                "temperature": 0.3,
                "max_tokens": 500
            }

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
                try:
                    callback(None)
                except Exception as e:
                    logger.error(f"翻译回调异常: {e}")
                return

            with self._lock:
                self._cache[text] = translated
                self._cache.move_to_end(text)
                while len(self._cache) > self._MAX_CACHE_SIZE:
                    self._cache.popitem(last=False)

            elapsed = time.time() - start_time
            logger.debug(f"翻译完成，耗时 {elapsed:.2f} 秒: {text[:30]}...")
            try:
                callback(translated)
            except Exception as e:
                logger.error(f"翻译回调异常: {e}")

        except requests.exceptions.Timeout as e:
            elapsed = time.time() - start_time
            logger.error(f"翻译请求超时 ({elapsed:.1f}s): {e}")
            try:
                callback(None)
            except Exception as cb_err:
                logger.error(f"翻译回调异常: {cb_err}")
        except requests.exceptions.RequestException as e:
            elapsed = time.time() - start_time
            logger.error(f"翻译请求失败 ({elapsed:.1f}s): {e}")
            self._session = requests.Session()
            self._session.headers.update({
                "Content-Type": "application/json",
                "Authorization": f"Bearer {getattr(self, '_api_key', '')}"
            })
            try:
                callback(None)
            except Exception as cb_err:
                logger.error(f"翻译回调异常: {cb_err}")
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error(f"解析翻译结果失败: {e}")
            try:
                callback(None)
            except Exception as cb_err:
                logger.error(f"翻译回调异常: {cb_err}")
        except Exception as e:
            logger.error(f"翻译异常: {e}")
            try:
                callback(None)
            except Exception as cb_err:
                logger.error(f"翻译回调异常: {cb_err}")

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


def get_translator() -> TranslatorService:
    """获取全局翻译服务实例"""
    global _translator
    if _translator is None:
        _translator = TranslatorService()
    return _translator
