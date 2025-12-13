import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime
import sys

# Add project root to path so we can import scraper modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from news_project.scraper.storage import Storage

# Configure Page
st.set_page_config(layout="wide", page_title="AI News Dashboard", page_icon="🌍")

def load_data(file_path):
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading {file_path}: {e}")
        return []

def render_table(articles, key_prefix, storage):
    if not articles:
        st.info("No data available.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(articles)
    
    # Ensure columns exist
    cols = ['score', 'title', 'date', 'venue', 'summary', 'link']
    for c in cols:
        if c not in df.columns:
            df[c] = ""
            
    # Add 'Select' column for checkbox (initially False)
    df.insert(0, "select", False)

    # Column Configuration
    column_config = {
        "select": st.column_config.CheckboxColumn("📌", width="small"),
        "score": st.column_config.NumberColumn("Score", format="%d ⭐️", width="small"),
        "title": st.column_config.TextColumn("Title", width="medium"),
        "date": st.column_config.TextColumn("Date", width="small"),
        "venue": st.column_config.TextColumn("Source", width="small"),
        "summary": st.column_config.TextColumn("Summary", width="large"),
        "link": st.column_config.LinkColumn("Link", width="small"),
    }

    # Data Editor (Editable Table)
    edited_df = st.data_editor(
        df[["select", "score", "title", "date", "venue", "summary", "link"]],
        column_config=column_config,
        hide_index=True,
        use_container_width=True, # Note: using deprecated one for now as 'width="stretch"' is experimental/newer
        # Actually better to use use_container_width=True for compatibility if user environment is older
        # But wait, previous error said "replace with width". Let's use `width='stretch'`?
        # Re-reading error: "For use_container_width=True, use width='stretch'". It implies older Streamlit might NOT support it?
        # Let's stick to use_container_width=True if it works, or just ignore warning.
        # Actually, let's try `use_container_width=True` but suppress warning or just use it.
        # Wait, the tool output SAID "Please replace...". I will use the new way for safety if version is high.
        # If I get an error, I revert.
        # Let's try key-based state management
        key=f"editor_{key_prefix}",
        disabled=["score", "title", "date", "venue", "summary", "link"] # Only 'select' is editable
    )

    # Save Button
    # Only show if items are selected
    selected_rows = edited_df[edited_df["select"] == True]
    
    if not selected_rows.empty:
        if st.button(f"⭐ Save {len(selected_rows)} to Favorites", key=f"btn_{key_prefix}"):
            count = 0
            for index, row in selected_rows.iterrows():
                # Reconstruct article dict (simpler way: find original via link or just use row data)
                # Using row data is safer for display consistency
                article_data = row.to_dict()
                del article_data['select'] # Remove select field
                
                # Check link to prevent duplicates (Storage handles it, but we display Toast)
                storage.save_to_favorites(article_data)
                count += 1
            
            st.success(f"Saved {count} articles to Favorites!")
            # Optional: Clear selection logic requires session state wizardry, 
            # for now manual uncheck is fine.

def render_favorites(articles):
    if not articles:
        st.info("No favorites yet.")
        return
    
    df = pd.DataFrame(articles)
    st.dataframe(
        df,
        column_config={
            "link": st.column_config.LinkColumn("Link"),
            "score": st.column_config.NumberColumn("Score", format="%d ⭐️"),
        },
        hide_index=True,
        use_container_width=True
    )

def main():
    st.title("🌍 AI News & Paper Monitor")
    st.caption(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # Initialize Storage for saving favorites
    storage = Storage() 

    # Tabs
    tab1, tab2, tab3 = st.tabs(["🔥 Latest Updates", "📜 History", "⭐ Favorites"])

    with tab1:
        st.header("Latest Updates")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📰 News")
            news = load_data("latest_news.json")
            st.metric("New Articles", len(news))
            render_table(news, "latest_news", storage)
            
        with col2:
            st.subheader("📜 Papers (Arxiv)")
            papers = load_data("latest_arxiv.json")
            st.metric("New Papers", len(papers))
            render_table(papers, "latest_arxiv", storage)

    with tab2:
        st.header("🗄️ Full History")
        filter_type = st.radio("Select Type", ["News", "Papers (Arxiv)"], horizontal=True)
        
        if filter_type == "News":
            data = load_data("history_news.json")
            key = "hist_news"
        else:
            data = load_data("history_arxiv.json")
            key = "hist_arxiv"
            
        st.write(f"Total Records: {len(data)}")
        render_table(data, key, storage)

    with tab3:
        st.header("⭐ My Favorites")
        # Reload favorites every time to reflect changes
        favs = storage.load_favorites()
        if favs:
             render_favorites(favs)
        else:
            st.info("No favorites yet. Select articles in other tabs and click 'Save to Favorites'!")

if __name__ == "__main__":
    main()
