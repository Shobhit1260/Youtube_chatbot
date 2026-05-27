from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_cohere import CohereEmbeddings
from langchain_core.prompts import MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from pathlib import Path
import os
import re
import logging
import redis
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis connection
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    decode_responses=True
)

app = FastAPI(title="YouTube Chatbot API", version="1.0.0")

llm = ChatOpenAI(
    model="openai/gpt-3.5-turbo",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    temperature=0.3,
    default_headers={
        "HTTP-Referer": "https://youtube-chatbot-e77g.onrender.com",
        "X-Title": "youtube-chatbot"
    }
)

embeddings = CohereEmbeddings(
    model="embed-english-v3.0",
    cohere_api_key=os.getenv("COHERSE_KEY")
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


def get_video_transcript(video_id: str) -> str:
    """Get transcript with local caching"""
    transcript_path = os.path.join(
        TRANSCRIPT_DIR,
        f"{video_id}.txt"
    )

    # -----------------------------
    # LOAD FROM LOCAL FILE
    # -----------------------------
    if os.path.exists(transcript_path):
        logger.info("Loading transcript from local storage")
        with open(transcript_path, "r", encoding="utf-8") as file:
            return file.read()

    # -----------------------------
    # FETCH FROM YOUTUBE
    # -----------------------------
    try:
        logger.info("Fetching transcript from YouTube")
        fetched_transcript = YouTubeTranscriptApi().fetch(
            video_id,
            languages=["en"]
        )

        transcript_list = fetched_transcript.to_raw_data()
        transcript_text = " ".join(
            item["text"] for item in transcript_list
        )

        # Limit transcript size
        if len(transcript_text) > 50000:
            logger.warning(
                f"Transcript too long ({len(transcript_text)} chars)"
            )
            transcript_text = transcript_text[:50000] + "..."

        # -----------------------------
        # SAVE LOCALLY
        # -----------------------------
        with open(transcript_path, "w", encoding="utf-8") as file:
            file.write(transcript_text)
        logger.info("Transcript saved locally")
        return transcript_text

    except TranscriptsDisabled:
        raise HTTPException(
            status_code=400,
            detail="Transcripts are disabled for this video"
        )

    except NoTranscriptFound:
        raise HTTPException(
            status_code=404,
            detail="No transcript found for this video"
        )

    except Exception as e:
        logger.error(f"Error getting transcript: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get transcript: {str(e)}"
        )


# -----------------------------
# LONG-TERM MEMORY (FAISS)
# -----------------------------


def get_vectorstore(video_id, texts):
    path = f"vector_db/{video_id}"
    # Load existing vectorstore
    if os.path.exists(path):
        return FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
    # Create new vectorstore
    vector_store = FAISS.from_texts(texts, embeddings)
    vector_store.save_local(path)
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
        # Get transcript
        transcript_text = get_video_transcript(video_id)

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
                   you do not explain more than user asks.
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
        response = chain.invoke({
        "summary": summary_memory,
        "chat_history": short_memory,
        "context": context,
        "question": query.question
        })
        # Extract content from response
        answer = response.content if hasattr(response, "content") else str(response)
        
       # UPDATE SHORT-TERM MEMORY
        add_short_memory(
             video_id,
             "user",
             query.question
         )

        add_short_memory(
             video_id,
             "assistant",
             answer
         )

        # UPDATE SUMMARY MEMORY
        update_summary(
             video_id,
             llm,
             query.question,
             answer
        )

        logger.info("Successfully generated response")
        return {
            "answer": answer,
            "video_id": video_id,
            "transcript_length": len(transcript_text),
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )




if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
