import json
import os
from datetime import datetime
from typing import List, Dict, Any
from news_project.scraper.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL

# RAG Configuration
MAX_CONTEXT_ITEMS = 200 # How many articles to stuff into context

class LibraryChat:
    def __init__(self):
        self.articles = []
        self.last_load_time = None
        
    def load_library(self):
        """Loads all JSON data into memory."""
        self.articles = []
        files = ["favorites.json"]
        seen_links = set()
        
        for fname in files:
            if os.path.exists(fname):
                try:
                    with open(fname, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for art in data:
                            if art.get('link') and art['link'] not in seen_links:
                                self.articles.append(art)
                                seen_links.add(art['link'])
                except Exception as e:
                    print(f"Error loading {fname}: {e}")
                    
        self.last_load_time = datetime.now()
        print(f"📚 RAG Library Loaded: {len(self.articles)} unique docs")

    def retrieve_relevant(self, query: str) -> List[Dict]:
        """
        Simple retrieval strategy:
        1. Keyword match (High priority)
        2. Recent (Recency bias)
        For small datasets, we can return the top N matches or just recent ones if no match.
        """
        if not self.articles:
            self.load_library()
            
        query_terms = query.lower().split()
        
        scored_docs = []
        for art in self.articles:
            score = 0
            # Search text fields
            text = (art.get('title', '') + " " + art.get('summary', '') + " " + " ".join(art.get('tags', [])) + " " + art.get('comment', '')).lower()
            
            match_count = sum(1 for term in query_terms if term in text)
            if match_count > 0:
                score += match_count * 10
            
            # Boost by Personal Score
            score += int(art.get('personal_score', 0)) * 0.1
            
            if score > 0:
                scored_docs.append((score, art))
                
        # Sort by score desc, then date desc
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        
        # If no keywords matched, maybe return favorites? Or just empty?
        # Let's return top scored, or if empty, return top favorites.
        if not scored_docs:
             # Fallback: Top Favorites
             favorites = [a for a in self.articles if a.get('personal_score', 0) > 50]
             return favorites[:MAX_CONTEXT_ITEMS]
             
        return [item[1] for item in scored_docs[:MAX_CONTEXT_ITEMS]]

    async def ask_deepseek(self, query: str, context_docs: List[Dict]):
        from openai import OpenAI
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        
        # Prepare Context String
        context_str = ""
        for i, doc in enumerate(context_docs, 1):
            tags = ", ".join(doc.get('tags', []))
            comment = f"User Comment: {doc['comment']}" if doc.get('comment') else ""
            context_str += f"[{i}] Title: {doc['title']}\n    Date: {doc.get('date')} | Tags: {tags}\n    Summary: {doc['summary']}\n    {comment}\n    Link: {doc['link']}\n\n"
            
        system_prompt = f"""You are a personal Knowledge Assistant.
You have access to a personal library of news and papers (Context).
Answer the user's question using ONLY the information from the Context.
If the answer is not in the context, say "I couldn't find that in your library."
Cite sources using [N] notation.
Context:
{context_str[:30000]} # Truncate if too huge
"""

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                stream=True
            )
            return response
        except Exception as e:
            return f"Error: {e}"
