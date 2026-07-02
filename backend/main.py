from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api.formatters import TextFormatter
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from langchain_cohere import CohereEmbeddings

from dotenv import load_dotenv
import os
import re
import json
import logging
import redis

# LOAD ENV

load_dotenv()

# -------------------------
# LOGGING
# -------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------
# REDIS (SAFE INIT)
# -------------------------
import os
print(f"DEBUG: Using Redis URL: {os.getenv('REDIS_URL')}")
redis_url=os.getenv("REDIS_URL")
redis_client = redis.from_url(redis_url, decode_responses=True)

# -------------------------
# APP
# -------------------------
app = FastAPI(title="YouTube Chatbot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# LLM
# -------------------------
llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    temperature=0.3,
    default_headers={
        "HTTP-Referer": "http://127.0.0.1/8000",
        "X-Title": "youtube-chatbot"
    }
)


# -------------------------
# EMBEDDINGS (FIXED KEY NAME)
# -------------------------
embeddings = CohereEmbeddings(
    model="embed-english-v3.0",
    cohere_api_key=os.getenv("COHERE_KEY")  # FIXED
)

# -------------------------
# MODELS
# -------------------------
class Query(BaseModel):
    video_id: str
    question: str


class HealthResponse(BaseModel):
    status: str
    message: str


# -------------------------
# MEMORY HELPERS
# -------------------------
def add_short_memory(video_id, role, message):
    key = f"short_memory:{video_id}"
    redis_client.rpush(key, json.dumps({"role": role, "content": message}))
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


def get_summary(video_id):
    return redis_client.get(f"summary_memory:{video_id}") or ""


def update_summary(video_id, llm, question, answer):
    old_summary = get_summary(video_id)

    prompt = f"""
You are a conversation summarizer.

Previous summary:
{old_summary}

New exchange:
User: {question}
Assistant: {answer}

Write a short updated summary:
"""

    response = llm.invoke(prompt)
    redis_client.set(f"summary_memory:{video_id}", response.content)


# -------------------------
# VIDEO ID EXTRACTION
# -------------------------
def extract_video_id(url_or_id: str) -> str:
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([^&\n?#]+)",
        r"^([a-zA-Z0-9_-]{11})$",
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    raise ValueError("Invalid YouTube URL or video ID")


# TRANSCRIPT

TRANSCRIPT_DIR = "transcripts"
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)

def get_video_transcript(video_id: str) -> str:
    path = os.path.join(TRANSCRIPT_DIR, f"{video_id}.txt")

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    try:
        # 1. Instantiate the API client
        api = YouTubeTranscriptApi()
        
        # 2. Fetch the transcript instance
        fetched_transcript = api.fetch(video_id)
        
        # 3. Direct extraction (skipping the broken formatter)
        # Each line in fetched_transcript has a .text attribute
        text_transcript = "\n".join(line.text for line in fetched_transcript)

        # 4. Save it locally for caching
        with open(path, "w", encoding="utf-8") as f:
            f.write(text_transcript)

        return text_transcript

    except TranscriptsDisabled:
        raise HTTPException(400, "Transcripts disabled for this video")

    except NoTranscriptFound:
        raise HTTPException(404, "No transcript exists for this video")

    except Exception as e:
        logger.exception("Transcript error: %s", e)
        raise HTTPException(500, f"Transcript fetch failed: {str(e)}")
    
# vector DB

def get_vectorstore(video_id, texts):
    path = os.path.join("vector_db", video_id)
    os.makedirs("vector_db", exist_ok=True)

    # Load existing
    if os.path.exists(path):
        try:
            return FAISS.load_local(
                path,
                embeddings,
                allow_dangerous_deserialization=True
            )
        except Exception:
            logger.warning("FAISS load failed, rebuilding index...")

    # Create new
    vector_store = FAISS.from_texts(texts, embeddings)
    vector_store.save_local(path)
    return vector_store



# routes

@app.get("/", response_model=HealthResponse)
def health():
    return HealthResponse(status="healthy", message="API running")


@app.post("/ask")
def ask(query: Query):
    try:
        video_id = extract_video_id(query.video_id)

        transcript = get_video_transcript(video_id)

        # memory
        try:
            short_memory = get_short_memory(video_id)
            summary_memory = get_summary(video_id)
        except Exception:
            logger.exception("Redis error")
            short_memory = []
            summary_memory = ""

        # chunking (FIXED)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100
        )

        docs = splitter.create_documents([transcript])
        texts = [d.page_content for d in docs]

        vector_store = get_vectorstore(video_id, texts)
        retriever = vector_store.as_retriever(search_type="mmr")

        docs = retriever.invoke(query.question)

        if not docs:
            context = "No relevant context found."
        else:
            context = "\n\n".join(d.page_content for d in docs)

        # prompt (FIXED)
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "Answer ONLY from transcript context. Be concise. No extra info."),
            MessagesPlaceholder("chat_history"),
            ("human",
             "Summary:\n{summary}\n\nContext:\n{context}\n\nQuestion:\n{question}")
        ])

        chain = prompt | llm

        response = chain.invoke({
            "summary": summary_memory,
            "chat_history": short_memory,
            "context": context,
            "question": query.question
        })

        answer = response.content if hasattr(response, "content") else str(response)

        # memory update
        add_short_memory(video_id, "user", query.question)
        add_short_memory(video_id, "assistant", answer)
        update_summary(video_id, llm, query.question, answer)

        return {
            "answer": answer,
            "video_id": video_id,
            "transcript_length": len(transcript)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(e)
        raise HTTPException(500, str(e))


# -------------------------
# RUN
# -------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)