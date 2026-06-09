const TOKEN_KEY = "slc_access_token";
const EXPIRES_KEY = "slc_token_expires_at";

const accessToken = localStorage.getItem(TOKEN_KEY);
if (!accessToken) window.location.replace("/login");

// ---- DOM refs ----
const banner = document.getElementById("banner");
const createTokenForm = document.getElementById("create-token-form");
const tokenUsesEl = document.getElementById("token-uses");
const tokenAuthTypesEl = document.getElementById("token-auth-types");
const tokenRows = document.getElementById("token-rows");
const tokenEmpty = document.getElementById("token-empty");
const tokenCount = document.getElementById("token-count");
const userRows = document.getElementById("user-rows");
const userEmpty = document.getElementById("user-empty");
const userCount = document.getElementById("user-count");

// ---- Helpers ----
function logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EXPIRES_KEY);
    window.location.replace("/login");
}

function showBanner(text, kind) {
    banner.textContent = text;
    banner.className = "banner" + (kind ? " " + kind : "");
    banner.hidden = !text;
}

// POSTs to an admin endpoint with the access token and optional extra headers.
// Returns the Response. Surfaces 401 (not signed in / not an admin) via a banner.
async function adminFetch(path, headers = {}) {
    const res = await fetch(path, {
        method: "POST",
        headers: { "Access-Token": accessToken, ...headers },
    });
    if (res.status === 401) {
        showBanner("You need to be signed in as an admin to use this page.", "error");
        throw new Error("unauthorized");
    }
    return res;
}

function tagList(authTypes) {
    const wrap = document.createElement("div");
    wrap.className = "tags";
    if (!authTypes || authTypes.length === 0) {
        const t = document.createElement("span");
        t.className = "tag";
        t.textContent = "—";
        wrap.appendChild(t);
        return wrap;
    }
    for (const type of authTypes) {
        const t = document.createElement("span");
        t.className = "tag";
        t.textContent = type;
        wrap.appendChild(t);
    }
    return wrap;
}

function actionButton(label, { danger = false } = {}) {
    const btn = document.createElement("button");
    btn.className = "icon-btn" + (danger ? " danger" : "");
    btn.type = "button";
    btn.textContent = label;
    return btn;
}

// ---- Registration tokens ----
async function loadTokens() {
    let data;
    try {
        const res = await adminFetch("/api/list_registration_tokens");
        data = await res.json();
    } catch (err) {
        return;
    }
    const tokens = data.registration_tokens || [];
    tokenRows.innerHTML = "";
    tokenCount.textContent = tokens.length === 1 ? "1 token" : tokens.length + " tokens";
    tokenEmpty.hidden = tokens.length > 0;

    for (const token of tokens) {
        const tr = document.createElement("tr");

        const tdKey = document.createElement("td");
        const cell = document.createElement("div");
        cell.className = "token-cell";
        const key = document.createElement("span");
        key.className = "mono token-key";
        key.textContent = token.token_key;
        key.title = token.token_key;
        const copyBtn = actionButton("Copy");
        copyBtn.addEventListener("click", () => copyToken(token.token_key, copyBtn));
        cell.appendChild(key);
        cell.appendChild(copyBtn);
        tdKey.appendChild(cell);

        const tdUses = document.createElement("td");
        tdUses.className = "num mono";
        tdUses.textContent = token.uses_remaining;

        const tdTypes = document.createElement("td");
        tdTypes.appendChild(tagList(token.auth_types));

        const tdActions = document.createElement("td");
        tdActions.className = "actions";
        const delBtn = actionButton("Delete", { danger: true });
        delBtn.addEventListener("click", () => deleteToken(token.token_key));
        tdActions.appendChild(delBtn);

        tr.append(tdKey, tdUses, tdTypes, tdActions);
        tokenRows.appendChild(tr);
    }
}

async function copyToken(key, btn) {
    try {
        await navigator.clipboard.writeText(key);
        const original = btn.textContent;
        btn.textContent = "Copied";
        setTimeout(() => { btn.textContent = original; }, 1200);
    } catch (err) {
        showBanner("Couldn't copy to clipboard.", "error");
    }
}

async function createToken(e) {
    e.preventDefault();
    const uses = parseInt(tokenUsesEl.value, 10);
    const authTypes = tokenAuthTypesEl.value.trim();
    if (!Number.isInteger(uses) || uses < 1) {
        showBanner("Allowed uses must be a positive whole number.", "error");
        return;
    }
    if (!authTypes) {
        showBanner("Please provide at least one auth type.", "error");
        return;
    }
    try {
        const res = await adminFetch("/api/create_registration_token", {
            "Registration-Token-Allowed-Uses": String(uses),
            "Registration-Token-Auth-Types": authTypes,
        });
        if (res.status !== 200) {
            showBanner("Failed to create token (status " + res.status + ").", "error");
            return;
        }
        showBanner("Registration token created.", "ok");
        await loadTokens();
    } catch (err) {
        /* 401 already surfaced */
    }
}

async function deleteToken(key) {
    if (!confirm("Delete this registration token? It can no longer be used to register.")) return;
    try {
        const res = await adminFetch("/api/delete_registration_token", { "Registration-Token-Key": key });
        if (res.status !== 200 && res.status !== 404) {
            showBanner("Failed to delete token (status " + res.status + ").", "error");
            return;
        }
        showBanner("Registration token deleted.", "ok");
        await loadTokens();
    } catch (err) {
        /* 401 already surfaced */
    }
}

// ---- Users ----
async function loadUsers() {
    let data;
    try {
        const res = await adminFetch("/api/list_users");
        data = await res.json();
    } catch (err) {
        return;
    }
    const users = data.users || [];
    userRows.innerHTML = "";
    userCount.textContent = users.length === 1 ? "1 user" : users.length + " users";
    userEmpty.hidden = users.length > 0;

    for (const u of users) {
        const tr = document.createElement("tr");

        const tdUid = document.createElement("td");
        const uid = document.createElement("span");
        uid.className = "mono uid-cell";
        uid.textContent = u.uid;
        uid.title = u.uid;
        tdUid.appendChild(uid);

        const tdTypes = document.createElement("td");
        tdTypes.appendChild(tagList(u.auth_types));

        const tdHash = document.createElement("td");
        const hash = document.createElement("span");
        hash.className = "mono uid-cell";
        hash.textContent = u.hashed_username || "—";
        hash.title = u.hashed_username || "";
        tdHash.appendChild(hash);

        const tdActions = document.createElement("td");
        tdActions.className = "actions";
        const delBtn = actionButton("Delete", { danger: true });
        delBtn.addEventListener("click", () => deleteUser(u.uid));
        tdActions.appendChild(delBtn);

        tr.append(tdUid, tdTypes, tdHash, tdActions);
        userRows.appendChild(tr);
    }
}

async function deleteUser(uid) {
    if (!confirm("Delete this user? This permanently removes their account and chats.")) return;
    try {
        const res = await adminFetch("/api/delete_user", { "Delete-User-ID": uid });
        if (res.status !== 200) {
            showBanner("Failed to delete user (status " + res.status + ").", "error");
            return;
        }
        showBanner("User deleted.", "ok");
        await loadUsers();
    } catch (err) {
        /* 401 already surfaced */
    }
}

// ---- Wire up ----
createTokenForm.addEventListener("submit", createToken);
document.getElementById("logout").addEventListener("click", logout);

// ---- Init ----
loadTokens();
loadUsers();
