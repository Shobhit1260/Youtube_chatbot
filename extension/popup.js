// Global variables
let currentVideoId = null;
let currentVideoTitle = null;
let currentTabId = null;

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
document.addEventListener("DOMContentLoaded", function () {
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
    currentTabId = tab.id;
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
    if (urlObj.hostname.includes("youtube.com")) {
      return urlObj.searchParams.get("v");
    }

    // YouTube shorts URL
    if (urlObj.pathname.includes("/shorts/")) {
      return urlObj.pathname.split("/shorts/")[1].split("/")[0];
    }

    // Youtu.be URL
    if (urlObj.hostname === "youtu.be") {
      return urlObj.pathname.substring(1);
    }

    return null;
  } catch (e) {
    return null;
  }
}

function showVideoInfo(title, url) {
  videoTitle.textContent = title.replace(" - YouTube", "");
  videoUrl.textContent = new URL(url).hostname;
  videoInfo.style.display = "block";
}

function updateStatus(type, message) {
  const statusDot = statusElement.querySelector(".status-dot");
  const statusText = statusElement.querySelector("span");

  statusText.textContent = message;

  statusDot.className = "status-dot";
  if (type === "error") {
    statusDot.style.background = "#ea4335";
  } else if (type === "loading") {
    statusDot.style.background = "#fbbc04";
  } else {
    statusDot.style.background = "#34a853";
  }
}

function enableInput() {
  questionInput.disabled = false;
  questionInput.focus();
}

function autoResizeTextarea() {
  questionInput.style.height = "auto";
  questionInput.style.height = Math.min(questionInput.scrollHeight, 80) + "px";
}

