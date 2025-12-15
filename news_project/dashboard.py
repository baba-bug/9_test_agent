import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime
import asyncio
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

def render_table(articles, key_prefix, storage, file_path=None, allow_delete=False, archive_target=None):
    if not articles:
        st.info("No data available.")
        return

    # 1. Sorting Controls (Multi-column) & View Toggle
    cols_available = ["score", "personal_score", "impact_score", "ai_score", "date"]
    
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
    required_cols = ['score', 'ai_score', 'impact_score', 'personal_score', 'title', 'date', 'venue', 'summary', 'link', 'score_reason', 'comment', 'tags']
    for c in required_cols:
        if c not in df.columns:
            if c == 'tags':
                df[c] = pd.Series([[]] * len(df)) # Initialize as empty lists
            else:
                df[c] = "" # Default empty string
                if c in ['score', 'ai_score', 'impact_score', 'personal_score']:
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
            "personal_score": st.column_config.NumberColumn("Pers", format="%d ❤️", width="small"),
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
        display_cols = ["select", "score", "personal_score", "ai_score", "impact_score", "title", "summary", "score_reason", "comment", "date", "venue", "link"]

        # --- DATA EDITOR ---
        edited_df = st.data_editor(
            df[display_cols],
            column_config=column_config,
            hide_index=True,
            use_container_width=True,
            key=f"editor_{key_prefix}",
            disabled=["score", "personal_score", "ai_score", "impact_score", "title", "date", "venue", "summary", "link", "score_reason"] # 'select' and 'comment' are editable
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
                # Layout: Action Controls | Content
                col_btn, col_content = st.columns([1.2, 8.8]) # Widen generic action column
                
                with col_btn:
                    # Case 1: Favorites Mode (Delete)
                    if allow_delete and file_path:
                        if st.button("🗑️", key=f"del_{key_prefix}_{index}", help="Remove from Favorites"):
                            # Delete logic
                            current_data = load_data(file_path)
                            new_data = [d for d in current_data if d.get('link') != row['link']]
                            save_data(file_path, new_data)
                            st.toast(f"Removed: {row['title'][:20]}...")
                            st.rerun()
                    
                    # Case 2: Latest Mode (Save + Archive)
                    else:
                        # 2A: Favorite Star
                        if st.button("⭐", key=f"fav_{key_prefix}_{index}", help="Save to Favorites"):
                            article_data = row.to_dict()
                            if 'select' in article_data: del article_data['select']
                            storage.save_to_favorites(article_data)
                            st.toast(f"Saved: {row['title'][:20]}...")
                            
                        # 2B: Archive Checkmark (If archive_target provided)
                        if archive_target and file_path:
                            if st.button("✅", key=f"arc_{key_prefix}_{index}", help="Mark as Read (Move to History)"):
                                # 1. Add to History
                                hist_data = load_data(archive_target)
                                hist_links = {d['link'] for d in hist_data}
                                article_data = row.to_dict()
                                if 'select' in article_data: del article_data['select']
                                
                                if article_data['link'] not in hist_links:
                                    hist_data.insert(0, article_data)
                                    save_data(archive_target, hist_data)
                                
                                # 2. Remove from Current (Latest)
                                cur_data = load_data(file_path)
                                new_cur_data = [d for d in cur_data if d.get('link') != row['link']]
                                save_data(file_path, new_cur_data)
                                
                                st.toast("Archived!")
                                st.rerun()
                
                with col_content:
                    st.markdown(f"#### [{row['title']}]({row['link']})")
                    st.caption(f"**{row['date']}** | {row['venue']} | Total: **{row['score']}** ⭐️ (Pers: **{row['personal_score']}** ❤️, AI: {row['ai_score']}, Imp: {row['impact_score']})")
                    
                    # Display Tags (if any)
                    if row['tags'] and isinstance(row['tags'], list):
                        # Simple badge style using colored text or code block style
                        tags_html = " ".join([f"`{t}`" for t in row['tags'][:5]])
                        st.markdown(f"🏷️ {tags_html}")

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

    tab1, tab2, tab3, tab4 = st.tabs(["🔥 Latest Updates", "📜 History", "⭐ Favorites (Editable)", "🤖 Hub Chat"])

    with tab1:
        c_title, c_btn = st.columns([8, 2])
        with c_title:
            st.header("Latest Updates")
        with c_btn:
             if st.button("📭 Archive All (Mark as Read)", type="primary"):
                 # Archive News
                 news_latest = load_data("latest_news.json")
                 if news_latest:
                     news_hist = load_data("history_news.json")
                     existing_links = {x['link'] for x in news_hist}
                     count = 0
                     for item in reversed(news_latest):
                         if item['link'] not in existing_links:
                             news_hist.insert(0, item)
                             count += 1
                     save_data("history_news.json", news_hist)
                     save_data("latest_news.json", []) # Clear latest
                     st.toast(f"Archived {count} news items.")
                 
                 # Archive Papers
                 paper_latest = load_data("latest_arxiv.json")
                 if paper_latest:
                     paper_hist = load_data("history_arxiv.json")
                     existing_links = {x['link'] for x in paper_hist}
                     count = 0
                     for item in reversed(paper_latest):
                         if item['link'] not in existing_links:
                             paper_hist.insert(0, item)
                             count += 1
                     save_data("history_arxiv.json", paper_hist)
                     save_data("latest_arxiv.json", []) # Clear latest
                     st.toast(f"Archived {count} papers.")
                 
                 st.rerun()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📰 News")
            news = load_data("latest_news.json")
            if news:
                render_table(news, "latest_news", storage, "latest_news.json", archive_target="history_news.json")
            else:
                st.info("All caught up!")

        with col2:
            st.subheader("📜 Papers")
            papers = load_data("latest_arxiv.json")
            if papers:
                render_table(papers, "latest_arxiv", storage, "latest_arxiv.json", archive_target="history_arxiv.json")
            else:
                st.info("All caught up!")
            
    with tab2:
        st.header("🗄️ Full History")
        col1, col2 = st.columns(2)
        
        with col1:
             st.subheader("📰 News History")
             data_news = load_data("history_news.json")
             render_table(data_news, "hist_news", storage, "history_news.json")
             
        with col2:
             st.subheader("📜 Paper History")
             data_arxiv = load_data("history_arxiv.json")
             render_table(data_arxiv, "hist_arxiv", storage, "history_arxiv.json")

    with tab3:
        st.header("⭐ My Favorites")
        # Reload to capture regrade updates
        favs = load_data("favorites.json")
        
        if favs:
            # Split by type (heuristic: arxiv link = paper)
            fav_papers = [f for f in favs if "arxiv.org" in f.get('link', '').lower()]
            fav_news = [f for f in favs if "arxiv.org" not in f.get('link', '').lower()]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📰 Favorite News")
                if fav_news:
                    render_table(fav_news, "fav_news", storage, "favorites.json", allow_delete=True)
                else:
                    st.info("No favorite news.")
                    
            with col2:
                st.subheader("📜 Favorite Papers")
                if fav_papers:
                    render_table(fav_papers, "fav_papers", storage, "favorites.json", allow_delete=True)
                else:
                    st.info("No favorite papers.")
        else:
            st.info("No favorites yet.")

    with tab4:
        st.header("💬 Chat with your Library")
        st.caption("Ask questions about your captured news, papers, and favorites.")
        
        # Initialize Chat Engine
        if "rag_chat" not in st.session_state:
            from news_project.rag_core import LibraryChat
            st.session_state.rag_chat = LibraryChat()
            st.session_state.rag_chat.load_library()
            
        if "messages" not in st.session_state:
            st.session_state.messages = [{"role": "assistant", "content": "Hello! I've indexed your library. Ask me anything about recent AI papers or news."}]

        # Display Chat History
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # Chat Input
        if prompt := st.chat_input("Ex: What are the latest 3D Gaussian Splatting papers?"):
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Generate Answer
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                
                # Retrieve Context
                with st.status("🔍 Searching Index...", expanded=False) as status:
                    docs = st.session_state.rag_chat.retrieve_relevant(prompt)
                    st.write(f"Found {len(docs)} relevant articles.")
                    for d in docs[:3]:
                        st.write(f"- {d['title']}")
                    status.update(label="✅ Search Complete", state="complete", expanded=False)
                
                # Stream Response
                try:
                    stream = asyncio.run(st.session_state.rag_chat.ask_deepseek(prompt, docs))
                    
                    # DeepSeek/OpenAI Stream handling
                    for chunk in stream:
                        if chunk.choices[0].delta.content:
                            full_response += chunk.choices[0].delta.content
                            message_placeholder.markdown(full_response + "▌")
                            
                    message_placeholder.markdown(full_response)
                except Exception as e:
                    st.error(f"Error generating response: {e}")
                    full_response = "Sorry, I encountered an error."
            
            # Save history
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            # Show References (Ephemeral for this turn, or we could append to history too? 
            # For now, just show immediately)
            with st.expander("📚 Referenced Sources", expanded=False):
                for i, d in enumerate(docs, 1):
                    # Check if cited? Simple check: if f"[{i}]" in full_response: ...
                    # Or just list all relevant ones (since context stuffing uses them all)
                    highlight = " **(Cited)**" if f"[{i}]" in full_response else ""
                    st.markdown(f"**[{i}]** [{d['title']}]({d['link']}){highlight}")
                    st.caption(f"{d.get('date', '')} | {d.get('venue', '')} | Tags: {d.get('tags', [])}")

if __name__ == "__main__":
    main()
