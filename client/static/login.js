const TOKEN_KEY = "slc_access_token";
const EXPIRES_KEY = "slc_token_expires_at";

// If already signed in, skip straight to the app.
if (localStorage.getItem(TOKEN_KEY)) {
    window.location.replace("/index");
}

let mode = "login"; // "login" | "register"

const tabLogin = document.getElementById("tab-login");
const tabRegister = document.getElementById("tab-register");
const submitBtn = document.getElementById("submit");
const form = document.getElementById("auth-form");
const msg = document.getElementById("msg");
const usernameInput = document.getElementById("username");
const passwordInput = document.getElementById("password");
const regTokenGroup = document.getElementById("reg-token-group");
const regTokenInput = document.getElementById("reg-token");

function setMode(next) {
    mode = next;
    const isLogin = mode === "login";
    tabLogin.classList.toggle("active", isLogin);
    tabRegister.classList.toggle("active", !isLogin);
    submitBtn.textContent = isLogin ? "Sign in" : "Create account";
    passwordInput.setAttribute("autocomplete", isLogin ? "current-password" : "new-password");
    regTokenGroup.hidden = isLogin;
    showMsg("", "");
}

function showMsg(text, kind) {
    msg.textContent = text;
    msg.className = "msg" + (kind ? " " + kind : "");
}

tabLogin.addEventListener("click", () => setMode("login"));
tabRegister.addEventListener("click", () => setMode("register"));

// Calls /api/login and persists the returned token. Returns true on success.
async function login(username, password) {
    const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Login-Username": username, "Login-Password": password },
    });
    if (res.status === 200) {
        const token = res.headers.get("Granted-Access-Token");
        const expires = res.headers.get("Access-Token-Expires-At");
        if (!token) throw new Error("Server did not return an access token.");
        localStorage.setItem(TOKEN_KEY, token);
        if (expires) localStorage.setItem(EXPIRES_KEY, expires);
        return true;
    }
    if (res.status === 401) throw new Error("Incorrect username or password.");
    if (res.status === 400) throw new Error("Please enter a username and password.");
    throw new Error("Sign in failed (status " + res.status + ").");
}

// Registers with a one-time registration token. On success the server returns
// an access token in the Access-Token response header, logging us in directly.
async function register(token, username, password) {
    const res = await fetch("/api/register", {
        method: "POST",
        headers: {
            "Registration-Token": token,
            "Registration-Username": username,
            "Registration-Password": password,
        },
    });
    if (res.status === 200) {
        const accessToken = res.headers.get("Access-Token");
        if (!accessToken) throw new Error("Server did not return an access token.");
        localStorage.setItem(TOKEN_KEY, accessToken);
        return true;
    }
    if (res.status === 401) throw new Error("Invalid or expired registration token.");
    if (res.status === 400) throw new Error("That username is already taken, or a field is missing.");
    if (res.status === 404) throw new Error("Registration isn't available yet on this server.");
    throw new Error("Registration failed (status " + res.status + ").");
}

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = usernameInput.value.trim();
    const password = passwordInput.value;
    if (!username || !password) {
        showMsg("Please enter a username and password.", "error");
        return;
    }

    submitBtn.disabled = true;
    try {
        if (mode === "register") {
            const regToken = regTokenInput.value.trim();
            if (!regToken) {
                showMsg("Please enter your registration token.", "error");
                submitBtn.disabled = false;
                return;
            }
            showMsg("Creating your account…", "");
            await register(regToken, username, password);
        } else {
            await login(username, password);
        }
        window.location.replace("/index");
    } catch (err) {
        showMsg(err.message || "Something went wrong.", "error");
        submitBtn.disabled = false;
    }
});