function updateCharCounter() {
  const length = questionInput.value.length;
  charCounter.textContent = `${length}/500`;

  if (length > 450) {
    charCounter.style.color = "#ea4335";
  } else if (length > 400) {
    charCounter.style.color = "#fbbc04";
  } else {
    charCounter.style.color = "#5f6368";
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
  addMessage(question, "user");

  // Clear input and disable while processing
  questionInput.value = "";
  questionInput.style.height = "auto";
  updateCharCounter();
  toggleSendButton();

  // Show loading
  showLoading();
  updateStatus("loading", "Processing...");

  try {
    console.log("Fetching transcript from active YouTube tab...");
    let transcriptText = null;
    try {
      transcriptText = await fetchTranscriptFromActiveTab();
    } catch (error) {
      console.warn(
        "Transcript extraction failed in the extension; backend will use any cached transcript.",
        error,
      );
    }

    console.log("Sending request to backend with video_id:", currentVideoId);
    console.log("Question:", question);

    const requestBody = {
      video_id: currentVideoId,
      question: question,
      transcript_text: transcriptText || "",
    };

    const response = await fetch("http://127.0.0.1:8000/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });

    console.log("Response status:", response.status);

    if (!response.ok) {
      let errorDetail = `HTTP ${response.status}`;
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorDetail;
      } catch (e) {
        // Response wasn't JSON, use status message
        errorDetail = response.statusText || errorDetail;
      }
      throw new Error(errorDetail);
    }

    const data = await response.json();
    console.log("Received response:", data);

    // Add AI response to chat
    addMessage(data.answer || "I couldn't generate a response.", "ai");
    updateStatus("ready", "Ready");
  } catch (error) {
    const errorMessageText =
      error instanceof Error ? error.message : String(error);
    const errorStack = error instanceof Error ? error.stack : "";
    console.error("Full error object:", error);
    console.error("Error message:", errorMessageText);
    console.error("Error stack:", errorStack);

    let errorMessage = "Sorry, I couldn't process your request. ";

    if (
      errorMessageText.includes("Failed to fetch") ||
      errorMessageText.includes("fetch")
    ) {
      errorMessage +=
        "Make sure the backend server is running at http://127.0.0.1:8000";
    } else if (errorMessageText.includes("Transcript text is required")) {
      errorMessage += "Could not read the transcript from this YouTube page.";
    } else if (errorMessageText.includes("No transcript found")) {
      errorMessage += "No transcript available for this video.";
    } else if (errorMessageText.includes("No transcript available")) {
      errorMessage += "No transcript available for this video.";
    } else {
      errorMessage += errorMessageText;
    }

    addMessage(errorMessage, "ai", true);
    updateStatus("error", "Error occurred");
  } finally {
    hideLoading();
    questionInput.focus();
  }
}

function addMessage(content, type, isError = false) {
  const messageDiv = document.createElement("div");
  messageDiv.className = `message ${type}-message`;

  const avatar = document.createElement("div");
  avatar.className = `${type}-avatar`;

  if (type === "ai") {
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

  const messageContent = document.createElement("div");
  messageContent.className = `message-content ${isError ? "error-message" : ""}`;

  const messageText = document.createElement("p");
  messageText.textContent = content;
  messageContent.appendChild(messageText);

  messageDiv.appendChild(avatar);
  messageDiv.appendChild(messageContent);

  messagesContainer.appendChild(messageDiv);

  // Scroll to bottom
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function showError(message) {
  addMessage(message, "ai", true);
}

function showLoading() {
  loadingOverlay.style.display = "flex";
}

function hideLoading() {
  loadingOverlay.style.display = "none";
}

async function fetchTranscriptFromActiveTab() {
  if (!currentTabId) {
    throw new Error("No active YouTube tab found");
  }

  const results = await chrome.scripting.executeScript({
    target: { tabId: currentTabId },
    world: "MAIN",
    func: async () => {
      try {
        const findInlinePlayerResponse = () => {
          const scripts = Array.from(document.querySelectorAll("script"));
          for (const s of scripts) {
            const t = s.textContent || "";
            const m = t.match(
              /ytInitialPlayerResponse\s*=\s*(\{[\s\S]*?\})\s*;/,
            );
            if (m && m[1]) {
              try {
                return JSON.parse(m[1]);
              } catch (e) {
                // ignore parse errors
              }
            }
          }
          return null;
        };

        let playerResponse =
          window.ytInitialPlayerResponse ||
          window.ytInitialData?.playerResponse ||
          null;

        if (!playerResponse) {
          try {
            const cfg =
              window.ytplayer &&
              window.ytplayer.config &&
              window.ytplayer.config.args &&
              window.ytplayer.config.args.player_response;
            if (cfg)
              playerResponse = typeof cfg === "string" ? JSON.parse(cfg) : cfg;
          } catch (e) {
            // ignore
          }
        }

        if (!playerResponse) {
          playerResponse = findInlinePlayerResponse();
        }

        const captionTracks =
          playerResponse?.captions?.playerCaptionsTracklistRenderer
            ?.captionTracks || [];

        const diag = {
          foundPlayerResponse: !!playerResponse,
          captionTracksLength: captionTracks ? captionTracks.length : 0,
        };

        if (!captionTracks || !captionTracks.length) {
          // Try YouTube timedtext API fallback (may work for auto-generated captions)
          try {
            const urlParams = new URL(location.href).searchParams;
            const vid =
              urlParams.get("v") ||
              (location.pathname.includes("/shorts/")
                ? location.pathname.split("/shorts/")[1].split("/")[0]
                : null);
            if (vid) {
              const alt = `https://www.youtube.com/api/timedtext?v=${vid}&lang=en&fmt=json3`;
              const altResp = await fetch(alt, { credentials: "include" });
              diag.timedtextFetch = altResp.status;
              if (altResp.ok) {
                const ct = altResp.headers.get("content-type") || "";
                if (ct.includes("application/json") || ct.includes("json")) {
                  const data = await altResp.json();
                  const events = data.events || [];
                  const ttext = events
                    .map((e) =>
                      (e.segs || []).map((s) => s.utf8 || s.a || "").join(""),
                    )
                    .join(" ")
                    .replace(/\s+/g, " ")
                    .trim();
                  if (ttext)
                    return {
                      transcriptText: ttext,
                      languageCode: "en",
                      _diag: diag,
                    };
                } else {
                  const txt = await altResp.text();
                  try {
                    const parser = new DOMParser();
                    const xml = parser.parseFromString(txt, "text/xml");
                    const texts = Array.from(xml.getElementsByTagName("text"));
                    const ttext = texts
                      .map((t) => t.textContent || "")
                      .join(" ")
                      .replace(/\s+/g, " ")
                      .trim();
                    if (ttext)
                      return {
                        transcriptText: ttext,
                        languageCode: "en",
                        _diag: diag,
                      };
                  } catch (e) {
                    const ttext = txt
                      .replace(/<[^>]+>/g, "")
                      .replace(/\s+/g, " ")
                      .trim();
                    if (ttext)
                      return {
                        transcriptText: ttext,
                        languageCode: "en",
                        _diag: diag,
                      };
                  }
                }
              }
            }
          } catch (e) {
            diag.timedtextError = String(e);
          }

          return {
            error: "No transcript available for this video.",
            _diag: diag,
          };
        }

        const preferredTrack =
          captionTracks.find((t) => (t.languageCode || "").startsWith("en")) ||
          captionTracks[0];
        let baseUrl = preferredTrack.baseUrl || preferredTrack.url || null;
        if (!baseUrl)
          return { error: "Caption track has no base URL.", _diag: diag };

        try {
          const tu = new URL(baseUrl);
          if (!tu.searchParams.get("fmt")) tu.searchParams.set("fmt", "json3");
          baseUrl = tu.toString();
        } catch (e) {
          // leave baseUrl as-is
        }

        const resp = await fetch(baseUrl, { credentials: "include" });
        diag.fetchStatus = resp.status;
        if (!resp.ok)
          return {
            error: `Failed to fetch transcript (${resp.status})`,
            _diag: diag,
          };

        const contentType = resp.headers.get("content-type") || "";
        let transcriptText = "";

        if (
          contentType.includes("application/json") ||
          contentType.includes("json")
        ) {
          const data = await resp.json();
          const events = data.events || [];
          transcriptText = events
            .map((e) => (e.segs || []).map((s) => s.utf8 || s.a || "").join(""))
            .join(" ")
            .replace(/\s+/g, " ")
            .trim();
        } else {
          const txt = await resp.text();
          // If we unexpectedly received HTML, include a short snippet for diagnostics
          if (contentType.includes("text/html") || txt.trim().startsWith("<")) {
            diag.htmlSnippet = txt.substring(0, 800);
          }
          try {
            const parser = new DOMParser();
            const xml = parser.parseFromString(txt, "text/xml");
            const texts = Array.from(xml.getElementsByTagName("text"));
            transcriptText = texts
              .map((t) => t.textContent || "")
              .join(" ")
              .replace(/\s+/g, " ")
              .trim();
          } catch (e) {
            transcriptText = txt
              .replace(/<[^>]+>/g, "")
              .replace(/\s+/g, " ")
              .trim();
          }
        }

        diag.contentType = contentType;
        diag.transcriptLength = transcriptText.length;
        if (!transcriptText)
          return {
            error: "No transcript text found for this video.",
            _diag: diag,
          };

        return {
          transcriptText,
          languageCode: preferredTrack.languageCode || "unknown",
          _diag: diag,
        };
      } catch (err) {
        return {
          error:
            "Unexpected error extracting transcript: " +
            (err && err.message ? err.message : String(err)),
          _diag: { error: String(err) },
        };
      }
    },
  });

  const payload = results && results[0] ? results[0].result : null;
  if (!payload)
    throw new Error("Failed to read transcript from the YouTube tab");
  if (payload.error) {
    const diag = payload._diag
      ? ` | diag: ${JSON.stringify(payload._diag)}`
      : "";
    throw new Error(payload.error + diag);
  }
  return payload.transcriptText;
}

// Auto-focus on input when popup opens
window.addEventListener("load", () => {
  setTimeout(() => {
    if (questionInput && !questionInput.disabled) {
      questionInput.focus();
    }
  }, 100);
});
