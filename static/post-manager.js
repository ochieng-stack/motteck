// ======= post-manager.js ======

//save a new post
async function savePost(category, title, imageFile, description) {

    const formdata = new FormData();
    formdata.append("category", category);
    formdata.append("title", title);
    formdata.append("image", imageFile);   // 🔥 THIS MUST MATCH FLASK
    formdata.append("description", description);

    const response = await fetch('/add_post', {
        method: 'POST',
        body: formdata
    });

    const data = await response.json();

    if (data.success) {
        window.location.href = "/";
    } else {
        alert("Post failed");
    }
}


// Get all posts from firestore (through flask)

async function getAllPosts(){
    const response = await fetch('/get_posts');
    const posts = await response.json();

    return posts; // already an array
}


// Get posts by category
async function getPostByCategory(category){
    const posts = await getAllPosts();
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
}