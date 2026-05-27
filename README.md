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

- Receives transcripts from the browser extension
- Processes questions using AI models (HuggingFace Gemma)
- Provides RESTful API endpoints

2. **Chrome Extension**
   - Modern, responsive UI
   - Integrates directly with YouTube pages

- Fetches transcripts from the open YouTube tab
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
  "question": "Your question here",
  "transcript_text": "Transcript text fetched in the extension"
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

### Test Transcript

```
GET /test/{video_id}
```

Check if a transcript is available for a specific video.

## 🛠️ Technology Stack

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

### Extension Configuration

Edit [extension/manifest.json](extension/manifest.json) to:

- Change extension name/description
- Modify permissions
- Update API endpoint URLs

## 🔧 Troubleshooting

### Common Issues

**1. "Transcripts are disabled for this video"**

- Some videos don't have transcripts available
- Try a different video with captions/subtitles

**2. "Transcript text is required" errors**

- Make sure you opened the extension on a YouTube watch page
- The extension now reads the transcript from the browser tab before calling the backend

**3. "Connection refused" errors**

- Ensure the backend server is running
- Check that you're using the correct port (8000)

**4. Extension not detecting video**

- Refresh the YouTube page
- Make sure you're on a video page (not search/home)

**5. API errors**

- Verify your HuggingFace token is valid
- Check backend logs for detailed error messages

### Reinstalling Virtual Environment

If you encounter dependency issues, delete and recreate the venv:

```bash
# Delete venv folder
rm -rf venv  # Mac/Linux
rmdir /s venv  # Windows

# Recreate
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r backend/requirements.txt
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is open source and available under the MIT License.

## 🙏 Acknowledgments

- HuggingFace for providing free AI model hosting
- Google for the YouTube Transcript API
- FastAPI for the excellent web framework
- LangChain for simplifying LLM integration

## 📞 Support

For issues, questions, or suggestions, please open an issue on the GitHub repository.

---

**Happy Learning! 🎓✨**
