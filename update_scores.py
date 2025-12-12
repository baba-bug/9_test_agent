import json
import os
import sys

# Ensure we can import from the package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from news_project.scraper.rankings import get_venue_score
except ImportError:
    # Fallback if package structure varies
    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "news_project"))
    from scraper.rankings import get_venue_score

def calculate_score(article):
    # 1. Base Tech Keywords
    keywords = {
        "AI": 5, "ARTIFICIAL INTELLIGENCE": 5, "LLM": 4, "TRANSFORMER": 3,
        "XR": 5, "AR": 5, "VR": 5, "MR": 5, "SPATIAL": 4, "VISION PRO": 4,
        "HCI": 5, "INTERFACE": 3, "INTERACTION": 3, "HUMAN": 2, "UX": 2,
        "AGENT": 6, "MULTI-AGENT": 6, "AUTONOMOUS": 4,
        "GENERATION": 5, "GENERATIVE": 5, "DIFFUSION": 4, "GAN": 3,
        "VIDEO": 2, "Creative": 2
    }
    
    # 2. High Impact New Tech (News Priority)
    new_tech_keywords = {
        "SAM3": 15, "GPT-5": 15, "GPT5": 15, "GEMINI 3": 15, 
        "OPENAI O1": 15, "CLAUDE 3.5": 10, "LLAMA 4": 15, 
        "MISTRAL LARGE": 10, "SORA": 12,
        "RELEASED": 8, "AVAILABLE NOW": 8, "OPEN SOURCE": 8, "GITHUB": 8, "CODE": 6
    }
    
    text = (article.get('title', '') + " " + article.get('summary', '') + " " + article.get('venue', '')).upper()
    
    score = 0
    details = []
    
    # A. Keyword Score
    for kw, weight in keywords.items():
        if kw in text:
            score += weight
            details.append(f"{kw}(+{weight})")
    
    # B. New Tech Score (Boost)
    for kw, weight in new_tech_keywords.items():
        if kw in text:
            score += weight
            details.append(f"🔥{kw}(+{weight})")
            
    # C. Venue/Journal Score
    venue_name = article.get('venue', '')
    if venue_name:
        v_score = get_venue_score(venue_name)
        if v_score > 0:
            score += v_score
            details.append(f"🏛VENUE(+{v_score})")
            
    return score, ", ".join(details) if details else "Base"

file_path = "latest_new_articles.json"

if os.path.exists(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print(f"Loaded {len(data)} articles.")
    
    for art in data:
        s, d = calculate_score(art)
        art['score'] = s
        art['score_reason'] = d
        
    # Sort
    data.sort(key=lambda x: x['score'], reverse=True)
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Updated {file_path} with ADVANCED scores and sorting.")
else:
    print(f"{file_path} not found.")
