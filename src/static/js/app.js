class UwaMarketplaceApp {
    constructor() {
        this.currentUser = null;
        this.currentPage = 'home';
        this.constants = {
            categories: [],
            conditions: [],
            allowed_email_domain: '@student.uwa.edu.au',
            chat_enabled: false,
        };
        this.currentItem = null;
        this.activeConversationId = null;
        this.chatPoller = null;
        this.csrfToken = this.readCsrfToken();
    }

    async init() {
        await this.loadConstants();
        await this.checkAuthStatus();

        window.addEventListener('hashchange', () => {
            this.loadRouteFromHash();
        });

        this.loadRouteFromHash();
    }

    readCsrfToken() {
        return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    }

    setCsrfToken(token) {
        if (!token) {
            return;
        }

        this.csrfToken = token;
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) {
            meta.setAttribute('content', token);
        }
    }

    stopConversationPolling() {
        if (this.chatPoller) {
            window.clearInterval(this.chatPoller);
            this.chatPoller = null;
        }
    }

    async request(url, options = {}) {
        const config = {
            method: options.method || 'GET',
            headers: {
                'Accept': 'application/json',
                ...(options.headers || {}),
            },
            credentials: 'same-origin',
        };

        if (options.body !== undefined) {
            config.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
            config.headers['Content-Type'] = config.headers['Content-Type'] || 'application/json';
        }

        if (config.method !== 'GET') {
            config.headers['X-CSRF-Token'] = this.csrfToken;
        }

        const response = await fetch(url, config);
        let data = {};

        try {
            data = await response.json();
        } catch (error) {
            data = {
                success: false,
                error: 'Unexpected response from server',
            };
        }

        if (data.csrf_token) {
            this.setCsrfToken(data.csrf_token);
        }

        data.http_status = response.status;
        return data;
    }

    async loadConstants() {
        const data = await this.request('/api/constants');
        if (data.success) {
            this.constants = data.constants;
        }
    }

    async checkAuthStatus() {
        const data = await this.request('/api/auth/current-user');
        if (data.success) {
            this.currentUser = data.user;
            this.updateNavigation();
        }
    }

    updateNavigation() {
        const authNav = document.getElementById('authNav');
        if (!authNav) {
            return;
        }

        if (this.currentUser) {
            authNav.innerHTML = `
                <a href="#" onclick="app.navigateTo('dashboard'); return false;">${this.escapeHtml(this.currentUser.username)}</a>
                <a href="#" onclick="app.navigateTo('sell'); return false;" class="btn-sell">Sell</a>
                <a href="#" onclick="app.handleLogout(); return false;">Logout</a>
            `;
            return;
        }

        authNav.innerHTML = `
            <a href="#" onclick="app.navigateTo('login'); return false;">Login</a>
            <a href="#" onclick="app.navigateTo('register'); return false;">Register</a>
        `;
    }

    buildHash(page, params = {}) {
        const query = new URLSearchParams();

        switch (page) {
            case 'browse':
                if (params.category) {
                    query.set('category', params.category);
                }
                if (params.search) {
                    query.set('search', params.search);
                }
                return `#/browse${query.toString() ? `?${query.toString()}` : ''}`;
            case 'login':
                return '#/login';
            case 'register':
                return '#/register';
            case 'sell':
                return '#/sell';
            case 'dashboard':
                return '#/dashboard';
            case 'item-detail':
                return `#/item/${params.itemId}`;
            default:
                return '#/';
        }
    }

    parseHash() {
        const raw = window.location.hash.replace(/^#/, '') || '/';
        const [pathPart, queryString = ''] = raw.split('?');
        const path = pathPart || '/';
        const segments = path.split('/').filter(Boolean);
        const query = new URLSearchParams(queryString);

        if (segments[0] === 'browse') {
            return {
                page: 'browse',
                params: {
                    category: query.get('category') || '',
                    search: query.get('search') || '',
                },
            };
        }

        if (segments[0] === 'login') {
            return { page: 'login', params: {} };
        }

        if (segments[0] === 'register') {
            return { page: 'register', params: {} };
        }

        if (segments[0] === 'sell') {
            return { page: 'sell', params: {} };
        }

        if (segments[0] === 'dashboard') {
            return { page: 'dashboard', params: {} };
        }

        if (segments[0] === 'item' && segments[1]) {
            return {
                page: 'item-detail',
                params: {
                    itemId: Number(segments[1]),
                },
            };
        }

        return { page: 'home', params: {} };
    }

    navigateTo(page, params = {}) {
        const targetHash = this.buildHash(page, params);
        if (window.location.hash === targetHash) {
            this.loadRouteFromHash();
            return;
        }
        window.location.hash = targetHash;
    }

    async loadRouteFromHash() {
        const { page, params } = this.parseHash();
        this.currentPage = page;
        this.stopConversationPolling();

        if ((page === 'sell' || page === 'dashboard') && !this.currentUser) {
            this.navigateTo('login');
            return;
        }

        switch (page) {
            case 'browse':
                await this.renderBrowse(params);
                break;
            case 'login':
                this.renderLogin();
                break;
            case 'register':
                this.renderRegister();
                break;
            case 'sell':
                this.renderSell();
                break;
            case 'dashboard':
                await this.renderDashboard();
                break;
            case 'item-detail':
                await this.renderItemDetail(params.itemId);
                break;
            default:
                await this.renderHome();
                break;
        }

        window.scrollTo(0, 0);
    }

    renderShell(html) {
        const root = document.getElementById('app-content');
        if (root) {
            root.innerHTML = html;
        }
    }

    renderMetricCards(reputation) {
        return `
            <div class="metric-grid">
                <div class="metric-card">
                    <span class="metric-value">${reputation.score.toFixed(1)}</span>
                    <span class="metric-label">Reputation</span>
                </div>
                <div class="metric-card">
                    <span class="metric-value">${reputation.completed_sales}</span>
                    <span class="metric-label">Sales</span>
                </div>
                <div class="metric-card">
                    <span class="metric-value">${reputation.completed_purchases}</span>
                    <span class="metric-label">Purchases</span>
                </div>
            </div>
        `;
    }

    renderUserBadge(user) {
        const verified = user.is_uwa_verified
            ? '<span class="campus-pill">Verified UWA student</span>'
            : '<span class="campus-pill pending">Verification pending</span>';
        return `${verified}<span class="rating-pill">${this.escapeHtml(user.reputation.label)} · ${user.reputation.score.toFixed(1)}</span>`;
    }

    renderItemCard(item) {
        return `
            <article class="item-card" onclick="app.navigateTo('item-detail', { itemId: ${item.id} })">
                <div class="item-image">
                    <div class="placeholder">${this.escapeHtml(item.category.slice(0, 3).toUpperCase())}</div>
                </div>
                <div class="item-content">
                    <h3>${this.escapeHtml(item.title)}</h3>
                    <div class="item-tags">
                        <span class="item-category">${this.escapeHtml(item.category)}</span>
                        <span class="item-condition">${this.escapeHtml(item.condition)}</span>
                    </div>
                    <p class="item-seller">Seller: ${this.escapeHtml(item.seller.full_name || item.seller.username)}</p>
                    <div class="item-badges">${this.renderUserBadge(item.seller)}</div>
                    <div class="item-footer">
                        <span class="price">$${item.price.toFixed(2)}</span>
                        <span class="status ${item.is_sold ? 'status-sold' : ''}">${item.is_sold ? 'Sold' : 'Available'}</span>
                    </div>
                </div>
            </article>
        `;
    }

    async renderHome() {
        const data = await this.request('/api/items?limit=6');
        const items = data.success ? data.items : [];

        this.renderShell(`
            <section class="hero hero-campus">
                <div class="hero-copy">
                    <span class="hero-kicker">Exclusive to the UWA campus community</span>
                    <h1>Buy, sell, and message other UWA students in one place.</h1>
                    <p>List textbooks, furniture, electronics, and moving-out essentials with verified student accounts and built-in chat.</p>
                    <div class="hero-actions">
                        <button class="btn btn-primary" onclick="app.navigateTo('browse')">Browse listings</button>
                        ${this.currentUser
                            ? '<button class="btn btn-secondary" onclick="app.navigateTo(\'sell\')">Post an item</button>'
                            : '<button class="btn btn-secondary" onclick="app.navigateTo(\'register\')">Create UWA account</button>'}
                    </div>
                </div>
                <div class="hero-panel">
                    <h3>Why this concept fits the assignment</h3>
                    <ul class="hero-points">
                        <li>Client-server SPA with Flask and AJAX.</li>
                        <li>Persistent users, listings, transactions, and messages.</li>
                        <li>Students can browse data created by other students.</li>
                        <li>Campus-only onboarding through UWA student email verification.</li>
                    </ul>
                </div>
            </section>

            <section class="section">
                <div class="section-heading">
                    <h2>Campus trust model</h2>
                    <p>Every account is validated against ${this.escapeHtml(this.constants.allowed_email_domain)} before it can join the marketplace.</p>
                </div>
                <div class="info-banner">
                    <div>
                        <strong>Real-time chat:</strong> buyers and sellers can message inside each listing and keep the conversation on campus.
                    </div>
                    <div>
                        <strong>Reputation:</strong> every completed sale and purchase contributes to a visible trader score.
                    </div>
                </div>
            </section>

            <section class="section">
                <div class="section-heading">
                    <h2>Latest listings</h2>
                    <p>${items.length ? 'Fresh listings from the current database.' : 'No listings yet. Create the first UWA campus listing.'}</p>
                </div>
                <div class="items-grid">
                    ${items.map((item) => this.renderItemCard(item)).join('')}
                </div>
            </section>
        `);
    }

    async renderBrowse(params = {}) {
        const category = params.category || '';
        const search = params.search || '';
        const query = new URLSearchParams({ limit: '24' });

        if (category) {
            query.set('category', category);
        }
        if (search) {
            query.set('search', search);
        }

        const data = await this.request(`/api/items?${query.toString()}`);
        const items = data.success ? data.items : [];

        this.renderShell(`
            <section class="browse-container">
                <aside class="filters">
                    <h3>Campus filters</h3>
                    <p class="panel-text">Find what other UWA students are selling right now.</p>
                    <div class="search-box">
                        <input type="text" id="searchInput" placeholder="Search listings..." value="${this.escapeHtml(search)}">
                        <button onclick="app.performSearch()">Search</button>
                    </div>
                    <h4>Categories</h4>
                    <div class="category-list">
                        <button class="category-btn ${!category ? 'active' : ''}" onclick="app.filterByCategory('')">All listings</button>
                        ${this.constants.categories.map((name) => `
                            <button class="category-btn ${category === name ? 'active' : ''}" onclick="app.filterByCategory('${this.escapeForSingleQuote(name)}')">${this.escapeHtml(name)}</button>
                        `).join('')}
                    </div>
                </aside>

                <section class="items-section">
                    <div class="section-heading">
                        <h2>${category ? `${this.escapeHtml(category)} listings` : 'All active listings'}</h2>
                        <p>${data.success ? `${data.total} results on the campus marketplace.` : 'Listings could not be loaded.'}</p>
                    </div>
                    <div class="items-grid">
                        ${items.length
                            ? items.map((item) => this.renderItemCard(item)).join('')
                            : '<div class="empty-state">No listings matched this search yet.</div>'}
                    </div>
                </section>
            </section>
        `);

        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('keypress', (event) => {
                if (event.key === 'Enter') {
                    this.performSearch();
                }
            });
        }
    }

    performSearch() {
        const search = document.getElementById('searchInput')?.value.trim() || '';
        const { params } = this.parseHash();
        this.navigateTo('browse', {
            category: params.category || '',
            search,
        });
    }

    filterByCategory(category) {
        const { params } = this.parseHash();
        this.navigateTo('browse', {
            category,
            search: params.search || '',
        });
    }

    renderConversationMessages(conversation) {
        if (!conversation || !conversation.messages || !conversation.messages.length) {
            return '<div class="empty-state compact">No messages yet. Start the conversation.</div>';
        }

        return `
            <div class="message-thread">
                ${conversation.messages.map((message) => `
                    <div class="message-bubble ${message.sender.id === this.currentUser?.id ? 'mine' : 'theirs'}">
                        <div class="message-author">${this.escapeHtml(message.sender.full_name || message.sender.username)}</div>
                        <div class="message-body">${this.escapeHtml(message.body)}</div>
                        <div class="message-time">${new Date(message.created_at).toLocaleString()}</div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    renderItemConversationPanel(item, conversation) {
        if (!this.currentUser) {
            return `
                <div class="chat-card">
                    <h3>Campus chat</h3>
                    <p class="panel-text">Login with your UWA student account to message this seller.</p>
                    <button class="btn btn-primary" onclick="app.navigateTo('login')">Login to chat</button>
                </div>
            `;
        }

        if (this.currentUser.id === item.seller.id) {
            return `
                <div class="chat-card">
                    <h3>Campus chat</h3>
                    <p class="panel-text">This is your own listing. Open the dashboard inbox to reply to buyers.</p>
                    <button class="btn btn-secondary" onclick="app.navigateTo('dashboard')">Open inbox</button>
                </div>
            `;
        }

        if (!conversation) {
            return `
                <div class="chat-card">
                    <h3>Message the seller</h3>
                    <p class="panel-text">Only verified UWA student accounts can access chat. Introduce yourself and ask about pick-up on campus.</p>
                    <form onsubmit="return app.startConversation(event, ${item.id})" class="chat-form">
                        <textarea name="message" rows="4" placeholder="Hi, is this still available? I can meet on campus this week." required></textarea>
                        <button type="submit" class="btn btn-primary">Start chat</button>
                    </form>
                </div>
            `;
        }

        return `
            <div class="chat-card">
                <div class="chat-header">
                    <div>
                        <h3>Chat with ${this.escapeHtml(conversation.counterpart.full_name || conversation.counterpart.username)}</h3>
                        <p class="panel-text">${this.renderUserBadge(conversation.counterpart)}</p>
                    </div>
                    <div class="chat-status">Live via AJAX polling</div>
                </div>
                ${this.renderConversationMessages(conversation)}
                <form onsubmit="return app.sendConversationMessage(event, ${conversation.id}, 'item', ${item.id})" class="chat-form">
                    <textarea name="message" rows="3" placeholder="Send a message..." required></textarea>
                    <button type="submit" class="btn btn-primary">Send</button>
                </form>
            </div>
        `;
    }

    async renderItemDetail(itemId) {
        const data = await this.request(`/api/items/${itemId}`);
        if (!data.success) {
            this.renderShell('<div class="empty-state">This listing could not be loaded.</div>');
            return;
        }

        this.currentItem = data.item;
        let conversation = null;

        if (this.currentUser) {
            const conversationData = await this.request(`/api/items/${itemId}/conversation`);
            if (conversationData.success && conversationData.mode === 'buyer') {
                conversation = conversationData.conversation;
                if (conversation) {
                    this.startItemConversationPolling(itemId);
                }
            }
        }

        const item = data.item;
        const canBuy = this.currentUser && this.currentUser.id !== item.seller.id && !item.is_sold;

        this.renderShell(`
            <section class="item-detail-container">
                <div class="item-image-section">
                    <div class="item-image-large">${this.escapeHtml(item.category.slice(0, 3).toUpperCase())}</div>
                </div>
                <div class="item-info-section">
                    <h1>${this.escapeHtml(item.title)}</h1>
                    <div class="item-meta">
                        <span class="badge">${this.escapeHtml(item.category)}</span>
                        <span class="badge">${this.escapeHtml(item.condition)}</span>
                        <span class="badge ${item.is_sold ? 'sold' : 'available'}">${item.is_sold ? 'Sold' : 'Available'}</span>
                    </div>

                    <div class="seller-card">
                        <h3>Seller profile</h3>
                        <p><strong>${this.escapeHtml(item.seller.full_name || item.seller.username)}</strong></p>
                        <p>@${this.escapeHtml(item.seller.username)}</p>
                        <div class="item-badges">${this.renderUserBadge(item.seller)}</div>
                        <p class="seller-bio">${this.escapeHtml(item.seller.bio || 'No profile bio yet.')}</p>
                        ${this.renderMetricCards(item.seller.reputation)}
                    </div>

                    <div class="pricing-section">
                        <h2>$${item.price.toFixed(2)}</h2>
                        ${canBuy
                            ? `<button class="btn btn-primary" onclick="app.handlePurchase(${item.id})">Buy now</button>`
                            : `<p class="sold-text">${item.is_sold ? 'This listing has already been sold.' : 'This is your own listing.'}</p>`}
                        <button class="btn btn-secondary" onclick="app.navigateTo('browse')">Back to browse</button>
                    </div>
                </div>
            </section>

            <section class="item-description-section">
                <h2>Description</h2>
                <p>${this.escapeHtml(item.description)}</p>
                <p class="date-posted">Posted on ${new Date(item.created_at).toLocaleDateString()}</p>
            </section>

            <section id="itemConversationPanel">
                ${this.renderItemConversationPanel(item, conversation)}
            </section>
        `);
    }

    async refreshItemConversation(itemId) {
        if (this.currentPage !== 'item-detail' || Number(this.currentItem?.id) !== Number(itemId)) {
            this.stopConversationPolling();
            return;
        }

        const data = await this.request(`/api/items/${itemId}/conversation`);
        if (!data.success || data.mode !== 'buyer') {
            return;
        }

        const panel = document.getElementById('itemConversationPanel');
        if (panel) {
            panel.innerHTML = this.renderItemConversationPanel(this.currentItem, data.conversation);
        }
    }

    startItemConversationPolling(itemId) {
        this.stopConversationPolling();
        this.chatPoller = window.setInterval(() => {
            this.refreshItemConversation(itemId);
        }, 5000);
    }

    async startConversation(event, itemId) {
        event.preventDefault();
        const form = event.target;
        const message = form.querySelector('textarea[name="message"]')?.value.trim() || '';

        if (!message) {
            this.showError('Message cannot be empty.');
            return false;
        }

        const data = await this.request(`/api/items/${itemId}/conversations`, {
            method: 'POST',
            body: { message },
        });

        if (!data.success) {
            this.showError(data.error || 'Could not start the conversation.');
            return false;
        }

        this.showSuccess('Chat started.');
        await this.renderItemDetail(itemId);
        return false;
    }

    async sendConversationMessage(event, conversationId, context, itemId = null) {
        event.preventDefault();
        const form = event.target;
        const message = form.querySelector('textarea[name="message"]')?.value.trim() || '';

        if (!message) {
            this.showError('Message cannot be empty.');
            return false;
        }

        const data = await this.request(`/api/conversations/${conversationId}/messages`, {
            method: 'POST',
            body: { message },
        });

        if (!data.success) {
            this.showError(data.error || 'Message could not be sent.');
            return false;
        }

        form.reset();
        this.showSuccess('Message sent.');

        if (context === 'item' && itemId) {
            const panel = document.getElementById('itemConversationPanel');
            if (panel) {
                panel.innerHTML = this.renderItemConversationPanel(this.currentItem, data.conversation);
            }
            this.startItemConversationPolling(itemId);
        } else if (context === 'dashboard') {
            this.activeConversationId = conversationId;
            const panel = document.getElementById('dashboardConversationPanel');
            if (panel) {
                panel.innerHTML = this.renderDashboardConversationPanel(data.conversation);
            }
            this.startDashboardConversationPolling(conversationId);
        }

        return false;
    }

    renderLogin() {
        this.renderShell(`
            <section class="auth-container">
                <div class="auth-card">
                    <h1>Login</h1>
                    <p class="panel-text">Use the account you created with your UWA student email.</p>
                    <form onsubmit="return app.handleLogin(event)">
                        <div class="form-group">
                            <label for="loginUsername">Username</label>
                            <input type="text" id="loginUsername" name="username" required>
                        </div>
                        <div class="form-group">
                            <label for="loginPassword">Password</label>
                            <input type="password" id="loginPassword" name="password" required>
                        </div>
                        <button type="submit" class="btn btn-primary">Login</button>
                    </form>
                    <p class="auth-link">
                        Need an account? <a href="#" onclick="app.navigateTo('register'); return false;">Register with your UWA email</a>
                    </p>
                    <div id="loginError" class="error-message" style="display:none;"></div>
                </div>
            </section>
        `);
    }

    async handleLogin(event) {
        event.preventDefault();

        const username = document.getElementById('loginUsername')?.value.trim() || '';
        const password = document.getElementById('loginPassword')?.value || '';
        const data = await this.request('/api/auth/login', {
            method: 'POST',
            body: { username, password },
        });

        if (!data.success) {
            this.showInlineError('loginError', data.error || 'Login failed.');
            return false;
        }

        this.currentUser = data.user;
        this.updateNavigation();
        this.showSuccess('Logged in successfully.');
        this.navigateTo('dashboard');
        return false;
    }

    renderRegister() {
        this.renderShell(`
            <section class="auth-container">
                <div class="auth-card auth-card-wide">
                    <h1>Create your UWA account</h1>
                    <p class="panel-text">Registration is restricted to ${this.escapeHtml(this.constants.allowed_email_domain)} addresses so only UWA students can join.</p>
                    <form onsubmit="return app.handleRegister(event)">
                        <div class="form-group">
                            <label for="registerFullName">Full name</label>
                            <input type="text" id="registerFullName" name="fullName" required>
                        </div>
                        <div class="form-group">
                            <label for="registerUsername">Username</label>
                            <input type="text" id="registerUsername" name="username" required>
                        </div>
                        <div class="form-group">
                            <label for="registerEmail">UWA student email</label>
                            <input type="email" id="registerEmail" name="email" placeholder="name@student.uwa.edu.au" required>
                        </div>
                        <div class="form-group">
                            <label for="registerPassword">Password</label>
                            <input type="password" id="registerPassword" name="password" minlength="6" required>
                        </div>
                        <button type="submit" class="btn btn-primary">Register</button>
                    </form>
                    <div id="registerError" class="error-message" style="display:none;"></div>
                </div>
            </section>
        `);
    }

    async handleRegister(event) {
        event.preventDefault();

        const fullName = document.getElementById('registerFullName')?.value.trim() || '';
        const username = document.getElementById('registerUsername')?.value.trim() || '';
        const email = document.getElementById('registerEmail')?.value.trim().toLowerCase() || '';
        const password = document.getElementById('registerPassword')?.value || '';

        if (!email.endsWith(this.constants.allowed_email_domain)) {
            this.showInlineError('registerError', `Use your ${this.constants.allowed_email_domain} email to register.`);
            return false;
        }

        const data = await this.request('/api/auth/register', {
            method: 'POST',
            body: {
                full_name: fullName,
                username,
                email,
                password,
            },
        });

        if (!data.success) {
            this.showInlineError('registerError', data.error || 'Registration failed.');
            return false;
        }

        this.showSuccess('Registration successful. Please login.');
        this.navigateTo('login');
        return false;
    }

    renderSell() {
        this.renderShell(`
            <section class="form-container">
                <h1>List a new item</h1>
                <p class="panel-text">Keep descriptions practical so buyers know condition, pick-up area, and timing.</p>
                <form onsubmit="return app.handleSellItem(event)">
                    <div class="form-group">
                        <label for="itemTitle">Title</label>
                        <input type="text" id="itemTitle" name="title" minlength="4" required>
                    </div>
                    <div class="form-group">
                        <label for="itemDescription">Description</label>
                        <textarea id="itemDescription" name="description" rows="6" minlength="15" required></textarea>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="itemPrice">Price (AUD)</label>
                            <input type="number" id="itemPrice" name="price" min="0.01" step="0.01" required>
                        </div>
                        <div class="form-group">
                            <label for="itemCategory">Category</label>
                            <select id="itemCategory" name="category" required>
                                <option value="">Select category</option>
                                ${this.constants.categories.map((category) => `<option value="${this.escapeHtml(category)}">${this.escapeHtml(category)}</option>`).join('')}
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="itemCondition">Condition</label>
                            <select id="itemCondition" name="condition" required>
                                <option value="">Select condition</option>
                                ${this.constants.conditions.map((condition) => `<option value="${this.escapeHtml(condition)}">${this.escapeHtml(condition)}</option>`).join('')}
                            </select>
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary">Publish listing</button>
                </form>
                <div id="sellError" class="error-message" style="display:none;"></div>
            </section>
        `);
    }

    async handleSellItem(event) {
        event.preventDefault();

        const title = document.getElementById('itemTitle')?.value.trim() || '';
        const description = document.getElementById('itemDescription')?.value.trim() || '';
        const price = document.getElementById('itemPrice')?.value || '';
        const category = document.getElementById('itemCategory')?.value || '';
        const condition = document.getElementById('itemCondition')?.value || '';

        const data = await this.request('/api/items', {
            method: 'POST',
            body: {
                title,
                description,
                price,
                category,
                condition,
            },
        });

        if (!data.success) {
            this.showInlineError('sellError', data.error || 'Listing failed.');
            return false;
        }

        this.showSuccess('Item listed successfully.');
        this.navigateTo('item-detail', { itemId: data.item.id });
        return false;
    }

    renderDashboardConversationPanel(conversation) {
        if (!conversation) {
            return '<div class="empty-state">Open a conversation to view messages.</div>';
        }

        return `
            <div class="chat-card">
                <div class="chat-header">
                    <div>
                        <h3>${this.escapeHtml(conversation.item.title)}</h3>
                        <p class="panel-text">Conversation with ${this.escapeHtml(conversation.counterpart.full_name || conversation.counterpart.username)}</p>
                    </div>
                    <div class="chat-status">${conversation.item.is_sold ? 'Listing sold' : 'Listing active'}</div>
                </div>
                ${this.renderConversationMessages(conversation)}
                <form onsubmit="return app.sendConversationMessage(event, ${conversation.id}, 'dashboard')" class="chat-form">
                    <textarea name="message" rows="3" placeholder="Reply to this conversation..." required></textarea>
                    <button type="submit" class="btn btn-primary">Send reply</button>
                </form>
            </div>
        `;
    }

    async renderDashboard() {
        const [dashboardData, conversationsData] = await Promise.all([
            this.request('/api/dashboard'),
            this.request('/api/conversations'),
        ]);

        if (!dashboardData.success) {
            this.renderShell('<div class="empty-state">Dashboard data could not be loaded.</div>');
            return;
        }

        const dashboard = dashboardData.dashboard;
        const conversations = conversationsData.success ? conversationsData.conversations : [];

        if (!this.activeConversationId && conversations.length) {
            this.activeConversationId = conversations[0].id;
        }

        const activeConversation = conversations.find((conversation) => conversation.id === this.activeConversationId) || conversations[0] || null;

        this.renderShell(`
            <section class="dashboard-container">
                <div class="dashboard-hero">
                    <div>
                        <h1>${this.escapeHtml(dashboard.user.full_name)}</h1>
                        <p class="panel-text">${this.escapeHtml(dashboard.user.email)}</p>
                        <div class="item-badges">${this.renderUserBadge(dashboard.user)}</div>
                    </div>
                    <div class="dashboard-actions">
                        <button class="btn btn-primary" onclick="app.navigateTo('sell')">Post a new item</button>
                        <button class="btn btn-secondary" onclick="app.navigateTo('browse')">Browse market</button>
                    </div>
                </div>

                ${this.renderMetricCards(dashboard.user.reputation)}

                <div class="dashboard-grid">
                    <section class="dashboard-section">
                        <h2>My listings (${dashboard.listings.length})</h2>
                        ${dashboard.listings.length
                            ? `
                                <div class="dashboard-list">
                                    ${dashboard.listings.map((item) => `
                                        <div class="dashboard-card">
                                            <div>
                                                <strong>${this.escapeHtml(item.title)}</strong>
                                                <p>${this.escapeHtml(item.description_preview)}</p>
                                            </div>
                                            <div class="dashboard-card-meta">
                                                <span>$${item.price.toFixed(2)}</span>
                                                <span>${item.is_sold ? 'Sold' : 'Active'}</span>
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            `
                            : '<div class="empty-state compact">You have not posted any listings yet.</div>'}
                    </section>

                    <section class="dashboard-section">
                        <h2>Purchases (${dashboard.purchases.length})</h2>
                        ${dashboard.purchases.length
                            ? `
                                <div class="dashboard-list">
                                    ${dashboard.purchases.map((purchase) => `
                                        <div class="dashboard-card">
                                            <div>
                                                <strong>${this.escapeHtml(purchase.item.title)}</strong>
                                                <p>Seller: ${this.escapeHtml(purchase.seller.full_name || purchase.seller.username)}</p>
                                            </div>
                                            <div class="dashboard-card-meta">
                                                <span>$${purchase.item.price.toFixed(2)}</span>
                                                <span>${this.escapeHtml(purchase.status)}</span>
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            `
                            : '<div class="empty-state compact">No purchases yet.</div>'}
                    </section>

                    <section class="dashboard-section">
                        <h2>Sales (${dashboard.sales.length})</h2>
                        ${dashboard.sales.length
                            ? `
                                <div class="dashboard-list">
                                    ${dashboard.sales.map((sale) => `
                                        <div class="dashboard-card">
                                            <div>
                                                <strong>${this.escapeHtml(sale.item.title)}</strong>
                                                <p>Buyer: ${this.escapeHtml(sale.buyer.full_name || sale.buyer.username)}</p>
                                            </div>
                                            <div class="dashboard-card-meta">
                                                <span>$${sale.item.price.toFixed(2)}</span>
                                                <span>${this.escapeHtml(sale.status)}</span>
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            `
                            : '<div class="empty-state compact">No sales yet.</div>'}
                    </section>
                </div>

                <section class="dashboard-section">
                    <div class="section-heading">
                        <h2>Live inbox</h2>
                        <p>Use this to coordinate pick-up, negotiate timing, and confirm campus meet-ups.</p>
                    </div>
                    <div class="conversation-layout">
                        <aside class="conversation-list">
                            ${conversations.length
                                ? conversations.map((conversation) => `
                                    <button class="conversation-item ${conversation.id === activeConversation?.id ? 'active' : ''}" onclick="app.openConversation(${conversation.id})">
                                        <div>
                                            <strong>${this.escapeHtml(conversation.item.title)}</strong>
                                            <p>${this.escapeHtml(conversation.counterpart.full_name || conversation.counterpart.username)}</p>
                                        </div>
                                        <span>${conversation.message_count} msg</span>
                                    </button>
                                `).join('')
                                : '<div class="empty-state compact">No conversations yet. Message a seller from any listing.</div>'}
                        </aside>
                        <div id="dashboardConversationPanel">
                            ${this.renderDashboardConversationPanel(activeConversation)}
                        </div>
                    </div>
                </section>
            </section>
        `);

        if (activeConversation) {
            this.startDashboardConversationPolling(activeConversation.id);
        }
    }

    openConversation(conversationId) {
        this.activeConversationId = conversationId;
        this.renderDashboard();
    }

    async refreshDashboardConversation(conversationId) {
        if (this.currentPage !== 'dashboard' || this.activeConversationId !== conversationId) {
            this.stopConversationPolling();
            return;
        }

        const data = await this.request(`/api/conversations/${conversationId}`);
        if (!data.success) {
            return;
        }

        const panel = document.getElementById('dashboardConversationPanel');
        if (panel) {
            panel.innerHTML = this.renderDashboardConversationPanel(data.conversation);
        }
    }

    startDashboardConversationPolling(conversationId) {
        this.stopConversationPolling();
        this.chatPoller = window.setInterval(() => {
            this.refreshDashboardConversation(conversationId);
        }, 5000);
    }

    async handlePurchase(itemId) {
        if (!window.confirm('Confirm purchase for this item?')) {
            return;
        }

        const data = await this.request(`/api/purchase/${itemId}`, {
            method: 'POST',
            body: {},
        });

        if (!data.success) {
            this.showError(data.error || 'Purchase failed.');
            return;
        }

        this.showSuccess('Purchase completed successfully.');
        this.navigateTo('dashboard');
    }

    async handleLogout() {
        const data = await this.request('/api/auth/logout', {
            method: 'POST',
            body: {},
        });

        if (!data.success) {
            this.showError(data.error || 'Logout failed.');
            return;
        }

        this.currentUser = null;
        this.activeConversationId = null;
        this.updateNavigation();
        this.showSuccess('Logged out.');
        this.navigateTo('login');
    }

    showInlineError(elementId, message) {
        const element = document.getElementById(elementId);
        if (!element) {
            this.showError(message);
            return;
        }

        element.textContent = message;
        element.style.display = 'block';
    }

    showError(message) {
        this.showNotification(message, 'error');
    }

    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    showNotification(message, type) {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        document.body.appendChild(notification);

        window.setTimeout(() => {
            notification.remove();
        }, 3500);
    }

    escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, (character) => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;',
        }[character]));
    }

    escapeForSingleQuote(value) {
        return String(value ?? '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    }
}


let app;
document.addEventListener('DOMContentLoaded', async () => {
    app = new UwaMarketplaceApp();
    await app.init();
});
