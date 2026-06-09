const TOKEN_KEY = "slc_access_token";
const EXPIRES_KEY = "slc_token_expires_at";

const token = localStorage.getItem(TOKEN_KEY);
if (!token) window.location.replace("/login");

// ---- DOM refs ----
const chatListEl = document.getElementById("chat-list");
const messagesEl = document.getElementById("messages");
const placeholderEl = document.getElementById("placeholder");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");
const statusEl = document.getElementById("status");
const modal = document.getElementById("modal");
const systemPromptEl = document.getElementById("system-prompt");

// ---- State ----
let chats = [];            // [{uid, title}]
let activeChatUid = null;
let responding = false;

// ---- API helper ----
function logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EXPIRES_KEY);
    window.location.replace("/login");
}

async function authedFetch(path, body) {
    const opts = {
        method: "POST",
        headers: { "Access-Token": token },
    };
    if (body !== undefined) {
        opts.headers["Content-Type"] = "application/json";
        opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    if (res.status === 401) { logout(); throw new Error("Session expired."); }
    return res;
}

function setStatus(text) { statusEl.textContent = text; }

// ---- Lightweight, dependency-free formatting ----
function escapeHtml(s) {
    return s.replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}
// Render fenced ``` code blocks and `inline code`; everything else stays as
// escaped text (the bubble uses white-space: pre-wrap for newlines).
function formatContent(text) {
    const parts = text.split(/```/);
    let html = "";
    for (let i = 0; i < parts.length; i++) {
        if (i % 2 === 1) {
            // code block; drop an optional leading language identifier line
            const code = parts[i].replace(/^[a-zA-Z0-9_+-]*\n/, "");
            html += "<pre><code>" + escapeHtml(code) + "</code></pre>";
        } else {
            html += escapeHtml(parts[i]).replace(/`([^`\n]+)`/g, "<code>$1</code>");
        }
    }
    return html;
}

// ---- Rendering ----
function clearMessages() {
    messagesEl.innerHTML = '<div class="messages-inner" id="messages-inner"></div>';
}
function messagesInner() { return document.getElementById("messages-inner"); }

function addMessage(role, content, { error = false } = {}) {
    const row = document.createElement("div");
    row.className = "row " + role;
    const bubble = document.createElement("div");
    bubble.className = "bubble" + (error ? " error" : "");
    bubble.innerHTML = formatContent(content);
    row.appendChild(bubble);
    messagesInner().appendChild(row);
    scrollToBottom();
    return bubble;
}

function scrollToBottom() { messagesEl.scrollTop = messagesEl.scrollHeight; }

function renderChatList() {
    chatListEl.innerHTML = "";
    if (chats.length === 0) {
        chatListEl.innerHTML = '<div class="empty">No chats yet. Start one with “New chat”.</div>';
        return;
    }
    for (const chat of chats) {
        const item = document.createElement("div");
        item.className = "chat-item" + (chat.uid === activeChatUid ? " active" : "");
        item.textContent = chat.title || chat.uid;
        item.title = chat.title || chat.uid;
        item.addEventListener("click", () => openChat(chat.uid));
        chatListEl.appendChild(item);
    }
}

// ---- Data loading ----
async function loadChats() {
    try {
        const res = await authedFetch("/list_chats");
        const data = await res.json();
        chats = data.chats || [];
        // Most recently used first (last_used is a stringified epoch timestamp).
        chats.sort((a, b) => (parseFloat(b.last_used) || 0) - (parseFloat(a.last_used) || 0));
        renderChatList();
    } catch (err) {
        setStatus("Couldn't load chats");
    }
}

async function openChat(uid) {
    activeChatUid = uid;
    renderChatList();
    clearMessages();
    placeholderEl.style.display = "none";
    inputEl.disabled = false;
    sendBtn.disabled = false;
    inputEl.focus();
    try {
        const res = await authedFetch("/get_chat", { chat_uid: uid });
        if (res.status === 404) { addMessage("assistant", "This chat no longer exists.", { error: true }); return; }
        const data = await res.json();
        for (const m of (data.messages || [])) {
            if (m.role === "user" || m.role === "assistant") addMessage(m.role, m.content);
        }
        if (!(data.messages || []).some(m => m.role === "user" || m.role === "assistant")) {
            clearMessages();
            const inner = messagesInner();
            const hint = document.createElement("div");
            hint.className = "placeholder";
            hint.style.minHeight = "200px";
            hint.textContent = "Say hello to start the conversation.";
            inner.appendChild(hint);
        }
    } catch (err) {
        addMessage("assistant", "Failed to load this chat.", { error: true });
    }
}

// ---- New chat ----
function openModal() { modal.classList.add("open"); systemPromptEl.focus(); }
function closeModal() { modal.classList.remove("open"); }

async function createChat() {
    const systemPrompt = systemPromptEl.value.trim() || "You are a helpful assistant.";
    closeModal();
    try {
        // The server returns the new chat's id in the Chat-UID response header
        // (no JSON body), so read it from there.
        const res = await authedFetch("/create_chat", { system_prompt: systemPrompt });
        const chatUid = res.headers.get("Chat-UID");
        await loadChats();
        if (chatUid) await openChat(chatUid);
    } catch (err) {
        setStatus("Couldn't create chat");
    }
}

// ---- Streaming send ----
// The server streams concatenated JSON objects (the browser strips the
// chunked framing), so we split them with a string-aware brace matcher.
function makeJsonSplitter(onObject) {
    let buf = "";
    return function feed(text) {
        buf += text;
        let depth = 0, start = -1, inStr = false, esc = false;
        for (let i = 0; i < buf.length; i++) {
            const ch = buf[i];
            if (inStr) {
                if (esc) esc = false;
                else if (ch === "\\") esc = true;
                else if (ch === '"') inStr = false;
                continue;
            }
            if (ch === '"') { inStr = true; continue; }
            if (ch === "{") { if (depth === 0) start = i; depth++; }
            else if (ch === "}") {
                depth--;
                if (depth === 0 && start !== -1) {
                    const slice = buf.slice(start, i + 1);
                    try { onObject(JSON.parse(slice)); } catch (e) { /* ignore partial */ }
                    start = -1;
                }
            }
        }
        // keep any trailing partial object
        buf = start === -1 ? "" : buf.slice(start);
    };
}

async function sendMessage() {
    const text = inputEl.value.trim();
    if (!text || responding || !activeChatUid) return;

    // clear the "say hello" hint on the first message
    if (!messagesInner()) clearMessages();
    const hint = messagesInner().querySelector(".placeholder");
    if (hint) hint.remove();

    addMessage("user", text);
    inputEl.value = "";
    autoGrow();
    setResponding(true);

    const bubble = addMessage("assistant", "");
    bubble.classList.add("cursor");
    let accumulated = "";
    let hadError = false;

    const splitter = makeJsonSplitter(obj => {
        if (obj.error) { hadError = true; return; }
        if (typeof obj.content === "string") {
            accumulated += obj.content;
            bubble.innerHTML = formatContent(accumulated);
            scrollToBottom();
        }
    });

    try {
        const res = await authedFetch("/send_chat_message", { chat_uid: activeChatUid, message: text });
        if (!res.ok && res.status !== 200) throw new Error("status " + res.status);
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            splitter(decoder.decode(value, { stream: true }));
        }
    } catch (err) {
        hadError = true;
    }

    bubble.classList.remove("cursor");
    if (hadError) {
        bubble.classList.add("error");
        bubble.innerHTML = formatContent(accumulated || "The model failed to respond. Please try again.");
    } else if (!accumulated) {
        bubble.innerHTML = formatContent("(no response)");
    }
    setResponding(false);
    inputEl.focus();
}

function setResponding(v) {
    responding = v;
    sendBtn.disabled = v;
    setStatus(v ? "Responding…" : "Ready");
}

// ---- Composer behaviour ----
function autoGrow() {
    inputEl.style.height = "auto";
    inputEl.style.height = Math.min(inputEl.scrollHeight, 200) + "px";
}
inputEl.addEventListener("input", autoGrow);
inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
sendBtn.addEventListener("click", sendMessage);

// ---- Wire up ----
document.getElementById("new-chat").addEventListener("click", openModal);
document.getElementById("modal-cancel").addEventListener("click", closeModal);
document.getElementById("modal-create").addEventListener("click", createChat);
document.getElementById("logout").addEventListener("click", logout);
modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

// ---- Init ----
loadChats();
