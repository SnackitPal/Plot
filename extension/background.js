/**
 * PLOT: The Cultural Atlas — Chrome Extension Background Service Worker
 * Manages side panel behavior and active tab deliberation context.
 */

// Configure side panel to open on action button click
chrome.runtime.onInstalled.addListener(() => {
  if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) {
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })
      .catch((err) => console.warn('[PLOT Background] Error setting side panel behavior:', err));
  }
});

// Helper: Broadcast active tab updates to sidepanel
async function notifyActiveTabChange(tabId, url, title) {
  try {
    await chrome.runtime.sendMessage({
      type: 'PLOT_TAB_CHANGED',
      tabId: tabId,
      url: url,
      title: title
    });
  } catch (err) {
    // Sidepanel may not be open; ignore disconnection errors
  }
}

// Track tab activation changes
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    if (tab && tab.url && !tab.url.startsWith('chrome://')) {
      notifyActiveTabChange(tab.id, tab.url, tab.title || '');
    }
  } catch (err) {
    console.debug('[PLOT Background] Tab query error:', err);
  }
});

// Track page navigation / completions
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab && tab.url && !tab.url.startsWith('chrome://')) {
    notifyActiveTabChange(tabId, tab.url, tab.title || '');
  }
});

// Respond to explicit requests from side panel
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && message.type === 'PLOT_GET_ACTIVE_TAB') {
    chrome.tabs.query({ active: true, currentWindow: true })
      .then((tabs) => {
        if (tabs && tabs[0]) {
          sendResponse({
            success: true,
            tabId: tabs[0].id,
            url: tabs[0].url,
            title: tabs[0].title
          });
        } else {
          sendResponse({ success: false, message: 'No active tab found' });
        }
      })
      .catch((err) => {
        sendResponse({ success: false, error: err.message });
      });
    return true; // Keep message channel open for async response
  }
});
