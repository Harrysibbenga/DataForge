/**
 * auth-ui.js - Handles authentication state and UI changes across the site
 */

document.addEventListener('DOMContentLoaded', function() {
    // Check if user is logged in (has valid token)
    const token = localStorage.getItem('auth_token');
    const isLoggedIn = !!token;
    
    // Get navigation elements
    const guestNav = document.getElementById('guest-nav');
    const userNav = document.getElementById('user-nav');
    const dashboardNavItem = document.getElementById('dashboard-nav-item');
    const userEmail = document.getElementById('user-email');
    const logoutBtn = document.getElementById('logout-btn');
    
    // Update navigation based on auth state
    if (isLoggedIn) {
        // Show user navigation
        if (guestNav) guestNav.classList.add('d-none');
        if (userNav) userNav.classList.remove('d-none');
        if (dashboardNavItem) dashboardNavItem.classList.remove('d-none');
        
        // Set user email (in a real app, decode from JWT or fetch from API)
        const email = localStorage.getItem('user_email') || 'user@example.com';
        if (userEmail) userEmail.textContent = email;
        
        // Handle logout button
        if (logoutBtn) {
            logoutBtn.addEventListener('click', function(e) {
                e.preventDefault();
                logout();
            });
        }
        
        // If we're on a protected page, fetch user data
        if (window.location.pathname === '/dashboard') {
            fetchUserData();
        }
    } else {
        // Show guest navigation
        if (guestNav) guestNav.classList.remove('d-none');
        if (userNav) userNav.classList.add('d-none');
        if (dashboardNavItem) dashboardNavItem.classList.add('d-none');
        
        // If we're on a protected page, redirect to login
        if (window.location.pathname === '/dashboard') {
            window.location.href = '/login?redirect=dashboard';
        }
    }
    
    // Highlight current page in navigation
    highlightCurrentPage();
});

/**
 * Log out the user
 */
function logout() {
    // Clear auth data
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_email');
    
    // Redirect to home page
    window.location.href = '/';
}

/**
 * Fetch user data from the API
 */
function fetchUserData() {
    const token = localStorage.getItem('auth_token');
    
    // In a real app, fetch data from your API
    fetch('/api/dashboard/user-info', {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to fetch user data');
        }
        return response.json();
    })
    .then(data => {
        // Store email for use across the site
        localStorage.setItem('user_email', data.email);
        
        // Update UI with user data
        const userEmail = document.getElementById('user-email');
        if (userEmail) userEmail.textContent = data.email;
        
        // Update other elements with user data if needed
        // For example, update the subscription info in the dashboard
    })
    .catch(error => {
        console.error('Error fetching user data:', error);
        
        // If unauthorized, log out
        if (error.message.includes('401')) {
            logout();
        }
    });
}

/**
 * Highlight the current page in the navigation
 */
function highlightCurrentPage() {
    const currentPath = window.location.pathname;
    
    // Remove active class from all nav items
    document.querySelectorAll('.navbar-nav .nav-link').forEach(link => {
        link.classList.remove('active');
    });
    
    // Add active class to current page
    const activeLink = document.querySelector(`.navbar-nav .nav-link[href="${currentPath}"]`);
    if (activeLink) {
        activeLink.classList.add('active');
    }
}
