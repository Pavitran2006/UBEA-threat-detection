/* 
   CyberGuard UEBA - SPA Components 
   Modular UI components for Login, Signup, and Dashboard
*/

// --- Shared Utilities ---
const getRiskColor = (level) => {
    switch (level) {
        case 'Critical': return '#ef4444';
        case 'High': return '#f97316';
        case 'Medium': return '#eab308';
        case 'Low': return '#4ade80';
        default: return '#94a3b8';
    }
};

const setupValidation = (form, submitBtn) => {
    const validateField = (input, force = false) => {
        const group = input.closest('.form-group');
        if (!group) return;

        let isValid = input.checkValidity();

        // Custom check for confirmation
        if (input.id === 'confirmPassword') {
            const pass = form.querySelector('#password').value;
            if (input.value !== pass) {
                isValid = false;
                input.setCustomValidity('Passwords must match');
            } else {
                input.setCustomValidity('');
            }
        }

        // Only show error if 'dirty' or forced (on blur)
        if (force || group.classList.contains('dirty')) {
            if (!isValid && input.value !== '') {
                group.classList.add('invalid');
            } else {
                group.classList.remove('invalid');
            }
        }

        submitBtn.disabled = !form.checkValidity();
    };

    form.querySelectorAll('input, select').forEach(input => {
        input.addEventListener('blur', () => {
            input.closest('.form-group').classList.add('dirty');
            validateField(input, true);
        });
        input.addEventListener('input', () => validateField(input));
    });

    // Initial check
    submitBtn.disabled = !form.checkValidity();
};

const setupPasswordToggle = (form) => {
    // Password toggle functionality removed
};

// --- Exported Components ---

export const Login = {
    render: () => `
        <div class="auth-container">
            <div class="auth-card">
                <div class="auth-header">
                    <h1>CyberGuard Access</h1>
                    <p>Enter your credentials to access the secure network</p>
                </div>
                <div id="messageBox" class="message"></div>
                <form id="loginForm" novalidate>
                    <div class="form-group" id="usernameGroup">
                        <label for="username">Username / Email</label>
                        <div class="input-wrapper">
                            <input type="text" id="username" name="username" class="auth-input" placeholder="Operator ID" required>
                        </div>
                        <span class="error-text">Please enter your ID.</span>
                    </div>
                    <div class="form-group" id="passwordGroup">
                        <label for="password">Password</label>
                        <div class="input-wrapper">
                            <input type="password" id="password" name="password" class="auth-input" placeholder="••••••••" required>
                        </div>
                        <span class="error-text">Password is required.</span>
                    </div>
                    <div class="form-options">
                        <label class="checkbox-container">
                            <input type="checkbox" id="rememberMe">
                            <span>Remember Me</span>
                        </label>
                        <a href="#" class="btn-link">Forgot Password?</a>
                    </div>
                    <button type="submit" id="submitBtn" class="btn-primary" disabled>
                        <span>Authorize Access</span>
                        <div class="loader"></div>
                    </button>
                </form>
                <div class="auth-footer">
                    New Operator? <button data-link="/signup" class="btn-link">Initialize Registration</button>
                </div>
            </div>
        </div>
    `,
    init: () => {
        const form = document.querySelector('#loginForm');
        const submitBtn = form.querySelector('#submitBtn');
        const messageBox = document.querySelector('#messageBox');

        setupValidation(form, submitBtn);

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            messageBox.style.display = 'none';
            submitBtn.classList.add('loading');
            try {
                const res = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username: form.username.value,
                        password: form.password.value
                    })
                });
                const data = await res.json();
                if (res.ok) {
                    localStorage.setItem('isAuthenticated', 'true');
                    localStorage.setItem('user', JSON.stringify({ username: form.username.value }));
                    window.dispatchEvent(new CustomEvent('authChange'));
                    window.appRouter.navigateTo('/dashboard');
                    window.showToast('Authorization successful. Welcome back!', 'success');
                } else {
                    throw new Error(data.detail || 'Access Denied');
                }
            } catch (err) {
                window.showToast(err.message, 'error');
                submitBtn.classList.remove('loading');
            }
        });
    }
};

