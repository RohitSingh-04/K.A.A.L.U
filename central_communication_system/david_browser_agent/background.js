// RGS Hub WebSocket Endpoint for David Browser Agent
const RGS_WS_URL = "ws://localhost:8000/ws/david";
let socket = null;
let isConnected = false;
let pingIntervalId = null;

function connectRGS() {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
        return;
    }

    console.log("[David WS] Connecting to RGS Hub at " + RGS_WS_URL + "...");
    try {
        socket = new WebSocket(RGS_WS_URL);
    } catch (e) {
        console.error("[David WS] Connection initialization failed:", e);
        isConnected = false;
        return;
    }

    socket.onopen = () => {
        console.log("[David WS] Connected successfully to RGS Hub.");
        isConnected = true;
        startHeartbeat();
    };

    socket.onmessage = async (event) => {
        try {
            const data = JSON.parse(event.data);
            const sender = data.sender || "unknown";
            const action = data.action;
            const payload = data.payload || {};

            // Handle ping responses (heartbeat)
            if (action === "pong") {
                return;
            }

            console.log(`[David WS] Received task from '${sender}' | Action: '${action}'`);
            let resultPayload = {};

            if (action === "navigate") {
                resultPayload = await navigateTab(payload.url || payload.target, payload);
            } else if (
                action === "click" || 
                action === "type" || 
                action === "fill_form" || 
                action === "scrape" || 
                action === "read_page" || 
                action === "get_page_elements" || 
                action === "inspect" || 
                action === "press_key"
            ) {
                // If fill_form has no fields provided, fetch from RGS Hub profile endpoint
                if (action === "fill_form" && (!payload.fields || Object.keys(payload.fields).length === 0)) {
                    try {
                        const profResp = await fetch("http://localhost:8000/profile");
                        if (profResp.ok) {
                            const profData = await profResp.json();
                            const b = profData.basic_details || {};
                            const u = profData.urls || {};
                            payload.fields = {
                                "First Name": (b.name || "").split(" ")[0] || "",
                                "Last Name": (b.name || "").split(" ").slice(1).join(" ") || "",
                                "Full Name": b.name || "",
                                "Name": b.name || "",
                                "Email": b.email || "",
                                "Phone": b.phone || "",
                                "Location": b.location || "",
                                "LinkedIn": u.linkedin || "",
                                "GitHub": u.github || "",
                                "Portfolio": u.portfolio || "",
                                "Website": u.website || ""
                            };
                        }
                    } catch (e) {
                        console.warn("[David WS] Could not load profile from RGS Hub:", e);
                    }
                }
                resultPayload = await executeContentAction(action, payload);
            } else if (action === "capture_screenshot") {
                resultPayload = await captureBrowserScreenshot();
            } else {
                resultPayload = { success: false, error: `Unknown browser action '${action}'` };
            }

            // Send execution results back through RGS to the sender
            const responseMessage = {
                recipient: sender,
                action: `${action}_result`,
                payload: resultPayload
            };
            socket.send(JSON.stringify(responseMessage));
            console.log(`[David WS] Sent '${action}_result' back to '${sender}'.`);

        } catch (err) {
            console.error("[David WS Error] Failed to process message:", err);
        }
    };

    socket.onclose = () => {
        console.warn("[David WS] Connection closed. Will attempt reconnect...");
        isConnected = false;
        stopHeartbeat();
        setTimeout(connectRGS, 3000);
    };

    socket.onerror = (error) => {
        console.error("[David WS Error]:", error);
        isConnected = false;
    };
}

// Keep service worker and WebSocket alive by pinging RGS Hub every 15 seconds
function startHeartbeat() {
    stopHeartbeat();
    pingIntervalId = setInterval(() => {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({
                recipient: "rgs_hub",
                action: "ping",
                payload: {}
            }));
        } else {
            connectRGS();
        }
    }, 15000);
}

function stopHeartbeat() {
    if (pingIntervalId) {
        clearInterval(pingIntervalId);
        pingIntervalId = null;
    }
}

// Alarm to ensure Service Worker stays active and reconnected periodically
chrome.alarms.create("david_keepalive", { periodInMinutes: 0.3 });
chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === "david_keepalive") {
        if (!socket || socket.readyState !== WebSocket.OPEN) {
            connectRGS();
        }
    }
});

