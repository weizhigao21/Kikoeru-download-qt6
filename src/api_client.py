import requests
import time
import threading
from collections import OrderedDict

from src.utils import strip_rj_prefix


class _APICache:
    def __init__(self, max_size=50, ttl=300):
        self._cache = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if time.time() - entry["time"] < self._ttl:
                    self._cache.move_to_end(key)
                    return entry["data"]
                else:
                    del self._cache[key]
            return None

    def put(self, key, data):
        with self._lock:
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = {"data": data, "time": time.time()}

    def clear(self):
        with self._lock:
            self._cache.clear()


API_BASE_URL = "https://api.asmr-200.com/api"
WORKS_PER_PAGE = 20
MAX_RETRIES = 3
RETRY_DELAY = 1

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
})
_cache = _APICache(max_size=100, ttl=120)


class _InFlight:
    def __init__(self):
        self._inflight = {}
        self._lock = threading.Lock()

    def dedup(self, key, fetcher):
        """去重并发请求。第一个调用者执行 fetcher，后续调用者等待结果。

        Returns:
            fetcher 的返回值（所有等待者获得相同结果）
        Raises:
            透传 fetcher 抛出的异常（所有等待者获得相同异常）
        """
        with self._lock:
            existing = self._inflight.get(key)
            if existing is not None:
                # 已有在途请求，等待其完成
                evt, result_holder, error_holder = existing
            else:
                # 首个调用者：注册 Event 并负责执行 fetcher
                evt = threading.Event()
                result_holder = {}
                error_holder = {}
                self._inflight[key] = (evt, result_holder, error_holder)

        if existing is not None:
            # 等待者：阻塞至首个调用者完成，复用其结果或异常
            evt.wait()
            if error_holder:
                raise error_holder["error"]
            return result_holder.get("result")

        # 首个调用者：执行 fetcher 并通知所有等待者
        try:
            result = fetcher()
            result_holder["result"] = result
            return result
        except Exception as e:
            error_holder["error"] = e
            raise
        finally:
            evt.set()
            with self._lock:
                self._inflight.pop(key, None)


_inflight = _InFlight()


def _fetch_or_dedup(key, fetcher):
    cached = _cache.get(key)
    if cached is not None:
        return cached
    result = _inflight.dedup(key, fetcher)
    # fetcher 成功时已通过 _cache.put 缓存结果，这里取缓存保持返回值一致
    if result is not None:
        cached_result = _cache.get(key)
        if cached_result is not None:
            return cached_result
    return result


def _request_with_retry(method, url, max_retries=MAX_RETRIES, **kwargs):
    for attempt in range(max_retries):
        try:
            response = _session.request(method, url, timeout=15, **kwargs)
            if response.status_code == 200:
                return response.json()
            if response.status_code == 404:
                return None
            if response.status_code == 429:
                # 优先读取 Retry-After 头，回退到指数退避
                retry_after = response.headers.get("Retry-After")
                if retry_after is not None:
                    try:
                        wait = min(float(retry_after), 60)
                    except ValueError:
                        wait = RETRY_DELAY * (2 ** attempt)
                else:
                    wait = RETRY_DELAY * (2 ** attempt)
                time.sleep(wait)
                continue
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait = RETRY_DELAY * (2 ** attempt)
                time.sleep(wait)
            else:
                raise
    return None


def _cache_key(*args):
    return "|".join(str(a) for a in args)


def _extract_total(data) -> int:
    """从响应提取作品总数，兼容 data['total'] 与 data['pagination']['totalCount']。"""
    if not isinstance(data, dict):
        return 0
    total = data.get("total") or 0
    if total:
        return total
    pagination = data.get("pagination")
    if isinstance(pagination, dict):
        return pagination.get("totalCount") or 0
    return 0


