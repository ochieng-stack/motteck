// ======= post-manager.js (Supabase + Flask) ======

// Save a new post with Cloudinary image upload
async function savePost(category, title, imageFile, description) {
    const formdata = new FormData();
    formdata.append("category", category);
    formdata.append("title", title);
    formdata.append("image", imageFile); // must match Flask key
    formdata.append("description", description);

    try {
        const response = await fetch('/add_post', {
            method: 'POST',
            body: formdata
        });

        const data = await response.json();

        if (data.success) {
            window.location.href = "/";
        } else {
            alert("Post failed: " + (data.error || ""));
        }
    } catch (err) {
        console.error("Error saving post:", err);
        alert("An error occurred while saving the post.");
    }
}

// Fetch all posts from Supabase via Flask
async function getAllPosts() {
    try {
        const response = await fetch('/get_posts');
        const posts = await response.json();
        return posts; // array of posts
    } catch (err) {
        console.error("Error fetching posts:", err);
        return [];
    }
}

// Fetch posts by category
async function getPostByCategory(category) {
    const posts = await getAllPosts();
    return posts.filter(p => p.category === category);
}

// Load liked posts from localStorage to prevent double likes
let likedPosts = JSON.parse(localStorage.getItem('likedPosts')) || {};

// Handle liking a post (persistent in Supabase)
async function likePost(postId) {
    if (likedPosts[postId]) return; // already liked

    try {
        const response = await fetch(`/like/${postId}`, { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            likedPosts[postId] = true;
            localStorage.setItem('likedPosts', JSON.stringify(likedPosts));

            // Update like button in UI
            const likeBtn = document.querySelector(`button[data-id='${postId}']`);
            if (likeBtn) {
                let count = parseInt(likeBtn.getAttribute('data-likes')) || 0;
                count++;
                likeBtn.innerText = `${count}`;
                likeBtn.setAttribute('data-likes', count);
                likeBtn.classList.add('liked');
            }
        } else {
            console.error("Failed to like post:", data.error);
        }
    } catch (err) {
        console.error("Error liking post:", err);
    }
}

// Optional: Delete a post (for admin)
async function deletePost(postId) {
    try {
        const response = await fetch(`/delete_post/${postId}`, { method: 'DELETE' });
        const data = await response.json();
        if (data.success) {
            // Remove post from UI
            const postEl = document.getElementById(`post-${postId}`);
            if (postEl) postEl.remove();
        } else {
            console.error("Failed to delete post:", data.error);
        }
    } catch (err) {
        console.error("Error deleting post:", err);
    }
}