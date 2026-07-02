# 🎥 Youtube Chatbot Assistant

An AI-powered chatbot that allows you to ask questions about any YouTube video. The assistant analyzes video transcripts using advanced language models to provide accurate answers about the content.

## ✨ Features

- 🤖 **AI-Powered Q&A**: Ask questions about any YouTube video and get intelligent responses
- 🎯 **Chrome Extension**: Convenient browser extension with a beautiful, modern UI
- 🚀 **FastAPI Backend**: High-performance API server for processing requests
- 📝 **Transcript Analysis**: Automatically fetches and analyzes video transcripts
- 🔄 **Real-time Responses**: Fast and accurate answers using HuggingFace models
- 💬 **Conversational Interface**: User-friendly chat interface for natural interactions

## 🏗️ Architecture

The project consists of two main components:

1. **Backend API** (FastAPI)
   - Fetches YouTube video transcripts
   - Processes questions using AI models (HuggingFace Gemma)
   - Provides RESTful API endpoints

2. **Chrome Extension**
   - Modern, responsive UI
   - Integrates directly with YouTube pages
   - Communicates with the backend API

## 📋 Prerequisites

- Python 3.8 or higher
- Google Chrome browser
- HuggingFace account (for API token)

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd youtube_Chatbot 
```

### 2. Set Up Backend

#### Create Virtual Environment

```bash
python -m venv venv
```

#### Activate Virtual Environment

**Windows:**
```bash
venv\Scripts\activate
```

**Mac/Linux:**
```bash
source venv/bin/activate
```

#### Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

#### Configure Environment Variables

Create a `.env` file in the `backend` directory:

```env
HF_TOKEN=your_huggingface_token_here
```

**Note:** You can get your HuggingFace token from [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)

### 3. Install Chrome Extension

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top right)
3. Click **Load unpacked**
4. Select the `extension` folder from this project
5. The extension icon should appear in your browser toolbar

## 🎮 Usage

### Start the Backend Server

```bash
cd backend
python main.py
```

The API server will start at `http://127.0.0.1:8000`

### Use the Extension

1. Navigate to any YouTube video
2. Click the extension icon in your browser toolbar
3. The extension will detect the current video
4. Type your question in the chat input
5. Get instant AI-powered answers about the video content

## 📡 API Endpoints

### Health Check
```
GET /
```
Returns the API health status.

### Ask Question
```
POST /ask
```
**Request Body:**
```json
{
  "video_id": "VIDEO_ID_OR_URL",
  "question": "Your question here"
}
```

**Response:**
```json
{
  "answer": "AI-generated answer",
  "video_id": "VIDEO_ID",
  "transcript_length": 5000
}
```



### Backend
- **FastAPI**: Modern web framework for building APIs
- **LangChain**: Framework for LLM applications
- **HuggingFace**: AI model hosting (Gemma 2-2B)
- **YouTube Transcript API**: Fetch video transcripts
- **Python-dotenv**: Environment variable management

### Frontend (Extension)
- **HTML/CSS/JavaScript**: Core web technologies
- **Chrome Extension API**: Browser integration
- **Fetch API**: HTTP requests to backend

## 📁 Project Structure

```
Ask-It-Youtube-Chatbot-Assistant/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── requirements.txt     # Python dependencies
│   └── .env                 # Environment variables (create this)
├── extension/
│   ├── manifest.json        # Extension configuration
│   ├── popup.html          # Extension UI
│   ├── popup.js            # Extension logic
│   ├── content.js          # Content script
│   └── styles.css          # Extension styles
└── README.md               # This file
```

## ⚙️ Configuration

### Backend Configuration

Edit [backend/main.py](backend/main.py) to customize:
- AI model selection
- Token limits
- Temperature settings
- CORS origins



## 🙏 Acknowledgments

- HuggingFace for providing free AI model hosting
- Google for the YouTube Transcript API
- FastAPI for the excellent web framework
- LangChain for simplifying LLM integration