def _fetch_works_page_impl(key_prefix, page, page_size):
    """推荐作品 / 最新收录 共用的作品列表获取实现（两者请求 URL 和参数完全相同）。"""
    key = _cache_key(key_prefix, page, page_size)

    def do_fetch():
        url = f"{API_BASE_URL}/works"
        params = {
            "page": page,
            "pageSize": page_size,
            "subtitle": "0"
        }
        data = _request_with_retry("GET", url, params=params)
        if data is None:
            result = ([], 1)
        elif isinstance(data, list):
            works = data
            max_page = page + 1 if len(works) >= page_size else page
            result = (works, max_page)
        else:
            works = data.get("works", data.get("list", []))
            total = _extract_total(data)
            max_page = max(1, (total + page_size - 1) // page_size) if total else page + 1
            result = (works, max_page)
        _cache.put(key, result)
        return result

    return _fetch_or_dedup(key, do_fetch)


def fetch_works_page(page: int, page_size: int = WORKS_PER_PAGE) -> tuple:
    return _fetch_works_page_impl("works", page, page_size)


def fetch_latest_works_page(page: int, page_size: int = WORKS_PER_PAGE) -> tuple:
    return _fetch_works_page_impl("latest", page, page_size)


def fetch_work_detail(rj_id):
    key = _cache_key("detail", rj_id)

    def do_fetch():
        rid = strip_rj_prefix(rj_id)
        url = f"{API_BASE_URL}/workInfo/{rid}"
        params = {"v": "2"}
        data = _request_with_retry("GET", url, params=params)
        if data:
            _cache.put(key, data)
        return data

    return _fetch_or_dedup(key, do_fetch)


def fetch_tracks(rj_id):
    key = _cache_key("tracks", rj_id)

    def do_fetch():
        rid = strip_rj_prefix(rj_id)
        url = f"{API_BASE_URL}/tracks/{rid}"
        params = {"v": "2"}
        data = _request_with_retry("GET", url, params=params)
        if data:
            _cache.put(key, data)
        return data

    return _fetch_or_dedup(key, do_fetch)


def search_by_tag(tags, page: int = 1, page_size: int = WORKS_PER_PAGE, circle: str = None):
    """按标签搜索；circle 非空时与厂商组合过滤（`$circle:xx$ $tag:yy$` 空格分隔，实测有效）。"""
    encoded_tag = _encode_tags(tags, circle)
    key = _cache_key("tag", encoded_tag, page, page_size)
    return _search_impl(key, encoded_tag, page, page_size)


def search_by_keyword(keyword, page: int = 1, page_size: int = WORKS_PER_PAGE):
    encoded_keyword = requests.utils.quote(keyword)
    key = _cache_key("keyword", encoded_keyword, page, page_size)
    return _search_impl(key, encoded_keyword, page, page_size)


def search_by_circle(circle_name, page: int = 1, page_size: int = WORKS_PER_PAGE):
    encoded_name = requests.utils.quote(f"$circle:{circle_name}$")
    key = _cache_key("circle", circle_name, page, page_size)
    return _search_impl(key, encoded_name, page, page_size)


def _parse_search_response(data, page, page_size):
    """解析搜索 API 响应为 (works, max_page) 元组。

    兼容多种响应格式：None / list / {"works":...} / {"data":{"works":...}} / {"data":[...]}。
    """
    if data is None:
        return ([], 1)
    if isinstance(data, dict) and "works" in data:
        works = data.get("works", [])
        total = _extract_total(data)
        max_page = max(1, (total + page_size - 1) // page_size) if total else 1
        return (works, max_page)
    if isinstance(data, dict) and "data" in data:
        inner = data["data"]
        if isinstance(inner, dict) and "works" in inner:
            works = inner.get("works", [])
            total = _extract_total(inner) or _extract_total(data)
            max_page = max(1, (total + page_size - 1) // page_size) if total else 1
        elif isinstance(inner, list):
            works = inner
            max_page = page + 1 if len(works) >= page_size else page
        else:
            works = []
            max_page = 1
        return (works, max_page)
    if isinstance(data, list):
        return (data, page + 1 if len(data) >= page_size else page)
    return ([], 1)


def _search_impl(key, encoded_query, page, page_size):
    """tag/keyword/circle 三种搜索共用的请求实现。"""
    def do_fetch():
        url = f"{API_BASE_URL}/search/{encoded_query}"
        params = {
            "page": page,
            "pageSize": page_size,
            "subtitle": "0",
            "djin": "false"
        }
        data = _request_with_retry("GET", url, params=params)
        result = _parse_search_response(data, page, page_size)
        _cache.put(key, result)
        return result

    return _fetch_or_dedup(key, do_fetch)


def _encode_tags(tags, circle: str = None):
    """标签/厂商搜索编码。

    - 厂商块：`$circle:xx$`（对齐 README 厂商搜索接口）。
    - 标签块：单标签用 `$tag:xx$` 精确语法，避免被后端当作全文关键词混入标题匹配的作品；
      多标签后端不支持 `$tag:a$$tag:b$`（返回 0），退化为空格分隔 AND。
    - 组合：`$circle:xx$ $tag:yy$` 空格分隔（紧挨会返回 0 结果，实测）。
    """
    tag_list = tags if isinstance(tags, list) else [tags]
    parts = []
    if circle:
        parts.append(f"$circle:{circle}$")
    if tag_list:
        if len(tag_list) == 1:
            parts.append(f"$tag:{tag_list[0]}$")
        else:
            parts.append(" ".join(tag_list))
    return requests.utils.quote(" ".join(parts), safe='')


def clear_api_cache():
    _cache.clear()


class APIClient:
    """API 客户端薄封装。所有方法委托到模块级函数，共享全局 session/缓存/去重。

    可选注入 session 和 cache 以便测试替换；默认使用模块级单例。
    """

    def __init__(self, session=None, cache=None):
        self._session = session if session is not None else _session
        self._cache = cache if cache is not None else _cache

    def fetch_works_page(self, page, page_size=WORKS_PER_PAGE):
        return fetch_works_page(page, page_size)

    def fetch_latest_works_page(self, page, page_size=WORKS_PER_PAGE):
        return fetch_latest_works_page(page, page_size)

    def fetch_work_detail(self, rj_id):
        return fetch_work_detail(rj_id)

    def fetch_tracks(self, rj_id):
        return fetch_tracks(rj_id)

    def search_by_tag(self, tags, page=1, page_size=WORKS_PER_PAGE, circle=None):
        return search_by_tag(tags, page, page_size, circle)

    def search_by_keyword(self, keyword, page=1, page_size=WORKS_PER_PAGE):
        return search_by_keyword(keyword, page, page_size)

    def search_by_circle(self, circle_name, page=1, page_size=WORKS_PER_PAGE):
        return search_by_circle(circle_name, page, page_size)


def get_api_client():
    return APIClient()
