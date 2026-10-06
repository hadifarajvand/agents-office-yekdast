/**
 * Citadel Agent Assistant — Service Worker (MV3)
 *
 * Captures the active tab context on user action and posts it to the
 * FastAPI backend /agent/browse endpoint. Mirrors the Claude-in-Chrome
 * pattern: explicit user action per tab, no background surveillance.
 */

const API_BASE = "http://localhost:8000";

// Open side panel when extension icon is clicked
chrome.action.onClicked.addListener(async (tab) => {
  await chrome.sidePanel.open({ tabId: tab.id });
});

// Listen for messages from the side panel
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "BROWSE_QUERY") {
    handleBrowseQuery(message).then(sendResponse);
    return true; // async response
  }
});

async function handleBrowseQuery({ tabId, query }) {
  try {
    // Get the active tab content
    const [result] = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => document.body.innerText.slice(0, 10000),
    });

    const tabContent = result?.result || "";
    const tab = await chrome.tabs.get(tabId);

    // Post to the backend
    const response = await fetch(`${API_BASE}/agent/browse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tab_url: tab.url,
        tab_content: tabContent,
        user_query: query,
      }),
    });

    if (!response.ok) {
      return { status: "error", answer: `Backend returned ${response.status}` };
    }

    return await response.json();
  } catch (error) {
    return { status: "error", answer: error.message };
  }
}
