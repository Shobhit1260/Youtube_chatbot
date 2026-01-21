chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "GET_VIDEO_ID") {
    try {
      // Check if we're on YouTube
      if (!window.location.hostname.includes('youtube.com')) {
        sendResponse({ error: "Not on YouTube page" });
        return;
      }

      let videoId = null;
      
      // Method 1: Extract from URL parameters (watch?v=...)
      const urlParams = new URLSearchParams(window.location.search);
      videoId = urlParams.get("v");
      
      // Method 2: Extract from pathname for shorts (/shorts/VIDEO_ID)
      if (!videoId && window.location.pathname.includes('/shorts/')) {
        videoId = window.location.pathname.split('/shorts/')[1]?.split('/')[0];
      }
      
      // Method 3: Extract from embed URLs (/embed/VIDEO_ID)
      if (!videoId && window.location.pathname.includes('/embed/')) {
        videoId = window.location.pathname.split('/embed/')[1]?.split('/')[0];
      }

      if (videoId) {
        sendResponse({ videoId });
      } else {
        sendResponse({ error: "No video ID found in URL" });
      }
    } catch (e) {
      console.error('Error extracting video ID:', e);
      sendResponse({ error: "Failed to extract video ID: " + e.message });
    }
  }
  return true; // Required to use sendResponse asynchronously
});