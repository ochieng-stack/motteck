
// =========================
// VIEW TRACKING
// =========================
const viewedPosts = new Set();

async function viewPost(postId) {
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
// TEXT FORMATTER (GLOBAL STANDARD)
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
// SAFE TEXT TRUNCATION
// =========================
function getShortText(text, limit = 250) {
    const clean = text.replace(/<[^>]*>/g, ""); // strip HTML
    return clean.length > limit
        ? clean.slice(0, limit) + "..."
        : clean;
}


// =========================
// SEE MORE (UNIFIED)
// =========================
function setupSeeMoreButtons() {
    document.querySelectorAll(".post-card").forEach(card => {

        const btn = card.querySelector(".see-more-btn");
        const textEl = card.querySelector(".post-text");

        if (!btn || !textEl) return;

        const fullHTML = textEl.innerHTML;
        const plainText = textEl.innerText;

        if (plainText.length <= 250) {
            btn.style.display = "none";
            return;
        }

        const short = getShortText(plainText, 250);
        let expanded = false;

        textEl.innerHTML = `<p>${short}</p>`;

        btn.addEventListener("click", (e) => {
            e.stopPropagation();

            expanded = !expanded;
            textEl.innerHTML = expanded ? fullHTML : `<p>${short}</p>`;
            btn.textContent = expanded ? "See Less" : "See More";
        });
    });
}


// =========================
// VIEW OBSERVER
// =========================
function setupViewObserver() {
    const posts = document.querySelectorAll(".post-card");

    const observer = new IntersectionObserver((entries) => {

        entries.forEach(entry => {
            if (entry.isIntersecting) {

                const postId = entry.target.id.replace("post-", "");

                setTimeout(() => {
                    viewPost(postId);
                }, 2000);

            }
        });

    }, { threshold: 0.6 });

    posts.forEach(post => observer.observe(post));
}


// =========================
// INIT HELPERS
// =========================
function initPostFeatures() {
    setupSeeMoreButtons();
    setupViewObserver();
}


// expose globally (important for other pages)
window.likePost = likePost;
window.viewPost = viewPost;
window.initPostFeatures = initPostFeatures;