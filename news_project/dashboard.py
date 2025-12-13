import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from news_project.scraper.storage import Storage

st.set_page_config(layout="wide", page_title="AI News Dashboard", page_icon="🌍")

# --- Custom CSS for wider columns ---
st.markdown("""
<style>
    .stDataFrame { width: 100%; }
</style>
""", unsafe_allow_html=True)

def load_data(file_path):
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        # st.error(f"Error loading {file_path}: {e}")
        return []

def save_data(file_path, data):
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Error saving {file_path}: {e}")

def render_table(articles, key_prefix, storage, file_path=None):
    if not articles:
        st.info("No data available.")
        return

    # 1. Sorting Controls (Multi-column)
    cols_available = ["score", "impact_score", "ai_score", "date"]
    
    c1, c2, c3 = st.columns([1, 1, 4])
    with c1:
        sort_by_1 = st.selectbox(f"Sort By ({key_prefix})", cols_available, index=0, key=f"sort1_{key_prefix}")
    with c2:
        sort_by_2 = st.selectbox(f"Then By ({key_prefix})", ["None"] + cols_available, index=0, key=f"sort2_{key_prefix}")
    
    # Process Data
    df = pd.DataFrame(articles)
    
    # Ensure columns exist
    required_cols = ['score', 'ai_score', 'impact_score', 'title', 'date', 'venue', 'summary', 'link', 'score_reason', 'comment']
    for c in required_cols:
        if c not in df.columns:
            df[c] = "" # Default empty string
            if c in ['score', 'ai_score', 'impact_score']:
                 df[c] = 0

    # Sort Data
    sort_cols = [sort_by_1]
    if sort_by_2 != "None":
        sort_cols.append(sort_by_2)
        
    df = df.sort_values(by=sort_cols, ascending=False)

    # Insert Select Column
    df.insert(0, "select", False)

    # Column Config
    column_config = {
        "select": st.column_config.CheckboxColumn("📌", width="small"),
        "score": st.column_config.NumberColumn("Total", format="%d ⭐️", width="small"),
        "ai_score": st.column_config.NumberColumn("AI", format="%d", width="small"),
        "impact_score": st.column_config.NumberColumn("Imp", format="%d", width="small"),
        
        # User request: "summary and score_reason dominant (wider)"
        "summary": st.column_config.TextColumn("Summary", width="large"),
        "score_reason": st.column_config.TextColumn("Reason", width="large"),
        "comment": st.column_config.TextColumn("💬 Comment (Editable)", width="medium"),
        
        "title": st.column_config.TextColumn("Title", width="medium"),
        "date": st.column_config.TextColumn("Date", width="small"),
        "venue": st.column_config.TextColumn("Source", width="small"),
        "link": st.column_config.LinkColumn("Link", width="small"),
    }

    # Display Order
    display_cols = ["select", "score", "ai_score", "impact_score", "title", "summary", "score_reason", "comment", "date", "venue", "link"]

    # --- DATA EDITOR ---
    edited_df = st.data_editor(
        df[display_cols],
        column_config=column_config,
        hide_index=True,
        use_container_width=True,
        key=f"editor_{key_prefix}",
        disabled=["score", "ai_score", "impact_score", "title", "date", "venue", "summary", "link", "score_reason"] # 'select' and 'comment' are editable
    )

    # --- ACTIONS ---
    # 1. Save Favorites
    selected_rows = edited_df[edited_df["select"] == True]
    if not selected_rows.empty:
        if st.button(f"⭐ Save {len(selected_rows)} to Favorites", key=f"btn_fav_{key_prefix}"):
            count = 0
            for index, row in selected_rows.iterrows():
                article_data = row.to_dict()
                del article_data['select']
                storage.save_to_favorites(article_data)
                count += 1
            st.success(f"Saved {count} to Favorites!")

    # 2. Save Comments (If file_path provided e.g., favorites.json)
    # Detect changes in comments. Since 'edited_df' has the new state, we can save it back.
    # Note: syncing edits back to the list requires mapping by something unique (e.g. Link).
    if file_path:
        # Check if comments changed? 
        # Simpler: Just provide a "Save Changes" button or Auto-save?
        # Streamlit re-runs on edit. We can save immediately if we detect change, OR provide a button.
        # Button is safer to avoid excessive IO.
        if st.button("💾 Save Comments", key=f"btn_save_{key_prefix}"):
            # We need to update the ORIGINAL list with new comments from edited_df
            # Convert edited_df back to list of dicts
            
            # Map updated info keyed by link
            updated_map = {}
            for idx, row in edited_df.iterrows():
                link = row['link']
                if link:
                    updated_map[link] = row['comment']
            
            # Load fresh file (in case of race condition) or use 'articles'
            current_data = load_data(file_path)
            updated_count = 0
            
            for art in current_data:
                lnk = art.get('link')
                if lnk and lnk in updated_map:
                    if art.get('comment') != updated_map[lnk]:
                        art['comment'] = updated_map[lnk]
                        updated_count += 1
            
            if updated_count > 0:
                save_data(file_path, current_data)
                st.success(f"Updated {updated_count} comments in {os.path.basename(file_path)}!")
            else:
                st.info("No changes to save.")

def main():
    st.title("🌍 AI News & Paper Monitor")
    st.caption(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    storage = Storage()

    tab1, tab2, tab3 = st.tabs(["🔥 Latest Updates", "📜 History", "⭐ Favorites (Editable)"])

    with tab1:
        st.header("Latest Updates")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📰 News")
            news = load_data("latest_news.json")
            render_table(news, "latest_news", storage) # No file_path, so comments won't persist to 'latest' (transient)
        with col2:
            st.subheader("📜 Papers")
            papers = load_data("latest_arxiv.json")
            render_table(papers, "latest_arxiv", storage)

    with tab2:
        st.header("🗄️ Full History")
        filter_type = st.radio("Type", ["News", "Papers"], horizontal=True)
        if filter_type == "News":
            data = load_data("history_news.json") 
            render_table(data, "hist_news", storage, "history_news.json") # Allow comment-saving to history
        else:
            data = load_data("history_arxiv.json")
            render_table(data, "hist_arxiv", storage, "history_arxiv.json")

    with tab3:
        st.header("⭐ My Favorites")
        # Reload to capture regrade updates
        favs = load_data("favorites.json")
        if favs:
            # Pass file_path="favorites.json" to enable Comment Saving
            render_table(favs, "favs", storage, "favorites.json")
        else:
            st.info("No favorites yet.")

if __name__ == "__main__":
    main()
