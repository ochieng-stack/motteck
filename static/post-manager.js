// ======= post-manager.js ======

//save a new post
function savePost(category, title,image,description) {
    const post = {
        id: Date.now(),
        category,
        title,
        image,
        description,
        date: new Date().toISOString()
    };
    // Get existing posts from localstorage
    const allPosts = JSON.parse(localStorage.getItem('motteckPosts')) || [];

    // Add new post
    allPosts.push(post);

    // save back to localstorage
    localStorage.setItem('motteckPosts',JSON.stringify(allPosts));
}

//Get all posts

function getAllPosts(){
    return JSON.parse(localStorage.getItem('motteckPosts')) || [];
}

// Get posts by category
function getPostByCategory(category){
    const posts = getAllPosts();
    return posts.filter(p => p.category === category);
}
// load liked posts from localStorage (so users cant like twice)
let likedPosts = JSON.parse(localStorage.getItem('likedPosts')) || {};

// Function to handle liking a post
function likePost(postId){
    //if the post is already liked, ignore it
    if ( likedPosts[postId]) return;

    // mark post as liked
    likedPosts[postId] = true;
    localStorage.setItem('likedPosts', JSON.stringify(likedPosts));

    // Find the button
    const likeBtn = document.querySelector(`button[data-id='${postId}']`);
    if (!likeBtn) return; // stop if button not found

    // get current like count
    let count = parseInt(likeBtn.getAttribute('data-likes')) || 0;
    count++;

    // update display
    likeBtn.innerText = `${count}`;
    likeBtn.setAttribute('data-likes', count);
    likeBtn.classList.add('liked');

    // send updated to server (optional)
    fetch('/like', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json'},
        body: JSON.stringify({ post_id: postId})
    });
}