export const Signup = {
    render: () => `
        <div class="auth-container">
            <div class="auth-card">
                <div class="auth-header">
                    <h1>Join the Network</h1>
                    <p>Initialize your operator profile to get started</p>
                </div>
                <div id="messageBox" class="message"></div>
                <form id="signupForm" novalidate>
                    <div class="form-group" id="usernameGroup">
                        <label for="username">Username</label>
                        <div class="input-wrapper">
                            <input type="text" id="username" name="username" class="auth-input" placeholder="Operator ID" required minlength="3">
                        </div>
                        <span class="error-text">Username must be at least 3 characters.</span>
                    </div>
                    <div class="form-group" id="emailGroup">
                        <label for="email">Email Address</label>
                        <div class="input-wrapper">
                            <input type="email" id="email" name="email" class="auth-input" placeholder="name@security.com" required>
                        </div>
                        <span class="error-text">Please enter a valid email.</span>
                    </div>
                    <div class="form-group" id="passwordGroup">
                        <label for="password">Password</label>
                        <div class="input-wrapper">
                            <input type="password" id="password" name="password" class="auth-input" placeholder="••••••••" required minlength="8">
                        </div>
                        <div class="strength-meter"><div class="strength-bar"></div></div>
                        <span class="error-text">Minimum 8 characters required.</span>
                    </div>
                    <div class="form-group" id="confirmPasswordGroup">
                        <label for="confirmPassword">Confirm Password</label>
                        <div class="input-wrapper">
                            <input type="password" id="confirmPassword" name="confirmPassword" class="auth-input" placeholder="••••••••" required>
                        </div>
                        <span class="error-text">Passwords must match.</span>
                    </div>
                    <div class="form-group" id="roleGroup">
                        <label for="role">Operator Role</label>
                        <div class="input-wrapper">
                            <select id="role" name="role" class="auth-input" required>
                                <option value="" disabled selected>Select your role</option>
                                <option value="user">Security Analyst (User)</option>
                                <option value="admin">System Administrator (Admin)</option>
                            </select>
                        </div>
                        <span class="error-text">Please select a role.</span>
                    </div>
                    <button type="submit" id="submitBtn" class="btn-primary" disabled>
                        <span>Initialize Registration</span>
                        <div class="loader"></div>
                    </button>
                </form>
                <div class="auth-footer">
                    Already an Operator? <button data-link="/login" class="btn-link">Sign In</button>
                </div>
            </div>
        </div>
    `,
    init: () => {
        const form = document.querySelector('#signupForm');
        const submitBtn = form.querySelector('#submitBtn');
        // const messageBox = document.querySelector('#messageBox'); // Removed as window.showToast is used

        const setupValidation = (form, submitBtn) => {
            const validateField = (input, force = false) => {
                const group = input.closest('.form-group');
                if (!group) return;

                let isValid = input.checkValidity();

                // Custom check for confirmation
                if (input.id === 'confirmPassword') {
                    const pass = form.querySelector('#password').value;
                    if (input.value !== pass) {
                        isValid = false;
                        input.setCustomValidity('Passwords must match');
                    } else {
                        input.setCustomValidity('');
                    }
                }

                // Only show error if 'dirty' or forced (on blur)
                if (force || group.classList.contains('dirty')) {
                    if (!isValid && input.value !== '') {
                        group.classList.add('invalid');
                    } else {
                        group.classList.remove('invalid');
                    }
                }

                submitBtn.disabled = !form.checkValidity();
            };

            form.querySelectorAll('input, select').forEach(input => {
                input.addEventListener('blur', () => {
                    input.closest('.form-group').classList.add('dirty');
                    validateField(input, true);
                });
                input.addEventListener('input', () => {
                    validateField(input);
                    if (input.id === 'password') {
                        const meter = form.querySelector('.strength-meter');
                        const bar = form.querySelector('.strength-bar');
                        meter.classList.add('active');
                        const val = input.value;
                        let strength = 0;
                        if (val.length > 8) strength += 25;
                        if (/[A-Z]/.test(val)) strength += 25;
                        if (/[0-9]/.test(val)) strength += 25;
                        if (/[^A-Za-z0-9]/.test(val)) strength += 25;

                        bar.style.width = strength + '%';
                        bar.style.backgroundColor = strength < 50 ? '#ef4444' : strength < 100 ? '#eab308' : '#4ade80';
                    }
                    submitBtn.disabled = !form.checkValidity();
                });
            });

            // Initial check
            submitBtn.disabled = !form.checkValidity();
        };

        setupValidation(form, submitBtn);

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            // messageBox.style.display = 'none'; // Removed as window.showToast is used
            submitBtn.classList.add('loading');
            const formData = {
                username: form.username.value,
                email: form.email.value,
                password: form.password.value,
                confirmPassword: form.confirmPassword.value,
                role: form.role.value
            };

            try {
                const res = await fetch('/api/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });
                const data = await res.json();
                if (res.ok) {
                    window.showToast('Registration successful! Redirecting...', 'success');

                    // Automatic login
                    localStorage.setItem('isAuthenticated', 'true');
                    localStorage.setItem('user', JSON.stringify({ username: formData.username }));
                    window.dispatchEvent(new CustomEvent('authChange'));
                    setTimeout(() => window.appRouter.navigateTo('/dashboard'), 1500);
                } else {
                    throw new Error(data.detail || 'Registration Failed');
                }
            } catch (err) {
                window.showToast(err.message, 'error');
                submitBtn.classList.remove('loading');
            }
        });
    }
};

