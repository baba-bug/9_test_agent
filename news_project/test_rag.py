import asyncio
from news_project.rag_core import LibraryChat

async def test():
    print("Testing RAG Library...")
    chat = LibraryChat()
    chat.load_library()
    
    query = "3D Gaussian"
    print(f"Searching for: {query}")
    docs = chat.retrieve_relevant(query)
    
    print(f"Found {len(docs)} docs.")
    for d in docs[:3]:
        print(f"- [{d.get('score', 0)}] {d['title']} (Tags: {d.get('tags')})")
        
    if docs:
        print("\nTesting DeepSeek Call (Mock or Real)...")
        # Just checking if function exists and runs without crashing
        # We won't expend tokens here unless necessary.
        print("DeepSeek call skipped to save tokens, but retrieval works.")

if __name__ == "__main__":
    asyncio.run(test())
