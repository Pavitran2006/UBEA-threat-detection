import { Router } from './router.js';
import { Login, Signup, Dashboard } from './components.js';

// --- Global Toast System ---
window.showToast = (message, type = 'info') => {
    const container = document.getElementById('toast-container');
    if (!container) {
        console.warn('Toast container not found. Please add <div id="toast-container"></div> to your HTML.');
        return;
    }
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 500);
    }, 4000);
};

// Initial state check
window.addEventListener('load', () => {
    // Hide loader after a brief delay for perceived performance
    setTimeout(() => {
        const loader = document.querySelector('.initial-loader');
        if (loader) loader.style.display = 'none';
    }, 500);
});

const routes = {
    '/': { component: Login.render, onRender: Login.init, showNav: false },
    '/login': { component: Login.render, onRender: Login.init, showNav: false },
    '/signup': { component: Signup.render, onRender: Signup.init, showNav: false },
    '/dashboard': {
        component: Dashboard.render,
        onRender: Dashboard.init,
        protected: true,
        showNav: true
    },
    '*': { component: () => '<h1>404 - Not Found</h1><p>System Breach or Missing Route.</p>', showNav: false }
};

document.addEventListener('DOMContentLoaded', () => {
    window.appRouter = new Router(routes);

    // Global Logout
    document.getElementById('logoutBtn').addEventListener('click', async () => {
        try {
            await fetch('/api/logout', { method: 'POST' });
            localStorage.removeItem('isAuthenticated');
            localStorage.removeItem('user');
            window.appRouter.navigateTo('/login');
            window.showToast('Logged out successfully!', 'success');
        } catch (err) {
            console.error('Logout failed:', err);
            window.showToast('Logout failed. Please try again.', 'error');
        }
    });

    // Mobile Toggle
    document.querySelector('.mobile-toggle').addEventListener('click', () => {
        document.getElementById('main-nav').classList.toggle('active');
    });
});

window.addEventListener('authChange', () => {
    // Force router to check state and update UI
    window.appRouter.handleRoute();
});
