import os
import hashlib
import threading
import requests
import logging
from PIL import Image, ImageTk
from collections import OrderedDict

logger = logging.getLogger('cache')

_thread_local = threading.local()


def get_http_session():
    if not hasattr(_thread_local, 'session'):
        _thread_local.session = requests.Session()
        _thread_local.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
    return _thread_local.session


class LRUCache:
    def __init__(self, capacity=100):
        self.capacity = capacity
        self.cache = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key):
        logger.debug("LRU.get key=%s", key[:50] if key else "")
        if self.lock.acquire(blocking=False):
            try:
                if key in self.cache:
                    self.cache.move_to_end(key)
                    return self.cache[key]
                return None
            finally:
                self.lock.release()
        logger.debug("LRU.get 锁被占用，跳过")
        return None

    def put(self, key, value):
        if self.lock.acquire(blocking=False):
            try:
                if key in self.cache:
                    self.cache.move_to_end(key)
                self.cache[key] = value
                if len(self.cache) > self.capacity:
                    self.cache.popitem(last=False)
            finally:
                self.lock.release()

    def remove(self, key):
        if self.lock.acquire(blocking=False):
            try:
                if key in self.cache:
                    del self.cache[key]
            finally:
                self.lock.release()


class ImageCacheManager:
    def __init__(self, cache_dir, max_memory=100, max_disk_mb=500):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.memory_cache = LRUCache(capacity=max_memory)
        self._thumbnail_size = (180, 180)
        self.max_disk_bytes = max_disk_mb * 1024 * 1024
        self._cleanup_lock = threading.Lock()

    def _get_cache_path(self, url):
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{url_hash}.jpg")

    def _resize_thumbnail(self, img):
        return img.copy().thumbnail(self._thumbnail_size, Image.Resampling.LANCZOS)

    def get(self, url):
        return self.get_thumbnail(url)

    def get_at_size(self, url, size):
        cache_key = f"load_{size}_{url}"
        logger.debug("get_at_size: key=%s", cache_key[:60])
        r = self.memory_cache.get(cache_key)
        logger.debug("get_at_size 完成: %s", r is not None)
        return r

    def get_image(self, url):
        cached = self.memory_cache.get(url)
        if cached:
            return cached

        cache_path = self._get_cache_path(url)
        if os.path.exists(cache_path):
            try:
                img = Image.open(cache_path)
                img.load()
                photo = ImageTk.PhotoImage(img)
                self.memory_cache.put(url, photo)
                return photo
            except Exception:
                return None
        return None

    def get_thumbnail(self, url):
        cache_key = f"thumb_{url}"
        logger.debug("get_thumbnail: key=%s", cache_key[:60])
        cached = self.memory_cache.get(cache_key)
        logger.debug("get_thumbnail 内存查完: %s", cached is not None)
        if cached:
            return cached

        cache_path = self._get_cache_path(url)
        if os.path.exists(cache_path):
            try:
                logger.debug("get_thumbnail 读磁盘: %s", cache_path[-30:])
                img = Image.open(cache_path)
                img.load()
                img_copy = img.copy()
                img_copy.thumbnail(self._thumbnail_size, Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img_copy)
                self.memory_cache.put(cache_key, photo)
                logger.debug("get_thumbnail 磁盘读取完成")
                return photo
            except Exception as e:
                logger.debug("get_thumbnail 异常: %s", e)
                return None
        logger.debug("get_thumbnail 磁盘无缓存")
        return None

    def save_image(self, url, img_data):
        cache_path = self._get_cache_path(url)
        try:
            if isinstance(img_data, bytes):
                import io
                img = Image.open(io.BytesIO(img_data))
            else:
                img = img_data

            if img.mode == 'RGBA':
                bg = Image.new('RGB', img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            img.save(cache_path, 'JPEG', quality=85, optimize=True)

            photo = ImageTk.PhotoImage(img)
            self.memory_cache.put(url, photo)
            self._schedule_disk_cleanup()
            return photo
        except Exception as e:
            print(f"保存图片失败: {e}")
            return None

    def save_thumbnail(self, url, img_data):
        cache_key = f"thumb_{url}"
        cache_path = self._get_cache_path(url)
        try:
            if isinstance(img_data, bytes):
                import io
                img = Image.open(io.BytesIO(img_data))
            else:
                img = img_data

            if img.mode == 'RGBA':
                bg = Image.new('RGB', img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            if not os.path.exists(cache_path):
                img.save(cache_path, 'JPEG', quality=85, optimize=True)

            img_copy = img.copy()
            img_copy.thumbnail(self._thumbnail_size, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img_copy)
            self.memory_cache.put(cache_key, photo)
            self._schedule_disk_cleanup()
            return photo
        except Exception as e:
            print(f"保存缩略图失败: {e}")
            return None

    def load_from_url(self, url, size=None):
        cache_key = f"load_{size}_{url}" if size else f"load_{url}"
        cached = self.memory_cache.get(cache_key)
        if cached:
            return cached

        pil_img = self._load_pil_from_url(url, size)
        if pil_img is None:
            return None
        photo = ImageTk.PhotoImage(pil_img)
        self.memory_cache.put(cache_key, photo)
        return photo

    def _load_pil_from_url(self, url, size=None):
        pil_cache_key = f"pil_{size}_{url}" if size else f"pil_{url}"
        cached = self.memory_cache.get(pil_cache_key)
        if cached:
            return cached

        cache_path = self._get_cache_path(url)
        if not os.path.exists(cache_path):
            try:
                resp = get_http_session().get(url, timeout=10)
                if resp.status_code != 200:
                    return None
                import io
                img = Image.open(io.BytesIO(resp.content))
                if img.mode == 'RGBA':
                    bg = Image.new('RGB', img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[3])
                    img = bg
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(cache_path, 'JPEG', quality=85, optimize=True)
            except Exception:
                return None

        try:
            img = Image.open(cache_path)
            img.load()
            if size:
                img = img.copy()
                img.thumbnail(size, Image.Resampling.LANCZOS)
            else:
                img = img.copy()
                img.thumbnail(self._thumbnail_size, Image.Resampling.LANCZOS)
            self.memory_cache.put(pil_cache_key, img)
            return img
        except Exception:
            return None

    def is_cached(self, url):
        cache_path = self._get_cache_path(url)
        return os.path.exists(cache_path)

    def clear_memory_cache(self):
        self.memory_cache.cache.clear()

    def get_stats(self):
        return {
            "memory_count": len(self.memory_cache.cache),
            "memory_capacity": self.memory_cache.capacity,
            "disk_path": self.cache_dir
        }

    def _schedule_disk_cleanup(self):
        if self._cleanup_lock.acquire(blocking=False):
            try:
                threading.Thread(target=self._cleanup_disk_cache, daemon=True).start()
            except Exception:
                self._cleanup_lock.release()

    def _cleanup_disk_cache(self):
        try:
            total_size = 0
            files = []
            for fname in os.listdir(self.cache_dir):
                fpath = os.path.join(self.cache_dir, fname)
                if os.path.isfile(fpath):
                    fsize = os.path.getsize(fpath)
                    ftime = os.path.getmtime(fpath)
                    files.append((fpath, fsize, ftime))
                    total_size += fsize

            if total_size <= self.max_disk_bytes:
                return

            files.sort(key=lambda x: x[2])
            for fpath, fsize, _ in files:
                if total_size <= self.max_disk_bytes * 0.8:
                    break
                try:
                    os.remove(fpath)
                    total_size -= fsize
                except Exception:
                    pass
        finally:
            self._cleanup_lock.release()
