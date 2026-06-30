import os

from .observability import get_logger


logger = get_logger(__name__)

# 项目根目录 (仓库根目录)
# config.py 在 news_project/scraper/config.py, 所以向上两级就是仓库根目录
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# 目标网站列表
TARGET_URLS = [
    "https://about.fb.com/news/",
    "https://ai.meta.com/blog/",
    "https://openai.com/research/index/",
    "https://blog.google/products/search/",
    "https://www.apple.com/newsroom/",
    "https://newsroom.tiktok.com/?lang=en",
    "https://www.aboutamazon.com/amazon-news-today",
    "https://machinelearning.apple.com/updates",
    'https://www.theverge.com/tech',
    "https://arxiv.org/list/cs.HC/recent",
    "https://arxiv.org/list/cs.MA/recent",
    "https://arxiv.org/list/cs.MM/recent",
    'https://blog.google/technology/google-deepmind/',
    'https://www.media.mit.edu/',
    'https://hci.stanford.edu/research/',
    'https://www.microsoft.com/en-us/research/blog/',
    'https://blogs.nvidia.com/',
    'https://www.microsoft.com/en-us/research/lab/mixed-reality-ai-lab-cambridge/publications/',
    'https://www.microsoft.com/en-us/research/lab/ai-frontiers/publications/',
    'https://pi.cs.tsinghua.edu.cn/publication/',
    'https://icilab.cn/publication/',
    
]    



# LLM API configuration.
# Prefer Gemini environment variables; local development can use gemini_api_key.txt.
LLM_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API") or os.getenv("GOOGLE_API_KEY") or ""
LLM_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
LLM_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

# If running locally, load the API key from the local file.
local_key_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "gemini_api_key.txt"))
if os.path.exists(local_key_path):
    try:
        with open(local_key_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GEMINI_API_KEY="):
                    LLM_API_KEY = line.split("=", 1)[1].strip()
                    break
                if line and "=" not in line:
                    LLM_API_KEY = line
                    break
    except Exception as e:
        logger.warning("local_api_key_read_failed error=%s", e)

DEEPSEEK_API_KEY = LLM_API_KEY
DEEPSEEK_BASE_URL = LLM_BASE_URL

if LLM_API_KEY:
    logger.debug("llm_api_key_configured model=%s", LLM_MODEL)
else:
    logger.warning("llm_api_key_missing")

# 🍪 Cookie 配置中心
SITE_COOKIES = {
    # "weibo.com": "...",
}
