import os
import hashlib
import threading
import time
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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "ja,zh-CN;q=0.9,zh;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Sec-Ch-Ua": "\"Google Chrome\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": "\"Windows\"",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "cross-site",
        })
    return _thread_local.session


class LRUCache:
    def __init__(self, capacity=100):
        self.capacity = capacity
        self.cache = OrderedDict()
        self.lock = threading.RLock()
        self._stats = {"hits": 0, "misses": 0, "skips": 0}

    def get(self, key):
        logger.debug("LRU.get key=%s", key[:50] if key else "")
        acquired = self.lock.acquire(timeout=0.01)  # 10ms超时
        if acquired:
            try:
                if key in self.cache:
                    self.cache.move_to_end(key)
                    self._stats["hits"] += 1
                    return self.cache[key]
                self._stats["misses"] += 1
                return None
            finally:
                self.lock.release()
        else:
            self._stats["skips"] += 1
            logger.debug("LRU.get 锁超时，跳过 (key=%s)", key[:30] if key else "")
            return None

    def put(self, key, value):
        acquired = self.lock.acquire(timeout=0.02)  # 20ms超时（写入可以稍长）
        if acquired:
            try:
                if key in self.cache:
                    self.cache.move_to_end(key)
                self.cache[key] = value
                if len(self.cache) > self.capacity:
                    self.cache.popitem(last=False)
            finally:
                self.lock.release()

    def remove(self, key):
        acquired = self.lock.acquire(timeout=0.01)
        if acquired:
            try:
                if key in self.cache:
                    del self.cache[key]
            finally:
                self.lock.release()

    def clear(self):
        """加锁清空缓存，避免 clear_memory_cache 直接操作内部 OrderedDict 绕过锁保护"""
        acquired = self.lock.acquire(timeout=0.05)
        if acquired:
            try:
                self.cache.clear()
            finally:
                self.lock.release()

    def get_stats(self):
        total = self._stats["hits"] + self._stats["misses"] + self._stats["skips"]
        if total == 0:
            return {"hit_rate": 0, "total_lookups": 0}
        hit_rate = self._stats["hits"] / (self._stats["hits"] + self._stats["misses"]) * 100
        return {
            "hit_rate": round(hit_rate, 1),
            "total_lookups": total,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "skips": self._stats["skips"]
        }

    def clear_stats(self):
        with self.lock:
            self._stats = {"hits": 0, "misses": 0, "skips": 0}


class ImageCacheManager:
    def __init__(self, cache_dir, max_memory=100, max_disk_mb=500):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.memory_cache = LRUCache(capacity=max_memory)
        self._thumbnail_size = (180, 180)
        self.max_disk_bytes = max_disk_mb * 1024 * 1024
        self._cleanup_lock = threading.Lock()
        self._preload_queue = []     # 有序预加载队列（按距离当前位置排序）
        self._preload_set = set()    # 去重辅助集合
        self._preloading = False    # 预加载进行中标志

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

    def _process_image(self, img_data):
        """将 bytes 或 PIL.Image 转换为 RGB 模式的 PIL.Image（处理 RGBA 透明通道）。

        save_image 和 save_thumbnail 共用的图像预处理逻辑。
        """
        import io
        if isinstance(img_data, bytes):
            img = Image.open(io.BytesIO(img_data))
        else:
            img = img_data

        if img.mode == 'RGBA':
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        return img

    def save_image(self, url, img_data):
        cache_path = self._get_cache_path(url)
        try:
            img = self._process_image(img_data)
            img.save(cache_path, 'JPEG', quality=85, optimize=True)

            photo = ImageTk.PhotoImage(img)
            self.memory_cache.put(url, photo)
            self._schedule_disk_cleanup()
            return photo
        except Exception as e:
            logger.exception("保存图片失败")
            return None

    def save_thumbnail(self, url, img_data):
        cache_key = f"thumb_{url}"
        cache_path = self._get_cache_path(url)
        try:
            img = self._process_image(img_data)

            if not os.path.exists(cache_path):
                img.save(cache_path, 'JPEG', quality=85, optimize=True)

            img_copy = img.copy()
            img_copy.thumbnail(self._thumbnail_size, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img_copy)
            self.memory_cache.put(cache_key, photo)
            self._schedule_disk_cleanup()
            return photo
        except Exception as e:
            logger.exception("保存缩略图失败")
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
        self.memory_cache.clear()
        self.memory_cache.clear_stats()

    def get_stats(self):
        disk_size = 0
        if os.path.exists(self.cache_dir):
            for f in os.listdir(self.cache_dir):
                try:
                    disk_size += os.path.getsize(os.path.join(self.cache_dir, f))
                except Exception:
                    pass

        return {
            "memory_count": len(self.memory_cache.cache),
            "memory_capacity": self.memory_cache.capacity,
            "disk_path": self.cache_dir,
            "disk_size_mb": round(disk_size / (1024 * 1024), 2),
            **self.memory_cache.get_stats()
        }

    def preload_thumbnails(self, urls, current_index=0):
        """智能预加载缩略图（前后各3张，按距离当前位置排序）"""
        if not urls or self._preloading:
            return

        # 计算需要预加载的范围
        preload_range = 3
        start = max(0, current_index - preload_range)
        end = min(len(urls), current_index + preload_range + 1)

        # 按距离当前位置排序，优先加载最近的
        urls_to_preload = []
        for i in range(start, end):
            u = urls[i]
            if u and u not in self._preload_set:
                urls_to_preload.append(u)
                self._preload_set.add(u)

        # 按距离排序后追加到队列
        urls_to_preload.sort(key=lambda u: abs(urls.index(u) - current_index))
        self._preload_queue.extend(urls_to_preload)

        if not self._preloading and self._preload_queue:
            self._preloading = True
            threading.Thread(target=self._preload_worker, daemon=True).start()

    def _preload_worker(self):
        """后台预加载工作线程"""
        try:
            while self._preload_queue:
                url = self._preload_queue.pop(0)
                self._preload_set.discard(url)
                if not url:
                    continue

                # 检查是否已在缓存中
                cache_key = f"thumb_{url}"
                if self.memory_cache.get(cache_key):
                    continue

                # 尝试从磁盘加载或下载
                self.get_thumbnail(url)

                # 短暂休眠，避免占用过多资源
                time.sleep(0.05)
        finally:
            self._preloading = False

    def _schedule_disk_cleanup(self):
        # acquire 成功后启动清理线程，_cleanup_disk_cache 的 finally 负责释放锁
        # Thread 启动几乎不会失败，无需 try/except
        if self._cleanup_lock.acquire(blocking=False):
            threading.Thread(target=self._cleanup_disk_cache, daemon=True).start()

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
