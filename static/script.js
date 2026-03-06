/**
 * Country Info Agent — Frontend Logic
 * Handles chat interactions with the FastAPI /api/ask endpoint.
 */

const chatArea = document.getElementById("chatArea");
const messagesEl = document.getElementById("messages");
const welcomeEl = document.getElementById("welcome");
const input = document.getElementById("questionInput");
const sendBtn = document.getElementById("sendBtn");

let isLoading = false;

// ---- Event listeners ----
sendBtn.addEventListener("click", handleSend);
input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
    }
});

// Example chip clicks
document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
        const q = chip.getAttribute("data-q");
        if (q) {
            input.value = q;
            handleSend();
        }
    });
});

// ---- Send handler ----
async function handleSend() {
    const question = input.value.trim();
    if (!question || isLoading) return;

    // Hide welcome screen
    if (welcomeEl) {
        welcomeEl.style.display = "none";
    }

    // Add user message
    addMessage(question, "user");
    input.value = "";
    input.focus();

    // Add loading indicator
    const loadingEl = addLoading();

    setLoading(true);

    try {
        const res = await fetch("/api/ask", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question }),
        });

        const data = await res.json();

        // Remove loading
        loadingEl.remove();

        // Add bot response
        addMessage(data.answer, "bot", {
            country: data.country,
            flagUrl: data.flag_url,
            isError: data.error,
        });
    } catch (err) {
        loadingEl.remove();
        addMessage(
            "Sorry, I couldn't connect to the server. Please make sure the backend is running.",
            "bot",
            { isError: true }
        );
    } finally {
        setLoading(false);
    }
}

// ---- Message rendering ----
function addMessage(text, role, opts = {}) {
    const wrapper = document.createElement("div");
    wrapper.className = `message ${role}`;

    const bubble = document.createElement("div");
    bubble.className = `bubble${opts.isError ? " error" : ""}`;

    if (role === "bot" && opts.flagUrl && opts.country) {
        const flagRow = document.createElement("div");
        flagRow.className = "message-flag";

        const flagImg = document.createElement("img");
        flagImg.src = opts.flagUrl;
        flagImg.alt = `Flag of ${opts.country}`;
        flagImg.loading = "lazy";

        const countryName = document.createElement("span");
        countryName.textContent = opts.country;

        flagRow.appendChild(flagImg);
        flagRow.appendChild(countryName);
        bubble.appendChild(flagRow);
    }

    const textEl = document.createElement("div");
    textEl.className = "message-text";
    textEl.textContent = text;
    bubble.appendChild(textEl);

    wrapper.appendChild(bubble);
    messagesEl.appendChild(wrapper);

    // Scroll to bottom
    chatArea.scrollTop = chatArea.scrollHeight;
}

function addLoading() {
    const wrapper = document.createElement("div");
    wrapper.className = "message bot";

    const bubble = document.createElement("div");
    bubble.className = "bubble";

    const dots = document.createElement("div");
    dots.className = "loading-dots";
    dots.innerHTML = "<span></span><span></span><span></span>";

    bubble.appendChild(dots);
    wrapper.appendChild(bubble);
    messagesEl.appendChild(wrapper);

    chatArea.scrollTop = chatArea.scrollHeight;
    return wrapper;
}

function setLoading(state) {
    isLoading = state;
    sendBtn.disabled = state;
    input.disabled = state;
}
