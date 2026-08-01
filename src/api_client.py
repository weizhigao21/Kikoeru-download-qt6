import requests
import time
import threading
from collections import OrderedDict


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
        self._results = {}
        self._lock = threading.Lock()

    def dedup(self, key, fetcher):
        with self._lock:
            if key in self._results:
                return True
            if key in self._inflight:
                evt = self._inflight[key]
        if 'evt' in dir():
            evt.wait()
            return True
        with self._lock:
            evt = threading.Event()
            self._inflight[key] = evt
        try:
            result = fetcher()
            with self._lock:
                self._results[key] = result
        finally:
            evt.set()
            with self._lock:
                self._inflight.pop(key, None)


_inflight = _InFlight()


def _fetch_or_dedup(key, fetcher):
    cached = _cache.get(key)
    if cached is not None:
        return cached
    try:
        _inflight.dedup(key, fetcher)
    except Exception:
        pass
    result = _cache.get(key)
    if result is None:
        result = fetcher()
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


def fetch_works_page(page: int, page_size: int = WORKS_PER_PAGE) -> tuple:
    key = _cache_key("works", page, page_size)

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
            total = data.get("total", 0)
            max_page = max(1, (total + page_size - 1) // page_size) if total else page + 1
            result = (works, max_page)
        _cache.put(key, result)
        return result

    return _fetch_or_dedup(key, do_fetch)


def fetch_latest_works_page(page: int, page_size: int = WORKS_PER_PAGE) -> tuple:
    key = _cache_key("latest", page, page_size)

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
            total = data.get("total", 0)
            max_page = max(1, (total + page_size - 1) // page_size) if total else page + 1
            result = (works, max_page)
        _cache.put(key, result)
        return result

    return _fetch_or_dedup(key, do_fetch)


def fetch_work_detail(rj_id):
    key = _cache_key("detail", rj_id)

    def do_fetch():
        rid = rj_id
        if str(rid).startswith("RJ"):
            rid = str(rid)[2:]
        rid = str(int(rid))
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
        rid = rj_id
        if str(rid).startswith("RJ"):
            rid = str(rid)[2:]
        rid = str(int(rid))
        url = f"{API_BASE_URL}/tracks/{rid}"
        params = {"v": "2"}
        data = _request_with_retry("GET", url, params=params)
        if data:
            _cache.put(key, data)
        return data

    return _fetch_or_dedup(key, do_fetch)


def search_by_tag(tags, page: int = 1, page_size: int = WORKS_PER_PAGE):
    encoded_tag = _encode_tags(tags)
    key = _cache_key("tag", encoded_tag, page, page_size)

    def do_fetch():
        url = f"{API_BASE_URL}/search/{encoded_tag}"
        params = {
            "page": page,
            "pageSize": page_size,
            "subtitle": "0",
            "djin": "false"
        }
        data = _request_with_retry("GET", url, params=params)
        if data is None:
            result = ([], 1)
        elif isinstance(data, dict) and "works" in data:
            works = data.get("works", [])
            total = data.get("total", 0)
            max_page = max(1, (total + page_size - 1) // page_size) if total else 1
            result = (works, max_page)
        elif isinstance(data, dict) and "data" in data:
            inner = data["data"]
            if isinstance(inner, dict) and "works" in inner:
                works = inner.get("works", [])
                total = inner.get("total", 0)
                max_page = max(1, (total + page_size - 1) // page_size) if total else 1
            elif isinstance(inner, list):
                works = inner
                max_page = page + 1 if len(works) >= page_size else page
            else:
                works = []
                max_page = 1
            result = (works, max_page)
        elif isinstance(data, list):
            result = (data, page + 1 if len(data) >= page_size else page)
        else:
            result = ([], 1)
        _cache.put(key, result)
        return result

    return _fetch_or_dedup(key, do_fetch)


def search_by_keyword(keyword, page: int = 1, page_size: int = WORKS_PER_PAGE):
    encoded_keyword = requests.utils.quote(keyword)
    key = _cache_key("keyword", encoded_keyword, page, page_size)

    def do_fetch():
        url = f"{API_BASE_URL}/search/{encoded_keyword}"
        params = {
            "page": page,
            "pageSize": page_size,
            "subtitle": "0",
            "djin": "false"
        }
        data = _request_with_retry("GET", url, params=params)
        if data is None:
            result = ([], 1)
        elif isinstance(data, dict) and "works" in data:
            works = data.get("works", [])
            total = data.get("total", 0)
            max_page = max(1, (total + page_size - 1) // page_size) if total else 1
            result = (works, max_page)
        elif isinstance(data, dict) and "data" in data:
            inner = data["data"]
            if isinstance(inner, dict) and "works" in inner:
                works = inner.get("works", [])
                total = inner.get("total", 0)
                max_page = max(1, (total + page_size - 1) // page_size) if total else 1
            elif isinstance(inner, list):
                works = inner
                max_page = page + 1 if len(works) >= page_size else page
            else:
                works = []
                max_page = 1
            result = (works, max_page)
        elif isinstance(data, list):
            result = (data, page + 1 if len(data) >= page_size else page)
        else:
            result = ([], 1)
        _cache.put(key, result)
        return result

    return _fetch_or_dedup(key, do_fetch)


def search_by_circle(circle_name, page: int = 1, page_size: int = WORKS_PER_PAGE):
    key = _cache_key("circle", circle_name, page, page_size)

    def do_fetch():
        encoded_name = requests.utils.quote(f"$circle:{circle_name}$")
        url = f"{API_BASE_URL}/search/{encoded_name}"
        params = {
            "page": page,
            "pageSize": page_size,
            "subtitle": "0",
            "djin": "false"
        }
        data = _request_with_retry("GET", url, params=params)
        if data is None:
            result = ([], 1)
        elif isinstance(data, dict) and "works" in data:
            works = data.get("works", [])
            total = data.get("total", 0)
            max_page = max(1, (total + page_size - 1) // page_size) if total else 1
            result = (works, max_page)
        elif isinstance(data, dict) and "data" in data:
            inner = data["data"]
            if isinstance(inner, dict) and "works" in inner:
                works = inner.get("works", [])
                total = inner.get("total", 0)
                max_page = max(1, (total + page_size - 1) // page_size) if total else 1
            elif isinstance(inner, list):
                works = inner
                max_page = page + 1 if len(works) >= page_size else page
            else:
                works = []
                max_page = 1
            result = (works, max_page)
        elif isinstance(data, list):
            result = (data, page + 1 if len(data) >= page_size else page)
        else:
            result = ([], 1)
        _cache.put(key, result)
        return result

    return _fetch_or_dedup(key, do_fetch)


def _encode_tags(tags):
    if isinstance(tags, list):
        return requests.utils.quote(" ".join(tags), safe='')
    return requests.utils.quote(str(tags), safe='')


def clear_api_cache():
    _cache.clear()


class APIClient:
    def fetch_works_page(self, page, page_size=WORKS_PER_PAGE):
        return fetch_works_page(page, page_size)

    def fetch_latest_works_page(self, page, page_size=WORKS_PER_PAGE):
        return fetch_latest_works_page(page, page_size)

    def fetch_work_detail(self, rj_id):
        return fetch_work_detail(rj_id)

    def fetch_tracks(self, rj_id):
        return fetch_tracks(rj_id)

    def search_by_tag(self, tags, page=1, page_size=WORKS_PER_PAGE):
        return search_by_tag(tags, page, page_size)

    def search_by_keyword(self, keyword, page=1, page_size=WORKS_PER_PAGE):
        return search_by_keyword(keyword, page, page_size)

    def search_by_circle(self, circle_name, page=1, page_size=WORKS_PER_PAGE):
        return search_by_circle(circle_name, page, page_size)


def get_api_client():
    return APIClient()
