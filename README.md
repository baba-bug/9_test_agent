# AI News & Paper Monitor

This project is an automated AI news and research paper tracking system. It scrapes targeted websites, evaluates content using AI to score relevance and impact, and presents a personalized dashboard for keeping up with the latest in AI.

## Features

### 1. Intelligent Monitoring (`main.py`)
- **Multi-Source Scraping**: Automatically fetches content from configured news sites and ArXiv.
- **AI Scoring System**:
    - **Relevance**: Evaluates how relevant the content is to AI/ML.
    - **Impact**: Scores based on venue/source reputation.
    - **Personalization**: Boosts scores based on your interests inferred from your favorites.
- **Content Classification**: Automatically separates generic News from Academic Papers (ArXiv).
- **De-duplication**: Uses content hashing to avoid processing the same articles twice.

### 2. Interactive Dashboard (`dashboard.py`)
- **Dual-Column View**: Efficiently browse "News" and "Papers" side-by-side.
- **Latest vs. History**:
    - **Latest Updates**: See the freshest items since your last check.
    - **History**: Searchable archive of all past items.
- **Rich Interaction**:
    - **Table & Card Views**: Choose between a dense data table or expanded cards with summaries.
    - **One-Click Actions**: Favorite (⭐), Archive (✅), or Delete (🗑️) items instantly.
    - **Comments**: Add personal notes to any article.
- **RAG Chat (Hub Chat)**:
    - Chat with your entire library!
    - Uses Retrieval Augmented Generation to answer questions based on the papers and news you've collected.

## Installation & Usage

1.  **Clone/Pull the Repository**:
    ```bash
    git pull
    ```

2.  **Install Dependencies**:
    Ensure you have Python installed, then run:
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: Use a generic `pip install` or your conda environment as preferred)*

3.  **Run the Dashboard**:
    Start the visual interface using Streamlit:
    ```bash
    streamlit run news_project/dashboard.py
    ```
    The dashboard will open in your default browser (usually at `http://localhost:8501`).

4.  **(Optional) Run the Scraper Manually**:
    To trigger a fresh fetch of news/papers:
    ```bash
    python news_project/main.py
    ```
