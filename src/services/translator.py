import requests
import json
import threading
import logging
import time
import re
from typing import Optional, Callable
from collections import OrderedDict

logger = logging.getLogger('translator')


class TranslatorService:
    """AI 翻译服务 - 使用 OpenAI 兼容 API"""

    _MAX_CACHE_SIZE = 500

    def __init__(self):
        self._cache: OrderedDict = OrderedDict()
        self._explain_cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        # 初始化配置属性，避免 update_config 未调用时 _translate_thread 访问 _base_url 抛 AttributeError
        self._api_key = ""
        self._base_url = ""
        self._model = ""
        self._thinking_enabled = True
        self._context = ""  # 翻译上下文/风格提示（用户可自定义，注入翻译 system prompt）
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

    def update_config(self, api_key: str, base_url: str, model: str, thinking_enabled: bool = True,
                      context: str = ""):
        """更新 API 配置

        Args:
            context: 翻译上下文/风格提示（用户自定义，注入翻译 system prompt；
                     空字符串 = 不注入，拆解请求不受影响）
        """
        self._api_key = api_key
        self._base_url = base_url.rstrip('/')
        for suffix in ('/chat/completions', '/chat/completions/'):
            if self._base_url.lower().endswith(suffix):
                self._base_url = self._base_url[:-len(suffix)]
                break
        self._base_url = self._base_url.rstrip('/')
        self._model = model
        self._thinking_enabled = thinking_enabled
        self._context = (context or "").strip()
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

    def explain(self, text: str, callback: Callable[[Optional[str]], None], timeout: Optional[int] = None):
        """异步生成词义拆解（逐词解释 + 整体理解）。

        与 translate() 同模式：空文本直接回调 None；缓存命中直接回调；
        未命中启动后台线程（prompt / max_tokens / 缓存按 explain 分流）。
        """
        if timeout is None:
            timeout = 90 if getattr(self, '_thinking_enabled', True) else 30
        if not text or not text.strip():
            self._safe_callback(callback, None)
            return

        with self._lock:
            if text in self._explain_cache:
                cached = self._explain_cache[text]
                if cached and cached.strip():
                    self._explain_cache.move_to_end(text)
                    self._safe_callback(callback, cached)
                    return
                else:
                    del self._explain_cache[text]

        threading.Thread(
            target=self._translate_thread,
            args=(text, callback, timeout, "explain"),
            daemon=True
        ).start()

    def _translate_thread(self, text: str, callback: Callable[[Optional[str]], None], timeout: int = 30,
                          mode: str = "translate"):
        """翻译/拆解线程，带超时保护 + 结果清洗 + 思考模式降级重试。

        Args:
            mode: "translate" 标题翻译 / "explain" 词义拆解（prompt、max_tokens、缓存按 mode 分流）
        """
        start_time = time.time()
        try:
            if not self._api_key:
                logger.error("未配置 API Key")
                self._safe_callback(callback, None)
                return

            thinking_enabled = self._thinking_enabled
            translated = self._request_translation(text, timeout, thinking_enabled, mode)

            # 思考模式 content 为空（DeepSeek thinking 常见）→ 自动降级普通模式重试一次
            if translated is None and thinking_enabled:
                logger.warning("思考模式未产出%s，降级为普通模式重试",
                               "译文" if mode == "translate" else "拆解")
                translated = self._request_translation(text, timeout, thinking=False, mode=mode)

            if not translated:
                logger.warning("%s返回空结果", "翻译" if mode == "translate" else "拆解")
                self._safe_callback(callback, None)
                return

            cache = self._cache if mode == "translate" else self._explain_cache
            with self._lock:
                cache[text] = translated
                cache.move_to_end(text)
                while len(cache) > self._MAX_CACHE_SIZE:
                    cache.popitem(last=False)

            elapsed = time.time() - start_time
            logger.debug("%s完成，耗时 %.2f 秒: %s...",
                         "翻译" if mode == "translate" else "拆解", elapsed, text[:30])
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

    # ---------- 请求与结果提取 ----------
    _SYSTEM_PROMPT = (
        "你是一个专业的日语→简体中文翻译引擎。严格遵守以下规则：\n"
        "1. 只输出译文本身，禁止输出任何解释、注释、前缀、后缀、引号或 Markdown 格式；\n"
        "2. 禁止输出代码块（```）、JSON、列表编号等包装形式；\n"
        "3. 译文必须完整覆盖源文本的全部内容，不得省略、概括或添加；\n"
        "4. 即使源文本是片假名、拟声词、专有名词、作品标题，也要尽力直译或音译，不得拒绝翻译；\n"
        "5. 如果输入本身不是日语，原样返回输入文本。"
    )

    _EXPLAIN_SYSTEM_PROMPT = (
        "你是一个专业的日语→简体中文标题解说引擎。对给定的日文作品标题做逐词拆解。\n"
        "严格遵守以下规则：\n"
        "1. 只拆解有解释价值的词/短语：自造词、拟声拟态词、专有名词、古语或戏剧化写法、"
        "口语缩略/拉长音、俚语；跳过普通助词（は/が/の/に 等）和显而易见的常用词；\n"
        "2. 每行一条，格式「词：解释」，解释用简体中文，单条不超过 30 字；"
        "自造词需拆词源（如 ムチプリーナ = ムチ+プリ+ーナ）；\n"
        "3. 输出 8-12 条，宁缺毋滥；\n"
        "4. 最后一行以「整体理解：」开头，用 1-2 句概括标题含义与语气氛围；\n"
        "5. 禁止输出其他任何内容、前缀、Markdown 或代码块；\n"
        "6. 输入不是日语时，仅输出「整体理解：」加一句话说明。"
    )

    def _request_translation(self, text: str, timeout: int, thinking: bool, mode: str = "translate") -> Optional[str]:
        """单次请求：构造 payload → 发送 → 清洗提取结果。

        翻译/拆解共用（按 mode 分流 prompt、user 消息、max_tokens）。
        返回清洗后的结果；content 为空时尝试从 reasoning_content 提取；
        仍为空则返回 None（由调用方决定降级/失败）。
        """
        url = f"{self._base_url}/chat/completions"
        if mode == "explain":
            system_prompt = self._EXPLAIN_SYSTEM_PROMPT
            user_content = f"对下面文本做逐词拆解：\n{text}"
            max_tokens = 4096 if thinking else 2048
        else:
            system_prompt = self._SYSTEM_PROMPT
            # 翻译上下文/风格提示（v2.2.1）：用户自定义，追加到 system prompt 尾部
            if self._context:
                system_prompt = system_prompt + "\n\n" + self._context
            user_content = f"直接输出下面文本的简体中文译文：\n{text}"
            max_tokens = 2048 if thinking else 800
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "max_tokens": max_tokens,
        }
        if thinking:
            # DeepSeek 思考模式：开启思考并限制推理强度；该模式下不支持 temperature
            payload["thinking"] = {"type": "enabled"}
            payload["reasoning_effort"] = "high"
        else:
            payload["temperature"] = 0.3

        response = self._session.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        msg = result["choices"][0]["message"]

        # 1) 常规 content
        raw = (msg.get("content") or "").strip()
        translated = self._clean_output(raw)
        if translated:
            return translated

        # 2) 思考模式下 content 可能为空 → 从 reasoning_content 提取译文
        reasoning = (msg.get("reasoning_content") or "").strip()
        translated = self._clean_output(self._extract_from_reasoning(reasoning))
        if translated:
            logger.debug("从 reasoning_content 提取到译文")
            return translated
        return None

    def _extract_from_reasoning(self, reasoning: str) -> Optional[str]:
        """从思考过程（reasoning_content）中提取最终译文。

        优先找「译文/翻译结果/最终答案是」等标记行的冒号后内容；
        无标记时取最后一行（思考结束通常紧跟最终答案）。
        """
        if not reasoning:
            return None
        lines = [ln.strip() for ln in reasoning.splitlines() if ln.strip()]
        if not lines:
            return None
        for i, ln in enumerate(lines):
            m = re.search(r'(?:译文|翻译结果|最终译文|最终答案|答案是|因此结果是)\s*[:：]?\s*(.*)$', ln)
            if m:
                tail = m.group(1).strip().strip('"\'“”')
                if tail and not re.fullmatch(r'[\s\-—=~·.。、，,]+', tail):
                    return tail
                # 冒号后为空 → 取下一行
                if i + 1 < len(lines):
                    cand = lines[i + 1].strip().strip('"\'“”')
                    if cand:
                        return cand
        return lines[-1].strip('"\'“”') or None

    def _clean_output(self, raw: Optional[str]) -> Optional[str]:
        """清洗模型输出：剥掉代码块 / JSON 包裹 / 成对引号 / 解释前缀。

        返回干净译文；无法提取或模型拒绝翻译时返回 None。
        """
        if not raw:
            return None
        text = raw.strip()
        if not text:
            return None

        # 1) Markdown 代码块（```...``` 或 ```lang\n...\n```）
        m = re.search(r'```(?:[a-zA-Z0-9_+-]*)\s*\n?(.*?)```', text, re.S)
        if m and m.group(1).strip():
            text = m.group(1).strip()
        # 2) JSON 包裹：{"translation": "..."} / {"result": "..."} 等
        m = re.search(r'\{[^{}]*"(?:translation|result|text|translated|译文|翻译|内容)"\s*:\s*"((?:[^"\\]|\\.)*)"\s*\}', text, re.S)
        if m and m.group(1).strip():
            text = m.group(1).strip()
        # 3) 成对包裹引号（ASCII 双引号/单引号、中文双引号“”）
        if len(text) >= 2:
            if (text[0] == text[-1] == '"') or (text[0] == text[-1] == "'"):
                text = text[1:-1].strip()
            elif text[0] == '\u201c' and text[-1] == '\u201d':
                text = text[1:-1].strip()
        # 4) 解释前缀：如「以下是翻译结果：」「翻译：」「译文：」
        text = re.sub(r'^(?:以下是?|这是)?(?:其)?\s*(?:简体中文)?\s*(?:翻译|译文|中文翻译)\s*(?:结果|内容)?\s*[:：]\s*', '', text)
        # 5) 模型拒绝/无法翻译 → 视为失败
        if re.search(r'^(?:抱歉|对不起|不好意思|很抱歉)[，,]?\s*(?:我)?(?:无法|不能|无法进行|拒绝|没有权限|暂不)', text):
            return None
        # 6) 纯占位/无意义输出
        if not text or re.fullmatch(r'[\s\-—=~·.。、，,]+', text):
            return None
        return text

    def invalidate(self, text: str):
        """清除指定文本的翻译缓存"""
        with self._lock:
            self._cache.pop(text, None)

    def clear_cache(self):
        """清除翻译与拆解缓存"""
        with self._lock:
            self._cache.clear()
            self._explain_cache.clear()

    def get_cached(self, text: str) -> Optional[str]:
        """获取缓存的翻译结果"""
        with self._lock:
            if text in self._cache:
                self._cache.move_to_end(text)
                return self._cache[text]
            return None

    def get_explained(self, text: str) -> Optional[str]:
        """获取缓存的词义拆解结果（不触发请求）"""
        with self._lock:
            if text in self._explain_cache:
                self._explain_cache.move_to_end(text)
                return self._explain_cache[text]
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