// Respond to popup requests for live status and manual reconnect
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "GET_STATUS") {
        sendResponse({ connected: isConnected && socket && socket.readyState === WebSocket.OPEN });
    } else if (request.action === "RECONNECT") {
        connectRGS();
        sendResponse({ status: "Connecting..." });
    }
    return true;
});

// Helper: Wait for tab to complete loading or timeout
function waitForTabLoad(tabId, timeoutMs = 4000) {
    return new Promise((resolve) => {
        let timer = null;
        const listener = (updatedTabId, changeInfo) => {
            if (updatedTabId === tabId && changeInfo.status === "complete") {
                chrome.tabs.onUpdated.removeListener(listener);
                if (timer) clearTimeout(timer);
                resolve();
            }
        };
        chrome.tabs.onUpdated.addListener(listener);
        timer = setTimeout(() => {
            chrome.tabs.onUpdated.removeListener(listener);
            resolve();
        }, timeoutMs);
    });
}

// Navigate browser tab to a specified URL and automatically return an intelligent page snapshot
async function navigateTab(url, payload = {}) {
    if (!url) return { success: false, error: "No URL provided for navigation." };
    try {
        let targetUrl = url;
        if (!targetUrl.startsWith("http://") && !targetUrl.startsWith("https://")) {
            targetUrl = "https://" + targetUrl;
        }

        let targetTab = null;
        if (payload.new_tab) {
            targetTab = await chrome.tabs.create({ url: targetUrl });
        } else {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            if (tab && tab.id) {
                targetTab = await chrome.tabs.update(tab.id, { url: targetUrl });
            } else {
                targetTab = await chrome.tabs.create({ url: targetUrl });
            }
        }

        // Wait for page to finish loading
        if (targetTab && targetTab.id) {
            await waitForTabLoad(targetTab.id, 4500);

            // Allow client-rendered frameworks a moment to populate DOM
            await new Promise((r) => setTimeout(r, 600));

            // Extract live page snapshot
            try {
                const results = await chrome.scripting.executeScript({
                    target: { tabId: targetTab.id },
                    func: invokeContentScriptAction,
                    args: ["scrape", {}]
                });
                const snapshot = results[0]?.result || {};
                return {
                    success: true,
                    url: snapshot.url || targetUrl,
                    title: snapshot.title || "Web Page",
                    featured_answer: snapshot.featured_answer || null,
                    search_results: snapshot.search_results || [],
                    page_summary: snapshot.page_text ? snapshot.page_text.substring(0, 1500) : "",
                    message: `Navigated to ${targetUrl}. Page Title: "${snapshot.title || 'Untitled'}"`
                };
            } catch (scriptErr) {
                return {
                    success: true,
                    url: targetUrl,
                    message: `Navigated to ${targetUrl}`
                };
            }
        }

        return { success: true, url: targetUrl, message: `Navigated to ${targetUrl}` };
    } catch (err) {
        return { success: false, error: err.toString() };
    }
}

// Execute DOM actions via Chrome Scripting API on the active tab
async function executeContentAction(action, payload) {
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab) return { success: false, error: "No active browser tab found. Please ensure a tab is open in Chrome." };

        const results = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: invokeContentScriptAction,
            args: [action, payload]
        });

        return results[0]?.result || { success: true };
    } catch (err) {
        return { success: false, error: err.toString() };
    }
}

