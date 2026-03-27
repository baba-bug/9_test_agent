import os

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



# API Key 配置
# 优先从环境变量获取，如果没有则使用默认值（开发测试用）
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API", "abc")

# If running locally, load the API key from the local file
local_key_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "deepseek_api_key.txt"))
if os.path.exists(local_key_path):
    try:
        with open(local_key_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("DEEPSEEK_API_KEY="):
                    DEEPSEEK_API_KEY = line.split("=", 1)[1].strip()
                    break
    except Exception as e:
        print(f"Error reading local API key file: {e}")

DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# DEBUG: Check which key is loaded
if DEEPSEEK_API_KEY:
    print(f"🔑 Loaded API Key: {DEEPSEEK_API_KEY[:4]}... (Length: {len(DEEPSEEK_API_KEY)})")
else:
    print("❌ No API Key loaded!")

# 🍪 Cookie 配置中心
SITE_COOKIES = {
    # "weibo.com": "...",
}
