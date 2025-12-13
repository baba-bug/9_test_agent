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

def render_table(articles, key_prefix, storage, file_path=None, allow_delete=False):
    if not articles:
        st.info("No data available.")
        return

    # 1. Sorting Controls (Multi-column) & View Toggle
    cols_available = ["score", "impact_score", "ai_score", "date"]
    
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        sort_by_1 = st.selectbox(f"Sort By ({key_prefix})", cols_available, index=0, key=f"sort1_{key_prefix}")
    with c2:
        sort_by_2 = st.selectbox(f"Then By ({key_prefix})", ["None"] + cols_available, index=0, key=f"sort2_{key_prefix}")
    with c3:
        view_mode = st.radio("Display Mode", ["Table", "Card (Expanded)"], horizontal=True, key=f"view_{key_prefix}", index=0)
    
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

    # --- RENDER TABLE VIEW ---
    if view_mode == "Table":
        # Column Config
        column_config = {
            "select": st.column_config.CheckboxColumn("📌", width="small"),
            "score": st.column_config.NumberColumn("Total", format="%d ⭐️", width="small"),
            "ai_score": st.column_config.NumberColumn("AI", format="%d", width="small"),
            "impact_score": st.column_config.NumberColumn("Imp", format="%d", width="small"),
            
            # User request: "summary and score_reason dominant (wider)"
            "summary": st.column_config.TextColumn("Summary", width="large"),
            "score_reason": st.column_config.TextColumn("Reason", width="large"),
            "comment": st.column_config.TextColumn("💬 Comment (Editable)", width="small"),
            
            "title": st.column_config.TextColumn("Title", width="large"),
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
    
    # --- RENDER CARD VIEW ---
    else:
        st.info("ℹ️ Card View: All text is fully visible. Select items using the checkbox on the left.")
        
        # We need to track selection manually in list mode
        # Create a container for actions at the top?
        # Let's create a dictionary to hold the selection state
        selected_links = []
        
        # Iterate and render cards
        for index, row in df.iterrows():
            with st.container():
                # Layout: Checkbox | Content
                # NOTE: Nested columns limit. We are already inside [Tab] -> [Col].
                # If we use columns here, we are at level 3. Streamlit might allow it, but let's be safe and use [0.5, 9.5]
                col_check, col_content = st.columns([0.5, 9.5])
                
                with col_check:
                    # Unique key based on link + prefix
                    is_selected = st.checkbox("Select", key=f"chk_{key_prefix}_{index}", label_visibility="collapsed")
                    if is_selected:
                        selected_links.append(row['link'])
                
                with col_content:
                    st.markdown(f"#### [{row['title']}]({row['link']})")
                    st.caption(f"**{row['date']}** | {row['venue']} | Total: **{row['score']}** ⭐️ (AI: {row['ai_score']}, Imp: {row['impact_score']})")
                    
                    st.markdown(f"**📝 Summary:** {row['summary']}")
                    st.markdown(f"**🤖 Reason:** {row['score_reason']}")
                    
                    # Editable Comment (Auto-save on blur/enter)
                    current_comment = row['comment']
                    if not isinstance(current_comment, str) or current_comment.lower() == 'nan':
                        current_comment = ""
                        
                    # Use text_input for compact view (narrower)
                    new_comment = st.text_input("Comment", value=current_comment, 
                                               key=f"txt_{key_prefix}_{index}", 
                                               label_visibility="collapsed",
                                               placeholder="Add a comment...")
                    
                    if new_comment != current_comment and file_path:
                        # Save immediately
                        all_data = load_data(file_path)
                        updated = False
                        for item in all_data:
                            if item.get('link') == row['link']:
                                item['comment'] = new_comment
                                updated = True
                                break
                        if updated:
                            save_data(file_path, all_data)
                            st.toast(f"Saved comment for: {row['title'][:30]}...")
                            st.rerun() # Force reload to show updated state

                st.divider()

        # Create a boolean mask
        df['select'] = df['link'].isin(selected_links)
        edited_df = df 


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

    # 2. Save Comments (Legacy/Table Mode button)
    if file_path and view_mode == "Table":
        if st.button("💾 Save Comments", key=f"btn_save_{key_prefix}"):
             updated_map = {}
             for idx, row in edited_df.iterrows():
                 link = row['link']
                 if link:
                     updated_map[link] = row['comment']
             
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

    # 3. Delete from Favorites (If allow_delete=True)
    if allow_delete and file_path:
        selected_rows = edited_df[edited_df["select"] == True]
        if not selected_rows.empty:
            if st.button(f"🗑️ Delete {len(selected_rows)} from Favorites", key=f"btn_del_{key_prefix}", type="primary"):
                # Get links to delete
                links_to_delete = set(selected_rows['link'].tolist())
                
                # Filter original data
                current_data = load_data(file_path)
                new_data = [d for d in current_data if d.get('link') not in links_to_delete]
                
                if len(new_data) < len(current_data):
                    save_data(file_path, new_data)
                    st.success(f"Deleted {len(current_data) - len(new_data)} items!")
                    st.rerun()
                else:
                    st.warning("Could not match items to delete.")

    # 4. Reading Mode (Detail View for Selected Items)
    # Always allow reading mode if items are selected
    selected_rows_read = edited_df[edited_df["select"] == True]
    if not selected_rows_read.empty:
        st.divider()
        st.subheader("📖 Reading Mode (Deep Dive)")
        for idx, row in selected_rows_read.iterrows():
            with st.container():
                st.markdown(f"### [{row['title']}]({row['link']})")
                st.caption(f"📅 {row['date']} | 🏛️ {row['venue']} | ⭐️ {row['score']}")
                
                st.info(f"**📝 Summary**\n\n{row['summary']}")
                st.success(f"**🤖 AI Reason**\n\n{row['score_reason']}")
                
                if row['comment']:
                    st.warning(f"**💬 Your Comment:** {row['comment']}")
                
                st.markdown("---")

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
            render_table(news, "latest_news", storage, "latest_news.json") # Enable comments
        with col2:
            st.subheader("📜 Papers")
            papers = load_data("latest_arxiv.json")
            render_table(papers, "latest_arxiv", storage, "latest_arxiv.json")
            
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
            # Pass file_path="favorites.json" to enable Comment Saving and allow_delete=True
            render_table(favs, "favs", storage, "favorites.json", allow_delete=True)
        else:
            st.info("No favorites yet.")

if __name__ == "__main__":
    main()
