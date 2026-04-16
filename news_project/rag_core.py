from datetime import datetime
from typing import Any, Dict, List

from news_project.scraper import sqlite_store as db
from news_project.scraper.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL


MAX_CONTEXT_ITEMS = 200


class LibraryChat:
    def __init__(self):
        self.articles = []
        self.last_load_time = None

    def load_library(self):
        """Loads the favorite library from SQLite into memory."""
        conn = db.connect()
        try:
            self.articles = db.load_articles(conn, favorites=True)
        finally:
            conn.close()

        self.last_load_time = datetime.now()
        print(f"RAG Library Loaded: {len(self.articles)} unique docs")

    def retrieve_relevant(self, query: str) -> List[Dict]:
        if not self.articles:
            self.load_library()

        query_terms = query.lower().split()

        scored_docs = []
        for article in self.articles:
            score = 0
            text = (
                article.get("title", "")
                + " "
                + article.get("summary", "")
                + " "
                + " ".join(article.get("tags", []))
                + " "
                + article.get("comment", "")
            ).lower()

            match_count = sum(1 for term in query_terms if term in text)
            if match_count > 0:
                score += match_count * 10

            score += int(article.get("personal_score", 0)) * 0.1

            if score > 0:
                scored_docs.append((score, article))

        scored_docs.sort(key=lambda x: x[0], reverse=True)

        if not scored_docs:
            favorites = [a for a in self.articles if a.get("personal_score", 0) > 50]
            return favorites[:MAX_CONTEXT_ITEMS]

        return [item[1] for item in scored_docs[:MAX_CONTEXT_ITEMS]]

    async def ask_deepseek(self, query: str, context_docs: List[Dict[str, Any]]):
        from openai import OpenAI

        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

        context_str = ""
        for i, doc in enumerate(context_docs, 1):
            tags = ", ".join(doc.get("tags", []))
            comment = f"User Comment: {doc['comment']}" if doc.get("comment") else ""
            context_str += (
                f"[{i}] Title: {doc['title']}\n"
                f"    Date: {doc.get('date')} | Tags: {tags}\n"
                f"    Summary: {doc['summary']}\n"
                f"    {comment}\n"
                f"    Link: {doc['link']}\n\n"
            )

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
                    {"role": "user", "content": query},
                ],
                stream=True,
            )
            return response
        except Exception as e:
            return f"Error: {e}"