// Function injected into the active webpage context
function invokeContentScriptAction(action, payload) {
    payload = payload || {};
    const query = (payload.selector || payload.target || "").trim();
    const textToType = payload.text !== undefined ? payload.text : (payload.value || "");

    // Helper: Is an element visible to the user?
    function isVisible(el) {
        if (!el || el.nodeType !== Node.ELEMENT_NODE) return false;
        const style = window.getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
            return false;
        }
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    }

    // Helper: Find element using multi-tier smart resolution (CSS, text, aria, placeholder, roles)
    function findElement(targetQuery) {
        if (!targetQuery) return null;

        // Tier 1: Direct standard querySelector
        try {
            const el = document.querySelector(targetQuery);
            if (el && isVisible(el)) return el;
            if (el) return el;
        } catch (e) {
            // Not a valid CSS selector (e.g. plain text "Compose" or "Save & close")
        }

        const lower = targetQuery.toLowerCase();

        // Tier 2: Check aria-label (exact & substring)
        try {
            const ariaMatch = Array.from(document.querySelectorAll("[aria-label]")).find((el) => {
                const label = (el.getAttribute("aria-label") || "").toLowerCase();
                return (label === lower || label.includes(lower)) && isVisible(el);
            });
            if (ariaMatch) return ariaMatch;
        } catch (e) {}

        // Tier 3: Check placeholder, title, name, or tooltip
        try {
            const attrMatch = Array.from(
                document.querySelectorAll("input, textarea, button, [title], [data-tooltip], [name]")
            ).find((el) => {
                const ph = (el.getAttribute("placeholder") || "").toLowerCase();
                const title = (el.getAttribute("title") || "").toLowerCase();
                const name = (el.getAttribute("name") || "").toLowerCase();
                const tip = (el.getAttribute("data-tooltip") || "").toLowerCase();
                return (
                    (ph.includes(lower) || title.includes(lower) || name === lower || tip.includes(lower)) &&
                    isVisible(el)
                );
            });
            if (attrMatch) return attrMatch;
        } catch (e) {}

        // Tier 4: Clickable elements by text content (buttons, links, role=button)
        try {
            const clickables = Array.from(
                document.querySelectorAll('button, a, [role="button"], [role="menuitem"], [role="tab"], input[type="button"], input[type="submit"]')
            );
            // Exact text match first
            const exactText = clickables.find((el) => {
                const txt = (el.innerText || el.textContent || "").trim().toLowerCase();
                return txt === lower && isVisible(el);
            });
            if (exactText) return exactText;

            // Substring text match
            const subText = clickables.find((el) => {
                const txt = (el.innerText || el.textContent || "").toLowerCase();
                return txt.includes(lower) && isVisible(el);
            });
            if (subText) return subText;
        } catch (e) {}

        // Tier 5: Semantic target keywords
        // (a) Compose button in webmail
        if (lower.includes("compose")) {
            const compose = Array.from(document.querySelectorAll('[role="button"], button, div')).find((el) => {
                const txt = (el.innerText || el.getAttribute("aria-label") || "").toLowerCase();
                return txt.includes("compose") && isVisible(el);
            });
            if (compose) return compose;
        }

        // (b) Recipient / To field
        if (lower === "to" || lower.includes("recipient")) {
            const toEl = Array.from(
                document.querySelectorAll('input, div[role="combobox"], [contenteditable="true"], div[name="to"]')
            ).find((el) => {
                const aria = (el.getAttribute("aria-label") || "").toLowerCase();
                const name = (el.getAttribute("name") || "").toLowerCase();
                const ph = (el.getAttribute("placeholder") || "").toLowerCase();
                return (aria.includes("to") || aria.includes("recipient") || name === "to" || ph.includes("recipient")) && isVisible(el);
            });
            if (toEl) return toEl;
        }

        // (c) Message body / rich text editor
        if (lower.includes("body") || lower.includes("message") || lower.includes("content")) {
            const bodyEl = Array.from(
                document.querySelectorAll('div[aria-label*="Message Body" i], div[role="textbox"], [contenteditable="true"], textarea')
            ).find((el) => isVisible(el));
            if (bodyEl) return bodyEl;
        }

        // (d) Subject line
        if (lower.includes("subject")) {
            const subjectEl = Array.from(
                document.querySelectorAll('input[name="subjectbox"], input[placeholder*="Subject" i], [aria-label*="Subject" i]')
            ).find((el) => isVisible(el));
            if (subjectEl) return subjectEl;
        }

        // (e) Send / Submit button
        if (lower.includes("send") || lower.includes("submit")) {
            const sendEl = Array.from(document.querySelectorAll('[role="button"], button, input[type="submit"]')).find((el) => {
                const aria = (el.getAttribute("aria-label") || "").toLowerCase();
                const txt = (el.innerText || "").toLowerCase();
                return (aria.includes("send") || txt.includes("send") || aria.includes("submit")) && isVisible(el);
            });
            if (sendEl) return sendEl;
        }

        // (f) Close / Save and close / Discard
        if (lower.includes("close") || lower.includes("save") || lower.includes("discard")) {
            const closeEl = Array.from(document.querySelectorAll('[role="button"], button, img[aria-label], [aria-label]')).find((el) => {
                const aria = (el.getAttribute("aria-label") || "").toLowerCase();
                const title = (el.getAttribute("title") || "").toLowerCase();
                return (aria.includes("close") || aria.includes("save") || aria.includes("discard") || title.includes("close")) && isVisible(el);
            });
            if (closeEl) return closeEl;
        }

        // Tier 6: Any visible element containing text
        try {
            const anyEl = Array.from(document.querySelectorAll("span, p, div, label")).find((el) => {
                const txt = (el.innerText || "").trim().toLowerCase();
                return (txt === lower || txt.includes(lower)) && isVisible(el);
            });
            if (anyEl) return anyEl;
        } catch (e) {}

        return null;
    }

    // Helper: Type into element handling both native inputs and contenteditable divs
    function typeText(targetEl, text, pressEnter, clearExisting) {
        targetEl.focus();

        const isContentEditable =
            targetEl.isContentEditable ||
            targetEl.getAttribute("contenteditable") === "true" ||
            targetEl.getAttribute("role") === "textbox";

        if (isContentEditable) {
            if (clearExisting) {
                targetEl.innerHTML = "";
            }
            // Rich text / contenteditable insertion
            const selection = window.getSelection();
            const range = document.createRange();
            range.selectNodeContents(targetEl);
            range.collapse(false);
            selection.removeAllRanges();
            selection.addRange(range);

            const inserted = document.execCommand("insertText", false, text);
            if (!inserted || !targetEl.innerText.includes(text)) {
                targetEl.innerText = (clearExisting ? "" : targetEl.innerText) + text;
                targetEl.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: text }));
            }
        } else {
            // Native input or textarea
            if (clearExisting) {
                targetEl.value = "";
            }
            const proto = targetEl instanceof HTMLTextAreaElement ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
            const desc = Object.getOwnPropertyDescriptor(proto, "value");
            if (desc && desc.set) {
                desc.set.call(targetEl, (clearExisting ? "" : targetEl.value) + text);
            } else {
                targetEl.value = (clearExisting ? "" : targetEl.value) + text;
            }
            targetEl.dispatchEvent(new Event("input", { bubbles: true }));
            targetEl.dispatchEvent(new Event("change", { bubbles: true }));
        }

        if (pressEnter) {
            const enterEvents = [
                new KeyboardEvent("keydown", { key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true, cancelable: true }),
                new KeyboardEvent("keypress", { key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true, cancelable: true }),
                new KeyboardEvent("keyup", { key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true, cancelable: true })
            ];
            for (const ev of enterEvents) {
                targetEl.dispatchEvent(ev);
            }
            if (targetEl.form) {
                targetEl.form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
            }
        }
    }

    // Helper: Extract search engine results if on Google / Bing / Yahoo / DuckDuckGo
    function extractSearchResults() {
        const results = [];
        // Google Search cards
        const googleItems = document.querySelectorAll(".g, [data-sokoban-container], .MjjYud");
        googleItems.forEach((item) => {
            const titleEl = item.querySelector("h3");
            const snippetEl = item.querySelector(".VwiC3b, .yXK7lf, [style*='-webkit-line-clamp']");
            const linkEl = item.querySelector("a[href]");
            if (titleEl && titleEl.innerText.trim()) {
                results.push({
                    title: titleEl.innerText.trim(),
                    snippet: snippetEl ? snippetEl.innerText.trim() : "",
                    link: linkEl ? linkEl.href : ""
                });
            }
        });

        // Check for featured snippet / direct answer card
        const directAnswer = document.querySelector(
            '[data-attrid="wa:/description"], .kp-blk, .hgKElc, [data-tts="answers"], .V3FYCf, .Z0LcW'
        );
        const featuredText = directAnswer ? directAnswer.innerText.trim() : null;

        return {
            featured_answer: featuredText,
            organic_results: results.slice(0, 5)
        };
    }

    // Helper: Extract interactive elements for perception
    function scanInteractiveElements() {
        const buttons = [];
        const inputs = [];
        const links = [];

        document.querySelectorAll('button, [role="button"], input[type="button"], input[type="submit"]').forEach((b) => {
            if (isVisible(b)) {
                const label = (b.getAttribute("aria-label") || b.innerText || b.getAttribute("title") || "").trim();
                if (label && !buttons.includes(label) && label.length < 50) {
                    buttons.push(label);
                }
            }
        });

        document.querySelectorAll('input, textarea, [contenteditable="true"]').forEach((inp) => {
            if (isVisible(inp)) {
                const label =
                    inp.getAttribute("aria-label") ||
                    inp.getAttribute("placeholder") ||
                    inp.getAttribute("name") ||
                    inp.getAttribute("id") ||
                    "";
                const type = inp.getAttribute("type") || (inp.isContentEditable ? "contenteditable" : "text");
                if (label && label.length < 50) {
                    inputs.push({ type, label, name: inp.name || "" });
                }
            }
        });

        document.querySelectorAll("a[href]").forEach((a) => {
            if (isVisible(a)) {
                const txt = (a.innerText || "").trim();
                if (txt && txt.length > 2 && txt.length < 40 && !links.includes(txt)) {
                    links.push(txt);
                }
            }
        });

        return {
            buttons: buttons.slice(0, 15),
            inputs: inputs.slice(0, 10),
            links: links.slice(0, 10)
        };
    }

    // --- Action Handlers ---

    if (action === "click") {
        const el = findElement(query);
        if (!el) {
            return {
                success: false,
                error: `Element not found for '${query}'. Available buttons: ${scanInteractiveElements().buttons.join(", ") || "None found"}`
            };
        }
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.focus();
        el.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
        el.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true }));
        el.click();
        return {
            success: true,
            message: `Clicked element matched by '${query}' (${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""})`
        };
    }

    if (action === "type") {
        const el = findElement(query);
        if (!el) {
            return {
                success: false,
                error: `Input element not found for '${query}'. Available fields: ${scanInteractiveElements().inputs.map((i) => i.label || i.name).join(", ") || "None found"}`
            };
        }
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        typeText(el, textToType, !!payload.press_enter, !!payload.clear);
        return {
            success: true,
            message: `Successfully typed into '${query}' (${el.tagName.toLowerCase()})`
        };
    }

    if (action === "fill_form") {
        const fields = payload.fields || {};
        const filled = [];
        const skipped = [];
        for (const [key, val] of Object.entries(fields)) {
            if (!val) continue;
            const el = findElement(key);
            if (el) {
                el.scrollIntoView({ behavior: "smooth", block: "center" });
                typeText(el, String(val), false, true);
                filled.push(key);
            } else {
                skipped.push(key);
            }
        }
        return {
            success: filled.length > 0,
            filled_fields: filled,
            skipped_fields: skipped,
            message: `Filled ${filled.length} fields: [${filled.join(", ")}]. Skipped: [${skipped.join(", ")}]`
        };
    }

    if (action === "scrape" || action === "read_page") {
        const target = query ? findElement(query) : document.body;
        const pageText = target ? (target.innerText || "").substring(0, 3500) : "";
        const searchData = extractSearchResults();

        return {
            success: true,
            title: document.title,
            url: window.location.href,
            page_text: pageText,
            featured_answer: searchData.featured_answer,
            search_results: searchData.organic_results
        };
    }

    if (action === "get_page_elements" || action === "inspect") {
        const elements = scanInteractiveElements();
        return {
            success: true,
            title: document.title,
            url: window.location.href,
            buttons: elements.buttons,
            inputs: elements.inputs,
            links: elements.links
        };
    }

    if (action === "press_key") {
        const key = payload.key || "Enter";
        const target = document.activeElement || document.body;
        target.dispatchEvent(new KeyboardEvent("keydown", { key: key, code: key, bubbles: true }));
        target.dispatchEvent(new KeyboardEvent("keypress", { key: key, code: key, bubbles: true }));
        target.dispatchEvent(new KeyboardEvent("keyup", { key: key, code: key, bubbles: true }));
        return { success: true, message: `Pressed key: ${key}` };
    }

    return { success: false, error: `Invalid content action: ${action}` };
}

// Capture screenshot of the active browser tab
async function captureBrowserScreenshot() {
    try {
        const dataUrl = await chrome.tabs.captureVisibleTab(null, { format: "jpeg", quality: 80 });
        return { success: true, screenshot_base64: dataUrl.split(",")[1] };
    } catch (err) {
        return { success: false, error: err.toString() };
    }
}

// Initialize connection on load
connectRGS();
