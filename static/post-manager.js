// ======= post-manager.js (Supabase + Flask) ======

// Handle liking a post
async function likePost(postId) {
    const likedKey = `liked-${postId}`;

    // prevent double liking
    if (localStorage.getItem(likedKey)) {
        alert("You already liked this post!");
        return;
    }

    try {
        const response = await fetch(`/like/${postId}`, { method: "POST" });
        const data = await response.json();

        if (data.success) {
            const countSpan = document.getElementById(`like-count-${postId}`);
            const button = document.getElementById(`like-btn-${postId}`);

            if (countSpan) countSpan.textContent = data.likes;
            if (button) button.style.backgroundColor = "#d6eefd";

            localStorage.setItem(likedKey, "true");
        } else {
            console.error("Failed to like post:", data.error);
        }
    } catch (err) {
        console.error("Error liking post:", err);
    }
}

// Delete a post (admin only)
async function deletePost(postId) {
    if (!confirm("Are you sure you want to delete this post?")) return;

    try {
        const response = await fetch(`/delete_post/${postId}`, { method: 'DELETE' });
        const data = await response.json();
        if (data.success) {
            const postEl = document.getElementById(`post-${postId}`);
            if (postEl) postEl.remove();
            alert("Post deleted successfully!");
        } else {
            alert("Failed to delete post: " + (data.error || ""));
        }
    } catch (err) {
        console.error("Error deleting post:", err);
        alert("An error occurred while deleting the post.");
    }
}

// Setup "See More" buttons for post cards
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

// Fetch and render posts on homepage
async function loadHomePosts() {
    try {
        const res = await fetch("/get_home_posts");
        const data = await res.json();

        const trendingContainer = document.getElementById("trending-posts");
        const recentContainer = document.getElementById("recent-posts");

        trendingContainer.innerHTML = "";
        recentContainer.innerHTML = "";

        function createPostCard(post) {
            return `
            <div class="post-card" id="post-${post.id}">
                <img src="${post.image_url}" alt="${post.title}">
                <div class="post-content">
                    <h3 class="post-title">${post.title}</h3>
                    <p class="post-text">${post.content.replace(/\n/g, '<br>')}</p>
                    <div class="post-actions">
                        <button id="like-btn-${post.id}" onclick="likePost(${post.id})">
                            ❤️ <span id="like-count-${post.id}">${post.likes || 0}</span>
                        </button>
                        <button class="see-more-btn">See More</button>
                        <button onclick="deletePost(${post.id})" class="delete-btn">🗑 Delete</button>
                    </div>
                </div>
            </div>
            `;
        }

        // Render Trending
        data.trending.forEach(post => {
            trendingContainer.innerHTML += createPostCard(post);
        });

        // Render Recent
        data.recent.forEach(post => {
            recentContainer.innerHTML += createPostCard(post);
        });

        setupSeeMoreButtons();

    } catch (err) {
        console.error("Error loading homepage posts:", err);
    }
}

// Load posts immediately
document.addEventListener("DOMContentLoaded", () => {
    loadHomePosts();
});