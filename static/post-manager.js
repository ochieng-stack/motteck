// ===== post-manager.js =====

// Increment post views when rendered
async function viewPost(postId) {
    try {
        const res = await fetch(`/view/${postId}`, { method: "POST" });
        const data = await res.json();
        if (data.success) {
            const viewCount = document.getElementById(`view-count-${postId}`);
            if (viewCount) viewCount.textContent = data.views;
        }
    } catch (err) {
        console.error("Error incrementing view:", err);
    }
}

// Handle liking a post
async function likePost(postId) {
    const likedKey = `liked-${postId}`;
    if (localStorage.getItem(likedKey)) {
        alert("You already liked this post!");
        return;
    }

    try {
        const res = await fetch(`/like/${postId}`, { method: "POST" });
        const data = await res.json();

        if (data.success) {
            const countSpan = document.getElementById(`like-count-${postId}`);
            const btn = document.getElementById(`like-btn-${postId}`);
            if (countSpan) countSpan.textContent = data.likes;
            if (btn) btn.style.backgroundColor = "#d6eefd";
            localStorage.setItem(likedKey, "true");
        } else {
            console.error("Failed to like post:", data.error);
        }
    } catch (err) {
        console.error("Error liking post:", err);
    }
}

// Setup "See More" buttons for long post content
function setupSeeMoreButtons() {
    const cards = document.querySelectorAll('.post-card');
    cards.forEach(card => {
        const seeMoreBtn = card.querySelector('.see-more-btn');
        const postText = card.querySelector('.post-text');
        if (!seeMoreBtn || !postText) return;

        const fullText = postText.innerHTML.trim();
        if (fullText.length <= 250) {
            seeMoreBtn.style.display = "none";
            return;
        }

        const shortText = fullText.slice(0, 250) + "...";
        let expanded = false;
        postText.innerHTML = shortText;

        seeMoreBtn.addEventListener("click", () => {
            expanded = !expanded;
            postText.innerHTML = expanded ? fullText : shortText;
            seeMoreBtn.textContent = expanded ? "See Less" : "See More";
        });
    });
}

// Create HTML for a single post
function createPostCard(post) {
    let image = post.image_url || "/static/images/ferrari.jpg";

    // Fix relative paths
    if (!image.startsWith("http")) image = "/static/" + image;

    return `
        <div class="post-card" id="post-${post.id}">
            <img src="${image}" alt="${post.title}">
            <div class="post-content">
                <h3 class="post-title">${post.title}</h3>
                <p class="post-text">${post.description || ""}</p>
                <div class="post-actions">
                    <button id="like-btn-${post.id}" onclick="likePost(${post.id})">
                        ❤️ <span id="like-count-${post.id}">${post.likes || 0}</span>
                    </button>
                    <span class="views">
                        👁️ <span id="view-count-${post.id}">${post.views || 0}</span>
                    </span>
                    <button class="see-more-btn">See More</button>
                </div>
            </div>
        </div>
    `;
}

// Fetch and render homepage posts
async function loadHomePosts() {
    try {
        const res = await fetch("/get_home_posts");
        const data = await res.json();

        const trendingContainer = document.getElementById("trending-posts");
        const recentContainer = document.getElementById("recent-posts");

        trendingContainer.innerHTML = "";
        recentContainer.innerHTML = "";

        // Keep track of IDs to prevent duplicates
        const renderedIds = new Set();

        // Render trending
        data.trending.forEach(post => {
            trendingContainer.innerHTML += createPostCard(post);
            renderedIds.add(post.id);
        });

        // Render recent, skipping any already in trending
        data.recent.forEach(post => {
            if (!renderedIds.has(post.id)) {
                recentContainer.innerHTML += createPostCard(post);
            }
        });

        // Setup see more buttons
        setupSeeMoreButtons();

        // Restore liked buttons style from localStorage
        data.trending.concat(data.recent).forEach(post => {
            const likedKey = `liked-${post.id}`;
            const btn = document.getElementById(`like-btn-${post.id}`);
            if (btn && localStorage.getItem(likedKey)) {
                btn.style.backgroundColor = "#d6eefd";
            }

            // Increment view count for each rendered post
            viewPost(post.id);
        });

    } catch (err) {
        console.error("Error loading homepage posts:", err);
    }
}

// Load posts when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
    loadHomePosts();
});