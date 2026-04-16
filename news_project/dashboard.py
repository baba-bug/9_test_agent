import os
import sys
from datetime import datetime

import streamlit as st


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from news_project.scraper.observability import setup_logging


setup_logging()

from news_project.dashboard_chat import render_chat_page
from news_project.dashboard_components import render_article_browser
from news_project.dashboard_data import archive_all_latest, data_path, load_data, split_favorites
from news_project.dashboard_status import render_status_page
from news_project.scraper.storage import Storage


st.set_page_config(layout="wide", page_title="AI News Dashboard")

st.markdown(
    """
    <style>
        .stDataFrame { width: 100%; }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_latest_page(storage: Storage) -> None:
    title_col, action_col = st.columns([8, 2])
    with title_col:
        st.header("Latest Updates")
    with action_col:
        if st.button("Archive all", type="primary"):
            counts = archive_all_latest()
            st.toast(f"Archived {counts['news']} news item(s) and {counts['papers']} paper item(s).")
            st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("News")
        render_article_browser(
            load_data(data_path("latest_news.json")),
            "latest_news",
            storage,
            data_path("latest_news.json"),
            archive_target=data_path("history_news.json"),
        )

    with col2:
        st.subheader("Papers")
        render_article_browser(
            load_data(data_path("latest_arxiv.json")),
            "latest_arxiv",
            storage,
            data_path("latest_arxiv.json"),
            archive_target=data_path("history_arxiv.json"),
        )


def render_history_page(storage: Storage) -> None:
    st.header("Full History")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("News History")
        render_article_browser(load_data(data_path("history_news.json")), "history_news", storage, data_path("history_news.json"))

    with col2:
        st.subheader("Paper History")
        render_article_browser(load_data(data_path("history_arxiv.json")), "history_arxiv", storage, data_path("history_arxiv.json"))


def render_favorites_page(storage: Storage) -> None:
    st.header("My Favorites")
    favorites = load_data(data_path("favorites.json"))
    if not favorites:
        st.info("No favorites yet.")
        return

    fav_news, fav_papers = split_favorites(favorites)
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Favorite News")
        render_article_browser(fav_news, "fav_news", storage, data_path("favorites.json"), allow_delete=True)

    with col2:
        st.subheader("Favorite Papers")
        render_article_browser(fav_papers, "fav_papers", storage, data_path("favorites.json"), allow_delete=True)


def main() -> None:
    st.title("AI News & Paper Monitor")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    storage = Storage()
    page = st.sidebar.radio(
        "Section",
        ["Latest", "History", "Favorites", "Hub Chat", "Status"],
        index=0,
    )

    if page == "Latest":
        render_latest_page(storage)
    elif page == "History":
        render_history_page(storage)
    elif page == "Favorites":
        render_favorites_page(storage)
    elif page == "Hub Chat":
        render_chat_page()
    elif page == "Status":
        render_status_page(storage)


if __name__ == "__main__":
    main()
