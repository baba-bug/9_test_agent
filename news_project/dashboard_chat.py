import asyncio

import streamlit as st


def render_chat_page() -> None:
    st.header("Hub Chat")
    st.caption("Ask questions about captured news, papers, and favorites.")

    if "rag_chat" not in st.session_state:
        from news_project.rag_core import LibraryChat

        st.session_state.rag_chat = LibraryChat()
        st.session_state.rag_chat.load_library()

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "I've indexed your library. Ask me anything about recent AI papers or news.",
            }
        ]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Example: What are the latest 3D Gaussian Splatting papers?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        docs = []
        full_response = ""
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            try:
                with st.status("Searching index...", expanded=False) as status:
                    docs = st.session_state.rag_chat.retrieve_relevant(prompt)
                    st.write(f"Found {len(docs)} relevant articles.")
                    for doc in docs[:3]:
                        st.write(f"- {doc['title']}")
                    status.update(label="Search complete", state="complete", expanded=False)

                stream = asyncio.run(st.session_state.rag_chat.ask_deepseek(prompt, docs))
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        full_response += chunk.choices[0].delta.content
                        message_placeholder.markdown(full_response + "...")
                message_placeholder.markdown(full_response)
            except Exception as e:
                st.error(f"Error generating response: {e}")
                full_response = "Sorry, I encountered an error."

        st.session_state.messages.append({"role": "assistant", "content": full_response})

        with st.expander("Referenced sources", expanded=False):
            for i, doc in enumerate(docs, 1):
                highlight = " **(Cited)**" if f"[{i}]" in full_response else ""
                st.markdown(f"**[{i}]** [{doc['title']}]({doc['link']}){highlight}")
                st.caption(f"{doc.get('date', '')} | {doc.get('venue', '')} | Tags: {doc.get('tags', [])}")
