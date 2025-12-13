
import asyncio
import json
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# from news_project.scraper.core import _query_ai
from news_project.scraper.config import DEEPSEEK_API_KEY
from news_project.scraper.rankings import get_venue_score

from news_project.scraper.personalization import extract_user_interests

# Helper to reconstruct prompt for single article
async def regrade_article(article, user_interests=[]):
    # Determine mode based on venue or link
    mode = "paper" if "arxiv" in article.get('venue', '').lower() or "paper" in article.get('type', '') else "news"
    
    # We construct a synthetic "content" from title + summary to feed the AI
    # This is much faster than re-fetching the web page
    content_snippet = f"Title: {article.get('title')}\nSummary: {article.get('summary')}\nLink: {article.get('link')}"
    
    today_str = article.get('date', '2025-12-13')

    # Build Personal Context
    personal_context = ""
    if user_interests and len(user_interests) > 0:
        interest_str = ", ".join(user_interests[:20])
        personal_context = f"\n    \"personal_score\": (0-100), // Based on user keywords: {interest_str}"
    else:
        personal_context = "\n    \"personal_score\": 0, // No user data"

    # Updated Prompt (Copied/Adapted from core.py latest version)
    if mode == "news":
        prompt = f"""
You are an AI News Editor for a Tech Hunter.
Current Date: {today_str}

Analyze the following article summary and extract key details in JSON format.
Content:
{content_snippet}

Output JSON format:
{{
    "ai_score": (0-100), // Relevance to: AI, Agent, HCI, XR/Spatial, Generation, Diffusion, 3D, VR, AR, MR, Spatial Computing, Brain, Recognition, Cognitive, Health, Sense, Control, Emotion, Affective, Eye Tracking, Gesture, Face, Disability.
    "impact_score": (0-50), // Industry Impact (Major Product=50, Update=10).{personal_context}
    "is_tech_release": (bool), // Is it an immediate tech release (code/model/demo)?
    "code_url": (str/null), // GitHub/HF link if present.
    "score_reason": (str), // Why this score?
    "tags": (List[str]) // 3-5 tech tags (e.g. "LLM", "Agent", "Hardware")
}}
Only return JSON.
"""
    else: # Paper
        prompt = f"""
You are an AI Researcher.
Current Date: {today_str}

Analyze the following research paper summary and extract key details in JSON format.
Content:
{content_snippet}

Output JSON format:
{{
    "ai_score": (0-100), // Relevance to: AI, Agent, HCI, XR/Spatial, Generation, Diffusion, 3D, VR, AR, MR, Spatial Computing, Brain, Recognition, Cognitive, Health, Sense, Control, Emotion, Affective, Eye Tracking, Gesture, Face.{personal_context}
    "impact_score": (0-50), // Academic Impact (CCF A/Top Journal=50, Arxiv=5).
    "is_tech_release": (bool), // Code/Weights released?
    "code_url": (str/null), // GitHub/HF link.
    "score_reason": (str), // Reason for score.
    "tags": (List[str]) // 3-5 tech tags (e.g. "Agent", "Vision", "RL")
}}
Only return JSON.
"""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            stream=False,
            response_format={"type": "json_object"}
        )
        result = response.choices[0].message.content
        data = json.loads(result)
        
        # Merge updates
        article['ai_score'] = data.get('ai_score', 0)
        article['personal_score'] = data.get('personal_score', 0)
        
        # Recalculate impact boost logic locally
        venue_score = get_venue_score(article.get('venue', ''))
        ai_impact = data.get('impact_score', 0)
        # Apply boost if Python lookup is higher
        article['impact_score'] = max(int(ai_impact), venue_score)
        
        article['is_tech_release'] = data.get('is_tech_release', False)
        article['score_reason'] = data.get('score_reason', '')
        article['tags'] = data.get('tags', []) # Extract tags
        
        if data.get('code_url'):
             article['code_url'] = data['code_url']
             
        # Recalculate Final Score
        tech_boost = 200 if (article['is_tech_release'] and article.get('code_url')) else 0
        
        article['score'] = article['ai_score'] + article['impact_score'] + tech_boost + article['personal_score']
        
        return article
        
    except Exception as e:
        print(f"Error regrading {article.get('title')}: {e}")
        return article

async def main():
    files = ["favorites.json", "latest_news.json", "latest_arxiv.json"]
    
    # Extract Interests ONCE
    interests = extract_user_interests("favorites.json")
    print(f"👤 Extracted User Interests ({len(interests)}): {interests[:10]}...")
    
    print("🔄 Regrading favorites based on new keywords...")
    
    path = "favorites.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        new_data = []
        for art in data:
            print(f"   Score: {art.get('title')[:30]}...")
            updated = await regrade_article(art, interests) # Pass interests
            new_data.append(updated)
            
        # Save back
        with open(path, "w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)
        print("✅ Favorites updated.")
        
    print("Optimization: Skipping regrade of latest/history to save tokens/time for now, unless requested.")
    
if __name__ == "__main__":
    asyncio.run(main())
