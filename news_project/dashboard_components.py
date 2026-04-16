import math
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from news_project.dashboard_data import archive_links, delete_by_links, update_comments


NUMERIC_COLUMNS = ["score", "personal_score", "impact_score", "ai_score"]
REQUIRED_COLUMNS = [
    "score",
    "ai_score",
    "impact_score",
    "personal_score",
    "title",
    "date",
    "venue",
    "summary",
    "link",
    "score_reason",
    "comment",
    "tags",
]


def _tags_as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value:
        return [value]
    return []


def _prepare_dataframe(articles: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(articles)
    for column in REQUIRED_COLUMNS:
        if column not in df.columns:
            df[column] = [[] for _ in range(len(df))] if column == "tags" else ""

    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0).astype(int)

    df["comment"] = df["comment"].fillna("").astype(str)
    df["tags"] = df["tags"].apply(_tags_as_list)
    return df


def _all_tags(df: pd.DataFrame) -> List[str]:
    tags = set()
    for value in df["tags"]:
        tags.update(_tags_as_list(value))
    return sorted(tags)


def _filter_dataframe(df: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    with st.expander("Filter", expanded=False):
        c1, c2, c3 = st.columns([2, 1, 2])
        with c1:
            query = st.text_input("Search title, summary, reason", key=f"search_{key_prefix}")
        with c2:
            min_score = st.number_input("Minimum score", min_value=0, value=0, step=10, key=f"min_score_{key_prefix}")
        with c3:
            selected_tags = st.multiselect("Tags", _all_tags(df), key=f"tags_{key_prefix}")

    filtered = df.copy()
    if query:
        query_lower = query.lower()
        search_text = (
            filtered["title"].fillna("").astype(str)
            + " "
            + filtered["summary"].fillna("").astype(str)
            + " "
            + filtered["score_reason"].fillna("").astype(str)
        ).str.lower()
        filtered = filtered[search_text.str.contains(query_lower, regex=False)]

    if min_score:
        filtered = filtered[filtered["score"] >= min_score]

    if selected_tags:
        selected = set(selected_tags)
        filtered = filtered[filtered["tags"].apply(lambda value: bool(selected.intersection(_tags_as_list(value))))]

    return filtered


def _render_cards(df: pd.DataFrame, key_prefix: str, storage, file_path: str = None, allow_delete: bool = False, archive_target: str = None) -> None:
    for index, row in df.iterrows():
        with st.container():
            action_col, content_col = st.columns([1.2, 8.8])
            with action_col:
                if allow_delete and file_path:
                    if st.button("Delete", key=f"card_delete_{key_prefix}_{index}"):
                        deleted = delete_by_links(file_path, [row["link"]])
                        st.toast(f"Deleted {deleted} item(s).")
                        st.rerun()
                else:
                    if st.button("Favorite", key=f"card_fav_{key_prefix}_{index}"):
                        storage.save_to_favorites(row.to_dict())
                        st.toast("Saved to favorites.")
                    if archive_target and file_path and st.button("Archive", key=f"card_archive_{key_prefix}_{index}"):
                        archived = archive_links(file_path, archive_target, [row["link"]])
                        st.toast(f"Archived {archived} item(s).")
                        st.rerun()

            with content_col:
                st.markdown(f"#### [{row['title']}]({row['link']})")
                st.caption(
                    f"{row['date']} | {row['venue']} | Total: {row['score']} "
                    f"(Personal: {row['personal_score']}, AI: {row['ai_score']}, Impact: {row['impact_score']})"
                )
                tags = " ".join(f"`{tag}`" for tag in _tags_as_list(row["tags"])[:6])
                if tags:
                    st.markdown(tags)
                st.markdown(f"**Summary:** {row['summary']}")
                st.markdown(f"**Reason:** {row['score_reason']}")

                if file_path:
                    current_comment = row.get("comment", "")
                    new_comment = st.text_input(
                        "Comment",
                        value=current_comment,
                        key=f"card_comment_{key_prefix}_{index}",
                        label_visibility="collapsed",
                        placeholder="Add a comment...",
                    )
                    if new_comment != current_comment:
                        update_comments(file_path, {row["link"]: new_comment})
                        st.toast("Comment saved.")

            st.divider()


def render_article_browser(
    articles: List[Dict[str, Any]],
    key_prefix: str,
    storage,
    file_path: str = None,
    allow_delete: bool = False,
    archive_target: str = None,
) -> None:
    if not articles:
        st.info("No data available.")
        return

    df = _prepare_dataframe(articles)
    filtered = _filter_dataframe(df, key_prefix)

    if filtered.empty:
        st.info("No items match the current filters.")
        return

    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    sortable_columns = ["score", "personal_score", "impact_score", "ai_score", "date"]
    with c1:
        sort_by = st.selectbox("Sort by", sortable_columns, index=0, key=f"sort_{key_prefix}")
    with c2:
        view_mode = st.radio("View", ["Table", "Cards"], horizontal=True, key=f"view_{key_prefix}")
    with c3:
        page_size = st.selectbox("Rows", [25, 50, 100, 200], index=0, key=f"page_size_{key_prefix}")
    with c4:
        total_pages = max(1, math.ceil(len(filtered) / page_size))
        page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, key=f"page_{key_prefix}")

    filtered = filtered.sort_values(by=sort_by, ascending=False)
    start = (page - 1) * page_size
    end = start + page_size
    page_df = filtered.iloc[start:end].copy()

    st.caption(f"Showing {start + 1}-{min(end, len(filtered))} of {len(filtered)} filtered items.")

    if view_mode == "Cards":
        _render_cards(page_df, key_prefix, storage, file_path=file_path, allow_delete=allow_delete, archive_target=archive_target)
        return

    page_df.insert(0, "select", False)
    display_cols = [
        "select",
        "score",
        "personal_score",
        "ai_score",
        "impact_score",
        "title",
        "summary",
        "score_reason",
        "comment",
        "date",
        "venue",
        "link",
    ]

    edited_df = st.data_editor(
        page_df[display_cols],
        column_config={
            "select": st.column_config.CheckboxColumn("Select", width="small"),
            "score": st.column_config.NumberColumn("Total", format="%d", width="small"),
            "personal_score": st.column_config.NumberColumn("Pers", format="%d", width="small"),
            "ai_score": st.column_config.NumberColumn("AI", format="%d", width="small"),
            "impact_score": st.column_config.NumberColumn("Imp", format="%d", width="small"),
            "summary": st.column_config.TextColumn("Summary", width="large"),
            "score_reason": st.column_config.TextColumn("Reason", width="large"),
            "comment": st.column_config.TextColumn("Comment", width="small"),
            "title": st.column_config.TextColumn("Title", width="large"),
            "date": st.column_config.TextColumn("Date", width="small"),
            "venue": st.column_config.TextColumn("Source", width="small"),
            "link": st.column_config.LinkColumn("Link", width="small"),
        },
        hide_index=True,
        use_container_width=True,
        key=f"editor_{key_prefix}",
        disabled=["score", "personal_score", "ai_score", "impact_score", "title", "date", "venue", "summary", "link", "score_reason"],
    )

    selected_rows = edited_df[edited_df["select"] == True]
    selected_links = selected_rows["link"].dropna().tolist()

    action_cols = st.columns(4)
    with action_cols[0]:
        if selected_links and st.button(f"Favorite {len(selected_links)}", key=f"fav_{key_prefix}"):
            for _, row in selected_rows.iterrows():
                article_data = row.to_dict()
                article_data.pop("select", None)
                storage.save_to_favorites(article_data)
            st.toast(f"Saved {len(selected_links)} item(s).")

    with action_cols[1]:
        if archive_target and file_path and selected_links and st.button(f"Archive {len(selected_links)}", key=f"archive_{key_prefix}"):
            archived = archive_links(file_path, archive_target, selected_links)
            st.toast(f"Archived {archived} item(s).")
            st.rerun()

    with action_cols[2]:
        if file_path and st.button("Save comments", key=f"comments_{key_prefix}"):
            comments = {row["link"]: row.get("comment", "") for _, row in edited_df.iterrows() if row.get("link")}
            updated = update_comments(file_path, comments)
            st.toast(f"Updated {updated} comment(s).")

    with action_cols[3]:
        if allow_delete and file_path and selected_links and st.button(f"Delete {len(selected_links)}", key=f"delete_{key_prefix}", type="primary"):
            deleted = delete_by_links(file_path, selected_links)
            st.toast(f"Deleted {deleted} item(s).")
            st.rerun()

    if selected_links:
        with st.expander("Reading mode", expanded=False):
            for _, row in selected_rows.iterrows():
                st.markdown(f"### [{row['title']}]({row['link']})")
                st.caption(f"{row['date']} | {row['venue']} | Score: {row['score']}")
                st.markdown(f"**Summary**\n\n{row['summary']}")
                st.markdown(f"**Reason**\n\n{row['score_reason']}")
                if row.get("comment"):
                    st.markdown(f"**Comment:** {row['comment']}")
                st.divider()
