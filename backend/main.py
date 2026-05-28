from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_cohere import CohereEmbeddings
from langchain_core.prompts import MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional
import os
import re
import logging
import redis
import json
import traceback

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env (backend/.env preferred)
env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

# Redis connection
redis_client = redis.Redis(
    host="localhost",
    port=int(6379),
    decode_responses=True,
)

app = FastAPI(title="YouTube Chatbot API", version="1.0.0")

llm = ChatOpenAI(
    model="openai/gpt-3.5-turbo",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    temperature=0.3,
    default_headers={
        "HTTP-Referer": "http://127.0.0.1:8000",
        "X-Title": "youtube-chatbot",
    },
)


embeddings = CohereEmbeddings(
    model="embed-english-v3.0", cohere_api_key=os.getenv("COHERSE_KEY")
)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your extension's origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Query(BaseModel):
    video_id: str
    question: str
    transcript_text: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    message: str


# -----------------------------
# SHORT-TERM MEMORY
# -----------------------------

TRANSCRIPT_DIR = "transcripts"
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)


def add_short_memory(video_id, role, message):
    key = f"short_memory:{video_id}"
    redis_client.rpush(key, json.dumps({"role": role, "content": message}))
    # Keep only last 10 messages
    redis_client.ltrim(key, -10, -1)


def get_short_memory(video_id):
    key = f"short_memory:{video_id}"
    messages = redis_client.lrange(key, 0, -1)
    chat_history = []
    for msg in messages:
        data = json.loads(msg)
        if data["role"] == "user":
            chat_history.append(HumanMessage(content=data["content"]))
        else:
            chat_history.append(AIMessage(content=data["content"]))
    return chat_history


# -----------------------------
# SUMMARY MEMORY
# -----------------------------


def get_summary(video_id):
    key = f"summary_memory:{video_id}"
    return redis_client.get(key) or ""


def update_summary(video_id, llm, question, answer):
    old_summary = get_summary(video_id)
    prompt = f"""
You are a conversation summarizer.
Previous Summary:
{old_summary}
New Conversation:
User: {question}
Assistant: {answer}
Create updated concise summary:
"""
    response = llm.invoke(prompt)
    new_summary = response.content
    redis_client.set(f"summary_memory:{video_id}", new_summary)


def extract_video_id(url_or_id: str) -> str:
    """Extract video ID from YouTube URL or return ID if already provided"""
    # Handle various YouTube URL formats
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([^&\n?#]+)",
        r"^([a-zA-Z0-9_-]{11})$",  # Direct video ID
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    raise ValueError(f"Invalid YouTube URL or video ID: {url_or_id}")


def get_cached_transcript(video_id: str) -> Optional[str]:
    """Load transcript from local cache if it exists"""
    transcript_path = os.path.join(TRANSCRIPT_DIR, f"{video_id}.txt")

    if os.path.exists(transcript_path):
        logger.info("Loading transcript from local storage")
        with open(transcript_path, "r", encoding="utf-8") as file:
            return file.read()

    return None


def save_transcript(video_id: str, transcript_text: str) -> str:
    """Persist a transcript received from the client"""
    transcript_path = os.path.join(TRANSCRIPT_DIR, f"{video_id}.txt")

    cleaned_text = transcript_text.strip()

    if len(cleaned_text) > 50000:
        logger.warning(f"Transcript too long ({len(cleaned_text)} chars)")
        cleaned_text = cleaned_text[:50000] + "..."

    with open(transcript_path, "w", encoding="utf-8") as file:
        file.write(cleaned_text)

    logger.info("Transcript saved locally")
    return cleaned_text


# -----------------------------
# LONG-TERM MEMORY (FAISS)
# -----------------------------


def get_vectorstore(video_id, texts):
    logger.info(f"Split into {len(texts)} chunks")
    path = f"vector_db/{video_id}"

    logger.info(f"Vector DB path: {path}")
    logger.info(f"Texts count: {len(texts)}")

    if len(texts) > 0:
        logger.info(f"First text chunk: {texts[0][:100]}")

    # Load existing vectorstore
    if os.path.exists(path):
        logger.info("Loading existing FAISS index")
        return FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)

    logger.info("Creating new vectorstore")

    vector_store = FAISS.from_texts(texts, embeddings)

    logger.info("Saving vectorstore")

    vector_store.save_local(path)

    logger.info("Vectorstore created successfully")

    return vector_store


@app.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="healthy", message="YouTube Chatbot API is running")


@app.post("/ask")
async def ask_video_question(query: Query):
    """Ask a question about a YouTube video"""
    try:
        logger.info(f"Processing query for video: {query.video_id}")
        # Extract and validate video ID
        video_id = extract_video_id(query.video_id)
        logger.info(f"Extracted video ID: {video_id}")

        transcript_text = query.transcript_text
        if transcript_text:
            transcript_text = save_transcript(video_id, transcript_text)
        else:
            transcript_text = get_cached_transcript(video_id)

        if not transcript_text:
            raise HTTPException(
                status_code=400,
                detail="Transcript text is required from the extension or a cached prior request.",
            )

        # LOAD MEMORIES
        try:
            short_memory = get_short_memory(video_id)
            summary_memory = get_summary(video_id)
        except Exception as e:
            logger.error(f"Redis error: {e}")
            short_memory = []
            summary_memory = ""

        logger.info(f"Retrieved transcript ({len(transcript_text)} characters)")

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        texts = text_splitter.split_text(transcript_text)
        vector_store = get_vectorstore(video_id, texts)
        retriever = vector_store.as_retriever(search_type="mmr")
        docs = retriever.invoke(query.question)
        context = "\n\n".join(doc.page_content for doc in docs)
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
                   You are an intelligent YouTube assistant.
                   you do not explain more than user asks to you like
                   Eg:according to transcript .......
                   Explain whatever user asks.
                    Use:
                     1. Conversation summary
                     2. Recent chat history
                     3. Transcript context
                     Conversation Summary:
                     {summary}
                     """,
                ),
                MessagesPlaceholder(variable_name="chat_history"),
                (
                    "human",
                    """
                    Transcript Context:
                    {context}
                    Question:
                    {question}
                    """,
                ),
            ]
        )

        # Create chain and invoke
        chain = prompt | llm
        logger.info("Invoking AI model...")
        response = chain.invoke(
            {
                "summary": summary_memory,
                "chat_history": short_memory,
                "context": context,
                "question": query.question,
            }
        )

        # Extract content from response
        answer = response.content if hasattr(response, "content") else str(response)

        try:
            add_short_memory(video_id, "user", query.question)
        except Exception as e:
            logger.error(f"Failed to save user memory: {e}")

        try:
            add_short_memory(video_id, "assistant", answer)
        except Exception as e:
            logger.error(f"Failed to save assistant memory: {e}")

        try:
            update_summary(video_id, llm, query.question, answer)
        except Exception as e:
            logger.error(f"Failed to update summary: {e}")

        logger.info("Successfully generated response")
        return {
            "answer": answer,
            "video_id": video_id,
            "transcript_length": len(transcript_text),
        }

    except Exception:
        logger.exception("Unhandled exception")
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
