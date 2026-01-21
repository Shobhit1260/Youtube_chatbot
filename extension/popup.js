// Global variables
let currentVideoId = null;
let currentVideoTitle = null;

// DOM elements
const questionInput = document.getElementById("question");
const askButton = document.getElementById("ask");
const messagesContainer = document.getElementById("messages");
const charCounter = document.getElementById("charCounter");
const statusElement = document.getElementById("status");
const loadingOverlay = document.getElementById("loadingOverlay");
const videoInfo = document.getElementById("videoInfo");
const videoTitle = document.getElementById("videoTitle");
const videoUrl = document.getElementById("videoUrl");

// Initialize the popup
document.addEventListener('DOMContentLoaded', function() {
  initializePopup();
  setupEventListeners();
});

function initializePopup() {
  // Check if we're on a YouTube video page
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (!tabs || tabs.length === 0) {
      updateStatus("error", "No active tab found");
      return;
    }

    const tab = tabs[0];
    const videoId = extractVideoId(tab.url);
    
    if (videoId) {
      currentVideoId = videoId;
      currentVideoTitle = tab.title;
      showVideoInfo(tab.title, tab.url);
      updateStatus("ready", "Ready");
      enableInput();
    } else {
      updateStatus("error", "Not a YouTube video");
      showError("Please open a YouTube video to start chatting!");
    }
  });
}

function setupEventListeners() {
  // Send button click
  askButton.addEventListener("click", handleSendMessage);
  
  // Enter key to send (Shift+Enter for new line)
  questionInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });
  
  // Auto-resize textarea and update character counter
  questionInput.addEventListener("input", () => {
    autoResizeTextarea();
    updateCharCounter();
    toggleSendButton();
  });
  
  // Initial setup
  updateCharCounter();
  toggleSendButton();
}

function extractVideoId(url) {
  try {
    const urlObj = new URL(url);
    
    // Standard YouTube URL
    if (urlObj.hostname.includes('youtube.com')) {
      return urlObj.searchParams.get('v');
    }
    
    // YouTube shorts URL
    if (urlObj.pathname.includes('/shorts/')) {
      return urlObj.pathname.split('/shorts/')[1].split('/')[0];
    }
    
    // Youtu.be URL
    if (urlObj.hostname === 'youtu.be') {
      return urlObj.pathname.substring(1);
    }
    
    return null;
  } catch (e) {
    return null;
  }
}

function showVideoInfo(title, url) {
  videoTitle.textContent = title.replace(' - YouTube', '');
  videoUrl.textContent = new URL(url).hostname;
  videoInfo.style.display = 'block';
}

function updateStatus(type, message) {
  const statusDot = statusElement.querySelector('.status-dot');
  const statusText = statusElement.querySelector('span');
  
  statusText.textContent = message;
  
  statusDot.className = 'status-dot';
  if (type === 'error') {
    statusDot.style.background = '#ea4335';
  } else if (type === 'loading') {
    statusDot.style.background = '#fbbc04';
  } else {
    statusDot.style.background = '#34a853';
  }
}

function enableInput() {
  questionInput.disabled = false;
  questionInput.focus();
}

function autoResizeTextarea() {
  questionInput.style.height = 'auto';
  questionInput.style.height = Math.min(questionInput.scrollHeight, 80) + 'px';
}

function updateCharCounter() {
  const length = questionInput.value.length;
  charCounter.textContent = `${length}/500`;
  
  if (length > 450) {
    charCounter.style.color = '#ea4335';
  } else if (length > 400) {
    charCounter.style.color = '#fbbc04';
  } else {
    charCounter.style.color = '#5f6368';
  }
}

function toggleSendButton() {
  const hasText = questionInput.value.trim().length > 0;
  askButton.disabled = !hasText || !currentVideoId;
}

async function handleSendMessage() {
  const question = questionInput.value.trim();
  
  if (!question) {
    questionInput.focus();
    return;
  }
  
  if (!currentVideoId) {
    showError("Please open a YouTube video first!");
    return;
  }
  
  // Add user message to chat
  addMessage(question, 'user');
  
  // Clear input and disable while processing
  questionInput.value = '';
  questionInput.style.height = 'auto';
  updateCharCounter();
  toggleSendButton();
  
  // Show loading
  showLoading();
  updateStatus("loading", "Processing...");
  
  try {
    const response = await fetch("http://127.0.0.1:8000/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        video_id: currentVideoId, 
        question: question 
      }),
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || `HTTP ${response.status}`);
    }
    
    const data = await response.json();
    
    // Add AI response to chat
    addMessage(data.answer || "I couldn't generate a response.", 'ai');
    updateStatus("ready", "Ready");
    
  } catch (error) {
    console.error("API Error:", error);
    
    let errorMessage = "Sorry, I couldn't process your request. ";
    
    if (error.message.includes('fetch')) {
      errorMessage += "Make sure the backend server is running.";
    } else {
      errorMessage += error.message;
    }
    
    addMessage(errorMessage, 'ai', true);
    updateStatus("error", "Error occurred");
  } finally {
    hideLoading();
    questionInput.focus();
  }
}

function addMessage(content, type, isError = false) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${type}-message`;
  
  const avatar = document.createElement('div');
  avatar.className = `${type}-avatar`;
  
  if (type === 'ai') {
    avatar.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
        <path d="M12 17h.01"/>
      </svg>
    `;
  } else {
    avatar.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
        <circle cx="12" cy="7" r="4"/>
      </svg>
    `;
  }
  
  const messageContent = document.createElement('div');
  messageContent.className = `message-content ${isError ? 'error-message' : ''}`;
  
  const messageText = document.createElement('p');
  messageText.textContent = content;
  messageContent.appendChild(messageText);
  
  messageDiv.appendChild(avatar);
  messageDiv.appendChild(messageContent);
  
  messagesContainer.appendChild(messageDiv);
  
  // Scroll to bottom
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function showError(message) {
  addMessage(message, 'ai', true);
}

function showLoading() {
  loadingOverlay.style.display = 'flex';
}

function hideLoading() {
  loadingOverlay.style.display = 'none';
}

// Auto-focus on input when popup opens
window.addEventListener('load', () => {
  setTimeout(() => {
    if (questionInput && !questionInput.disabled) {
      questionInput.focus();
    }
  }, 100);
});