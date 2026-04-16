import concurrent.futures
from typing import Dict

import pandas as pd
import streamlit as st

from news_project.dashboard_data import source_health_rows
from news_project.scraper.config import TARGET_URLS


def _check_url(url: str) -> Dict[str, str]:
    try:
        from curl_cffi import requests as cffi_requests

        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        response = cffi_requests.get(url, headers=headers, impersonate="chrome120", timeout=10)
        if response.status_code < 400:
            return {"url": url, "status": "ok", "code": str(response.status_code), "detail": "OK"}
        return {"url": url, "status": "http_error", "code": str(response.status_code), "detail": response.reason}
    except Exception as e:
        text = str(e)
        if "timeout" in text.lower() or "timed out" in text.lower():
            return {"url": url, "status": "timeout", "code": "", "detail": "Request took longer than 10 seconds"}
        return {"url": url, "status": "error", "code": "", "detail": text.split(":", 1)[0]}


def render_status_page(storage) -> None:
    st.header("Source Health")
    st.caption("Health is updated by scraper runs and stored in news_state.json.")

    rows = source_health_rows(storage.source_health)
    if rows:
        health_df = pd.DataFrame(rows).sort_values(by=["score", "consecutive_failures"], ascending=[True, False])
        st.dataframe(health_df, use_container_width=True, hide_index=True)
    else:
        st.info("No source health data yet. Run the scraper once to populate it.")

    with st.expander("Recent failure queues", expanded=False):
        has_failures = False
        for url, entry in storage.source_health.items():
            queue = entry.get("failure_queue", [])
            if not queue:
                continue
            has_failures = True
            st.markdown(f"**{url}**")
            st.dataframe(pd.DataFrame(queue), use_container_width=True, hide_index=True)
        if not has_failures:
            st.caption("No recorded failures.")

    st.divider()
    st.subheader("Live connection check")
    st.caption("This checks connectivity now; it does not call the AI extractor.")

    if st.button("Run live check", type="primary"):
        st.write(f"Testing {len(TARGET_URLS)} sources...")
        progress_bar = st.progress(0)
        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {executor.submit(_check_url, url): url for url in TARGET_URLS}
            for i, future in enumerate(concurrent.futures.as_completed(future_to_url)):
                results.append(future.result())
                progress_bar.progress((i + 1) / len(TARGET_URLS))

        results_df = pd.DataFrame(results).sort_values(by="status", ascending=False)
        st.dataframe(results_df, use_container_width=True, hide_index=True)
