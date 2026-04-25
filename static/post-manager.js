// =========================
// VIEW TRACKING (CLEAN + SAFE)
// =========================
const viewedPosts = new Set();

async function viewPost(postId) {

    // prevent duplicate frontend calls
    if (viewedPosts.has(postId)) return;

    try {
        const res = await fetch(`/view/${postId}`, { method: "POST" });
        const data = await res.json();

        if (data.success) {
            const el = document.getElementById(`view-count-${postId}`);
            if (el) el.textContent = data.views;

            viewedPosts.add(postId);
        }

    } catch (err) {
        console.error("View error:", err);
    }
}


// =========================
// LIKE SYSTEM
// =========================
async function likePost(postId) {
    const key = `liked-${postId}`;

    if (localStorage.getItem(key)) {
        alert("You already liked this post!");
        return;
    }

    try {
        const res = await fetch(`/like/${postId}`, { method: "POST" });
        const data = await res.json();

        if (data.success) {
            const count = document.getElementById(`like-count-${postId}`);
            const btn = document.getElementById(`like-btn-${postId}`);

            if (count) count.textContent = data.likes;
            if (btn) btn.style.backgroundColor = "#d6eefd";

            localStorage.setItem(key, "true");
        }

    } catch (err) {
        console.error("Like error:", err);
    }
}


// =========================
// TEXT FORMATTER
// =========================
function formatText(text) {
    if (!text) return "";

    return text
        .split("\n")
        .filter(line => line.trim() !== "")
        .map(line => `<p>${line.trim()}</p>`)
        .join("");
}


// =========================
// SAFE TRUNCATION
// =========================
function getShortText(text, limit = 250) {
    const clean = text.replace(/<[^>]*>/g, "");
    return clean.length > limit
        ? clean.slice(0, limit) + "..."
        : clean;
}


// =========================
// SEE MORE (STABLE VERSION)
// =========================
function setupSeeMoreButtons() {

    document.querySelectorAll(".post-card").forEach(card => {

        const btn = card.querySelector(".see-more-btn");
        const textEl = card.querySelector(".post-text");

        if (!btn || !textEl) return;

        const fullText = textEl.innerText;

        if (fullText.length <= 250) {
            btn.style.display = "none";
            return;
        }

        const shortText = getShortText(fullText, 250);
        let expanded = false;

        textEl.innerHTML = `<p>${shortText}</p>`;

        btn.addEventListener("click", (e) => {
            e.stopPropagation();

            expanded = !expanded;
            textEl.innerHTML = expanded
                ? `<p>${fullText}</p>`
                : `<p>${shortText}</p>`;

            btn.textContent = expanded ? "See Less" : "See More";
        });
    });
}


// =========================
// VIEW OBSERVER (FIXED)
// =========================
function setupViewObserver() {

    const posts = document.querySelectorAll(".post-card");

    const observer = new IntersectionObserver((entries) => {

        entries.forEach(entry => {

            if (entry.isIntersecting) {

                const postId = entry.target.id.replace("post-", "");

                // prevent multiple triggers per session
                if (viewedPosts.has(postId)) return;

                setTimeout(() => {
                    viewPost(postId);
                }, 2500); // slightly safer delay

            }
        });

    }, {
        threshold: 0.7 // stricter = better quality views
    });

    posts.forEach(post => observer.observe(post));
}


// =========================
// INIT
// =========================
function initPostFeatures() {
    setupSeeMoreButtons();
    setupViewObserver();
}


// expose globally
window.likePost = likePost;
window.viewPost = viewPost;
window.initPostFeatures = initPostFeatures;