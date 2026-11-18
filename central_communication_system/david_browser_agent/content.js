// David Browser Agent - Content Script
console.log("[David Content Script] Active on current page.");

// Listen for direct messages from the background script if needed
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "PING_PAGE") {
        sendResponse({ status: "ok", url: window.location.href, title: document.title });
    }
    return true;
});
