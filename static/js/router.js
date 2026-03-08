export class Router {
    constructor(routes) {
        this.routes = routes;
        this.rootElement = document.getElementById('app-root');
        window.addEventListener('popstate', () => this.handleRoute());
        this.init();
    }

    init() {
        document.addEventListener('click', e => {
            const target = e.target.closest('[data-link]');
            if (target) {
                e.preventDefault();
                this.navigateTo(target.getAttribute('data-link'));
            }
        });
        this.handleRoute();
    }

    navigateTo(path) {
        window.history.pushState(null, null, path);
        this.handleRoute();
    }

    async handleRoute() {
        const path = window.location.pathname;
        const route = this.routes[path] || this.routes['*'];

        // Auth Guard — verify session via HTTP-only cookie (not localStorage)
        let isAuthenticated = false;
        try {
            const res = await fetch('/api/me', { credentials: 'same-origin' });
            if (res.ok) {
                const user = await res.json();
                isAuthenticated = true;
                // Keep user info in localStorage only for display (username badge)
                localStorage.setItem('user', JSON.stringify(user));
            } else {
                localStorage.removeItem('isAuthenticated');
                localStorage.removeItem('user');
            }
        } catch (_) {
            // Network error — treat as unauthenticated
        }

        if (route.protected && !isAuthenticated) {
            this.navigateTo('/login');
            return;
        }

        // Redirect from login/signup if already authenticated
        if ((path === '/login' || path === '/signup') && isAuthenticated) {
            this.navigateTo('/dashboard');
            return;
        }

        // Render Component
        this.rootElement.innerHTML = '<div class="loader-overlay"><div class="spinner"></div></div>';
        try {
            const html = await route.component();
            this.rootElement.innerHTML = html;
            if (route.onRender) route.onRender();
        } catch (error) {
            console.error('Route error:', error);
            this.rootElement.innerHTML = `<h1>System Error</h1><p>${error.message}</p>`;
        }

        // Update Nav visibility
        const navbar = document.getElementById('main-nav');
        if (route.showNav === false) {
            navbar.classList.add('hidden');
        } else {
            navbar.classList.remove('hidden');
            const userBadge = document.getElementById('nav-user');
            if (userBadge) {
                const user = JSON.parse(localStorage.getItem('user') || '{}');
                userBadge.textContent = user.username || 'Analyst';
            }
        }
    }
}
