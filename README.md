# YouTube Chatbot

This project is a Chrome extension + FastAPI backend that answers questions about a YouTube video using transcript-based retrieval and conversation memory. The flow is:

1. Open a YouTube video in Chrome.
2. The extension reads the current video metadata and sends the question to the backend.
3. The backend extracts or loads the transcript, builds or reuses a FAISS vector store, retrieves relevant context, and calls an LLM through OpenRouter.
4. The answer is returned to the extension and displayed in the popup UI.

## Current project configuration

The repo is currently configured around the following stack:

- FastAPI backend in `backend/main.py`
- Redis-backed memory for short conversation history and summary memory
- OpenRouter API via `ChatOpenAI`
- Cohere embeddings via `CohereEmbeddings`
- FAISS vector index stored under `backend/vector_db/`
- Cached transcript storage under `backend/transcripts/`
- Chrome extension in `extension/` using Manifest V3

## Features

- Ask questions about the current YouTube video
- Use a transcript as the source of truth for grounding answers
- Cache transcripts locally to avoid repeated downloads
- Reuse a FAISS index for each video ID
- Maintain short-term chat memory and summary memory in Redis
- Works with a local API server or a hosted backend URL

## Project structure

```text
Youtube_chatbot/
├── backend/
│   ├── .env
│   ├── Dockerfile
│   ├── main.py
│   ├── requirements.txt
│   ├── transcripts/
│   └── vector_db/
├── extension/
│   ├── content.js
│   ├── manifest.json
│   ├── popup.html
│   ├── popup.js
│   └── styles.css
├── README.md
└── .gitignore
```

## Prerequisites

- Python 3.12+
- Redis running locally on `redis://localhost:6379/0`
- A valid OpenRouter API key
- A valid Cohere API key
- Chrome browser with Developer Mode enabled

## Environment variables

Create a `.env` file in the `backend` folder with the required values:

```env
REDIS_URL=redis://localhost:6379/0
OPENROUTER_API_KEY=your_openrouter_key
COHERE_KEY=your_cohere_key
```

These values are used in the backend config in `backend/main.py`.

## Backend setup

### 1. Create and activate a virtual environment

```bash
cd backend
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Redis

Make sure Redis is running before starting the API server. If you are running Redis locally, the default URL is:

```text
redis://localhost:6379/0
```

### 4. Start the backend

```bash
python main.py
```

The app runs at:

```text
http://127.0.0.1:8000
```

## Chrome extension setup

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable Developer mode
3. Click `Load unpacked`
4. Select the `extension` folder from this project
5. Open a YouTube video and click the extension icon

The extension currently points to the local backend at:

```text
http://127.0.0.1:8000
```

The extension manifest also includes a hosted backend URL in permissions for deployment scenarios:

```text
https://youtube-chatbot-e77g.onrender.com/*
```

## API behavior

### Health check

```http
GET /
```

Returns a simple health payload:

```json
{
  "status": "healthy",
  "message": "API running"
}
```

### Ask endpoint

```http
POST /ask
```

Request body:

```json
{
  "video_id": "dQw4w9WgXcQ",
  "question": "What is this video about?",
  "transcript_text": "Optional transcript text from the extension"
}
```

Response:

```json
{
  "answer": "AI-generated answer based on the transcript context",
  "video_id": "dQw4w9WgXcQ",
  "transcript_length": 1234
}
```

## How the backend works

The backend performs the following steps for each request:

- Extracts the YouTube video ID from a URL or ID string
- Loads the transcript from `backend/transcripts/<video_id>.txt` if it already exists
- Otherwise fetches it using `youtube_transcript_api`
- Splits the transcript into chunks
- Builds or loads a FAISS vector store in `backend/vector_db/<video_id>/`
- Uses MMR retrieval to find relevant context for the user question
- Loads memory from Redis for the given video
- Sends the summary, chat history, context, and question to the LLM
- Stores the latest user/assistant messages back in Redis

## Docker

A Dockerfile is included in `backend/` and exposes port 8000:

```bash
docker build -t youtube-chatbot ./backend
```

```bash
docker run -p 8000:8000 youtube-chatbot
```

## Notes

- `backend/transcripts/` and `backend/vector_db/` are generated automatically by the app.
- The extension can still fall back to cached transcripts if transcript extraction from the active tab fails.
- To switch the app to a deployed backend instead of local development, update the `API_BASE_URL` in `extension/popup.js` and confirm the correct host permissions in `extension/manifest.json`.

## Tech stack

### Backend

- FastAPI
- LangChain Core / LangChain Community / LangChain OpenAI
- Cohere embeddings
- FAISS
- Redis
- `youtube-transcript-api`
- OpenRouter via `ChatOpenAI`

### Frontend

- Manifest V3 Chrome extension
- HTML, CSS, JavaScript
- `fetch` API for backend requests