export const Dashboard = {
    render: () => `
        <div class="dashboard-container">
            <header class="dash-header">
                <h1>Enterprise Monitoring</h1>
                <p>User and Entity Behaviour Analytics for Internal Threat Identification</p>
            </header>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="count-users">0</div>
                    <p class="stat-label">Total Users</p>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="count-signals">0</div>
                    <p class="stat-label">Active Signals</p>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="count-alerts">0</div>
                    <p class="stat-label">Threat Alerts</p>
                </div>
            </div>

            <section class="data-section">
                <h2>Real-time User Risk Monitoring</h2>
                <div class="table-wrapper">
                    <table class="data-table">
                        <thead>
                            <tr><th>User</th><th>Risk Score</th><th>Classification</th><th>Status</th></tr>
                        </thead>
                        <tbody id="risk-table-body"></tbody>
                    </table>
                </div>
            </section>

            <section class="data-section">
                <h2 class="alert-title">Threat Intelligence & Feedback Loop</h2>
                <div class="table-wrapper">
                    <table class="data-table">
                        <thead>
                            <tr><th>Time</th><th>User</th><th>Score</th><th>Level</th><th>Status</th><th>Action</th></tr>
                        </thead>
                        <tbody id="alerts-table-body"></tbody>
                    </table>
                </div>
            </section>
        </div>
    `,
    init: () => {
        const fetchStats = async () => {
            try {
                const [statsRes, riskRes] = await Promise.all([
                    fetch('/api/dashboard/stats'),
                    fetch('/api/risk/user-risk')
                ]);
                if (statsRes.ok && riskRes.ok) {
                    const stats = await statsRes.json();
                    document.querySelector('#count-users').textContent = stats.users;
                    document.querySelector('#count-signals').textContent = stats.signals;
                    document.querySelector('#count-alerts').textContent = stats.alerts;

                    const riskData = await riskRes.json();
                    const riskBody = document.querySelector('#risk-table-body');
                    if (riskBody) {
                        riskBody.innerHTML = riskData.map(u => `
                            <tr>
                                <td>${u.username}</td>
                                <td style="color: ${getRiskColor(u.risk_level)}; font-weight: bold;">${u.risk_score}</td>
                                <td><span class="badge" style="background: ${getRiskColor(u.risk_level)}20; color: ${getRiskColor(u.risk_level)}">${u.risk_level}</span></td>
                                <td class="dim-text">${u.risk_score > 60 ? 'MANDATORY AUDIT' : 'Monitoring'}</td>
                            </tr>
                        `).join('');
                    }
                }
            } catch (err) { console.error('Stats fetch error:', err); }
        };

        const fetchAlerts = async () => {
            try {
                const res = await fetch('/api/dashboard/alerts');
                if (res.ok) {
                    const alerts = await res.json();
                    const alertBody = document.querySelector('#alerts-table-body');
                    if (alertBody) {
                        alertBody.innerHTML = alerts.map(a => `
                            <tr>
                                <td class="dim-text">${a.time}</td>
                                <td>${a.username}</td>
                                <td class="mono">${a.score}</td>
                                <td style="color: ${getRiskColor(a.level)}">${a.level}</td>
                                <td><span class="status-text ${a.status.toLowerCase()}">${a.status.toUpperCase()}</span></td>
                                <td>
                                    ${a.status === 'pending' ? `
                                        <div class="action-btns">
                                            <button class="btn-mini threat" onclick="window.submitFeedback(${a.id}, 'confirmed')">THREAT</button>
                                            <button class="btn-mini safe" onclick="window.submitFeedback(${a.id}, 'false_positive')">SAFE</button>
                                        </div>
                                    ` : '---'}
                                </td>
                            </tr>
                        `).join('');
                    }
                }
            } catch (err) { console.error('Alerts fetch error:', err); }
        };

        window.submitFeedback = async (id, status) => {
            await fetch('/api/ml/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ alert_id: id, status: status })
            });
            fetchAlerts();
            fetchStats();
        };

        fetchStats();
        fetchAlerts();
        const interval = setInterval(() => {
            if (!document.querySelector('#count-users')) {
                clearInterval(interval);
                return;
            }
            fetchStats();
            fetchAlerts();
        }, 10000);
    }
};
