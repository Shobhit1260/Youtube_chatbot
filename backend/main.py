from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from dotenv import load_dotenv
from pathlib import Path
import os
import re
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Explicitly load .env from project root directory
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)
logger.info(f"Loaded .env from: {env_path}")
hf_token = os.getenv("HuggingFace_API_Key")

if not hf_token:
    raise RuntimeError("HuggingFace_API_Key not found in .env file")

os.environ["HUGGINGFACEHUB_API_TOKEN"] = hf_token
app = FastAPI(title="YouTube Chatbot API", version="1.0.0")

llm = HuggingFaceEndpoint(
         repo_id="mistralai/Mistral-7B-Instruct-v0.2",
         task="text-generation",
         max_new_tokens=512,
         temperature=0.7
         )

        # Wrap it with ChatHuggingFace for proper conversational handling
model = ChatHuggingFace(llm=llm)

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

def extract_video_id(url_or_id: str) -> str:
    """Extract video ID from YouTube URL or return ID if already provided"""
    # Handle various YouTube URL formats
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([^&\n?#]+)',
        r'^([a-zA-Z0-9_-]{11})$'  # Direct video ID
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    
    raise ValueError(f"Invalid YouTube URL or video ID: {url_or_id}")

def get_video_transcript(video_id: str) -> str:
    """Get transcript for a YouTube video with error handling"""
    try:
        # Try to get transcript
        fetched_transcript = YouTubeTranscriptApi().fetch(video_id, languages=['en'])
        transcript_list = fetched_transcript.to_raw_data()
        transcript_text = " ".join([item['text'] for item in transcript_list])
        
        # Validate transcript length (Gemini has token limits)
        if len(transcript_text) > 50000:  # Rough character limit
            logger.warning(f"Transcript too long ({len(transcript_text)} chars), truncating...")
            transcript_text = transcript_text[:50000] + "..."
        
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

@app.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy", 
        message="YouTube Chatbot API is running"
    )

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
        logger.info(f"Retrieved transcript ({len(transcript_text)} characters)")
        
    
        
        
        # Create prompt template
        prompt = ChatPromptTemplate.from_template("""
        You are an intelligent assistant helping users understand YouTube videos. 
        Use the following transcript to answer the user's question accurately and concisely.
        
        If the answer cannot be found in the transcript, say so clearly.
        
        Transcript: {transcript}
        
        Question: {question}
        
        Answer:""")
        
        # Create chain and invoke
        chain = prompt | model
        logger.info("Invoking AI model...")

        if len(transcript_text) > 12000:
            transcript_text = transcript_text[:12000]
        
        response = chain.invoke({
            "transcript": transcript_text,
            "question": query.question
        })
        
        # Extract content from response
        answer = response.content if hasattr(response, 'content') else str(response)
        
        logger.info("Successfully generated response")
        return {
            "answer": answer,
            "video_id": video_id,
            "transcript_length": len(transcript_text)
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"An unexpected error occurred: {str(e)}"
        )

@app.get("/test/{video_id}")
async def test_transcript(video_id: str):
    """Test endpoint to check if transcript is available"""
    try:
        video_id = extract_video_id(video_id)
        transcript_text = get_video_transcript(video_id)
        
        return {
            "video_id": video_id,
            "transcript_available": True,
            "transcript_length": len(transcript_text),
            "preview": transcript_text[:200] + "..." if len(transcript_text) > 200 else transcript_text
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)