import json
import os
from collections import Counter
import re

def extract_user_interests(favorites_path="favorites.json", top_n=15):
    """
    Analyzes favorites.json to extract top keywords representing user interests.
    Returns a list of strings (keywords).
    """
    if not os.path.exists(favorites_path):
        return []

    try:
        with open(favorites_path, "r", encoding="utf-8") as f:
            favorites = json.load(f)
    except:
        return []

    text_content = ""
    for item in favorites:
        # Combine title and summary for analysis
        text_content += f" {item.get('title', '')} {item.get('summary', '')}"

    # Basic cleaning and tokenization
    # Remove special chars, lowercase
    text_content = re.sub(r'[^\w\s]', '', text_content).lower()
    words = text_content.split()

    # Simple stop words (expand as needed)
    stop_words = {
        "the", "a", "an", "in", "on", "at", "for", "to", "of", "and", "or", "with", "by",
        "is", "are", "was", "were", "this", "that", "it", "model", "using", "based", "new",
        "paper", "news", "study", "research", "proposed", "method", "results", "show",
        "from", "as", "be", "can", "we", "our", "which", "has", "have", "not", "but",
        "learning", "models", "data", "training", "approach", "system", "performance",
        "stateoftheart", "introduction", "work", "via", "introduction", "large", "language"
    }

    filtered_words = [w for w in words if w not in stop_words and len(w) > 2]
    
    # Count frequency
    counter = Counter(filtered_words)
    
    # Get top N common words
    top_keywords = [word for word, count in counter.most_common(top_n)]
    
    # Also manual check for specific high-value terms if they exist in text
    # (to ensure compound concepts like "generative ai" are captured if we did n-grams, 
    # but for now simple words work well for LLM context)
    
    return top_keywords
