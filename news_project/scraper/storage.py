import json
import os
from typing import Set, List, Dict, Any

try:
    from .config import DATA_DIR
except ImportError:
    from scraper.config import DATA_DIR

try:
    from google.cloud import storage as gcs
except ImportError:
    gcs = None

def _data_path(filename: str) -> str:
    """将裸文件名转换为基于 DATA_DIR 的绝对路径"""
    return os.path.join(DATA_DIR, filename)

class Storage:
    def __init__(self, file_path: str = "news_state.json"):
        self.file_path = _data_path(file_path)
        self.bucket_name = os.getenv("NEWS_BUCKET_NAME") # 如果设置了此环境变量，则使用 GCS
        self.seen_links: Set[str] = set()
        self.page_hashes: Dict[str, str] = {}
        self.load()

    def load(self):
        """加载已读文章链接 (优先 GCS，其次本地)"""
        if self.bucket_name and gcs:
            self._load_from_gcs()
        else:
            self._load_from_local()

    def save(self):
        """保存当前状态 (优先 GCS，其次本地)"""
        if self.bucket_name and gcs:
            self._save_to_gcs()
        else:
            self._save_to_local()

    def _load_from_local(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.seen_links = set(data.get("seen_links", []))
                    self.page_hashes = data.get("page_hashes", {})
                print(f"📂 [Local] Loaded history: {len(self.seen_links)} articles, {len(self.page_hashes)} page hashes.")
                
                # IMPORTANT: Also load links from History/Favorites files to ensure sync
                other_files = ["history_news.json", "history_arxiv.json", "favorites.json", "latest_news.json", "latest_arxiv.json"]
                for fname in other_files:
                    fpath = _data_path(fname)
                    if os.path.exists(fpath):
                        try:
                            with open(fpath, "r", encoding="utf-8") as f:
                                items = json.load(f)
                                for i in items:
                                    if i.get('link'):
                                        self.seen_links.add(i['link'])
                        except:
                            pass
                print(f"🔗 Aggregated seen links: {len(self.seen_links)}")

            except Exception as e:
                print(f"⚠ [Local] Failed to load state: {e}")
                self.seen_links = set()
                self.page_hashes = {}

    def _save_to_local(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump({
                    "seen_links": list(self.seen_links),
                    "page_hashes": self.page_hashes
                }, f, ensure_ascii=False, indent=2)
            # print("💾 [Local] State saved.")
        except Exception as e:
            print(f"❌ [Local] Failed to save state: {e}")

    def _load_from_gcs(self):
        try:
            client = gcs.Client()
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob(self.file_path)
            
            if blob.exists():
                data_str = blob.download_as_text()
                data = json.loads(data_str)
                self.seen_links = set(data.get("seen_links", []))
                self.page_hashes = data.get("page_hashes", {})
                print(f"☁ [GCS] Loaded history from {self.bucket_name}: {len(self.seen_links)} articles.")
            else:
                print(f"☁ [GCS] No history found in {self.bucket_name}, starting fresh.")
                self.seen_links = set()
                self.page_hashes = {}
        except Exception as e:
            print(f"⚠ [GCS] Failed to load state: {e}")
            self.seen_links = set()
            self.page_hashes = {}

    def _save_to_gcs(self):
        try:
            client = gcs.Client()
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob(self.file_path)
            
            data = json.dumps({
                "seen_links": list(self.seen_links),
                "page_hashes": self.page_hashes
            }, ensure_ascii=False, indent=2)
            
            blob.upload_from_string(data, content_type="application/json")
            print(f"☁ [GCS] State saved to {self.bucket_name}/{self.file_path}")
        except Exception as e:
            print(f"❌ [GCS] Failed to save state: {e}")

    def is_new(self, link: str) -> bool:
        """检查链接是否为新的"""
        return link not in self.seen_links

    def add_seen(self, link: str):
        """标记链接为已读"""
        self.seen_links.add(link)

    def get_page_hash(self, url: str) -> str:
        """获取保存的页面哈希值"""
        return self.page_hashes.get(url, "")

    def save_page_hash(self, url: str, content_hash: str):
        """保存页面哈希值"""
        self.page_hashes[url] = content_hash

    def filter_new_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """过滤出新文章"""
        new_articles = []
        for art in articles:
            link = art.get('link')
            if link and self.is_new(link):
                new_articles.append(art)
        return new_articles

    def load_favorites(self) -> List[Dict[str, Any]]:
        """加载收藏夹"""
        fav_path = _data_path("favorites.json")
        if not os.path.exists(fav_path):
            return []
        try:
            with open(fav_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠ Failed to load favorites: {e}")
            return []

    def save_to_favorites(self, article: Dict[str, Any]):
        """保存文章到收藏夹 (自动去重)"""
        fav_path = _data_path("favorites.json")
        favorites = self.load_favorites()
        
        # Check for duplicate link
        if any(f['link'] == article['link'] for f in favorites):
            print(f"⚠ Article already in favorites: {article['title']}")
            return

        favorites.insert(0, article) # Add to top
        try:
            with open(fav_path, "w", encoding="utf-8") as f:
                json.dump(favorites, f, ensure_ascii=False, indent=2)
            print(f"⭐ Saved to favorites: {article['title']}")
        except Exception as e:
            print(f"❌ Failed to save favorite: {e}")
