document.addEventListener("DOMContentLoaded", () => {
    const statusEl = document.getElementById("status");
    const reconnectBtn = document.getElementById("reconnectBtn");

    function updateStatus() {
        chrome.runtime.sendMessage({ action: "GET_STATUS" }, (response) => {
            if (chrome.runtime.lastError || !response) {
                statusEl.textContent = "Disconnected";
                statusEl.className = "status disconnected";
                return;
            }
            if (response.connected) {
                statusEl.textContent = "Connected";
                statusEl.className = "status connected";
            } else {
                statusEl.textContent = "Disconnected";
                statusEl.className = "status disconnected";
            }
        });
    }

    reconnectBtn.addEventListener("click", () => {
        statusEl.textContent = "Connecting...";
        statusEl.className = "status disconnected";
        chrome.runtime.sendMessage({ action: "RECONNECT" }, () => {
            setTimeout(updateStatus, 1500);
        });
    });

    updateStatus();
    setInterval(updateStatus, 3000);
});
