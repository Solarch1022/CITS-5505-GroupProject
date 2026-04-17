// SecondHand Market - Single Page Application
// Client-Server Architecture with Vanilla JavaScript

class SecondHandApp {
    constructor() {
        this.currentUser = null;
        this.currentPage = 'home';
        this.constants = {};
        this.items = [];
        this.currentItem = null;
        this.init();
    }

    // ============================================
    // Initialization
    // ============================================

    async init() {
        console.log('Initializing SecondHand Market App');
        
        // Load constants
        await this.loadConstants();
        
        // Check if user is logged in
        await this.checkAuthStatus();
        
        // Setup navigation
        this.setupNavigation();
        
        // Load initial page
        this.navigateTo('home');
    }

    async loadConstants() {
        try {
            const response = await fetch('/api/constants');
            const data = await response.json();
            if (data.success) {
                this.constants = data.constants;
            }
        } catch (error) {
            console.error('Failed to load constants:', error);
        }
    }

    async checkAuthStatus() {
        try {
            const response = await fetch('/api/auth/current-user');
            const data = await response.json();
            
            if (data.success && data.user && data.user.is_authenticated) {
                this.currentUser = data.user;
                console.log('User authenticated:', this.currentUser.username);
            } else {
                this.currentUser = null;
            }
            
            this.updateNavigation();
        } catch (error) {
            console.error('Failed to check auth status:', error);
        }
    }

    setupNavigation() {
        // Navigation links are setup, page rendering handled by navigateTo
    }

    updateNavigation() {
        const authNav = document.getElementById('authNav');
        if (!authNav) return;

        if (this.currentUser) {
            authNav.innerHTML = `
                <a href="#" onclick="app.navigateTo('dashboard'); return false;">${this.currentUser.username}</a>
                <a href="#" onclick="app.handleLogout(); return false;">Logout</a>
                <a href="#" onclick="app.navigateTo('sell'); return false;" class="btn-sell">+ Sell</a>
            `;
        } else {
            authNav.innerHTML = `
                <a href="#" onclick="app.navigateTo('login'); return false;">Login</a>
                <a href="#" onclick="app.navigateTo('register'); return false;">Register</a>
            `;
        }
    }

    // ============================================
    // Navigation & Routing
    // ============================================

    navigateTo(page, params = {}) {
        this.currentPage = page;
        
        // Protect pages that require authentication
        const protectedPages = ['sell', 'dashboard'];
        if (protectedPages.includes(page) && !this.currentUser) {
            this.navigateTo('login');
            return;
        }

        // Render the appropriate page
        switch (page) {
            case 'home':
                this.renderHome();
                break;
            case 'browse':
                this.renderBrowse();
                break;
            case 'login':
                this.renderLogin();
                break;
            case 'register':
                this.renderRegister();
                break;
            case 'item-detail':
                this.renderItemDetail(params.itemId);
                break;
            case 'sell':
                this.renderSell();
                break;
            case 'dashboard':
                this.renderDashboard();
                break;
            default:
                this.renderHome();
        }

        // Scroll to top
        window.scrollTo(0, 0);
    }

    // ============================================
    // Page: Home
    // ============================================

    async renderHome() {
        try {
            const response = await fetch('/api/items?limit=12');
            const data = await response.json();
            
            if (!data.success) {
                this.showError('Failed to load items');
                return;
            }

            this.items = data.items;

            let html = `
                <div class="hero">
                    <h1>Welcome to SecondHand Market</h1>
                    <p>Buy and sell quality items from your community</p>
                    <button class="btn btn-primary" onclick="app.navigateTo('browse')">Browse Items</button>
                    ${this.currentUser ? `<button class="btn btn-secondary" onclick="app.navigateTo('sell')">Sell Something</button>` : `<button class="btn btn-secondary" onclick="app.navigateTo('register')">Join Now</button>`}
                </div>

                <div class="section">
                    <h2>Featured Items</h2>
                    <div class="items-grid">
                        ${data.items.slice(0, 6).map(item => this.renderItemCard(item)).join('')}
                    </div>
                </div>
            `;

            document.getElementById('app-content').innerHTML = html;
        } catch (error) {
            console.error('Error rendering home:', error);
            this.showError('Error loading home page');
        }
    }

    // ============================================
    // Page: Browse Items
    // ============================================

    async renderBrowse() {
        try {
            const category = new URLSearchParams(window.location.search).get('category') || '';
            const search = new URLSearchParams(window.location.search).get('search') || '';

            let url = `/api/items?limit=24`;
            if (category) url += `&category=${encodeURIComponent(category)}`;
            if (search) url += `&search=${encodeURIComponent(search)}`;

            const response = await fetch(url);
            const data = await response.json();

            if (!data.success) {
                this.showError('Failed to load items');
                return;
            }

            let html = `
                <div class="browse-container">
                    <div class="filters">
                        <h3>Filters</h3>
                        <div class="search-box">
                            <input type="text" id="searchInput" placeholder="Search items..." value="${search}">
                            <button onclick="app.performSearch()">Search</button>
                        </div>
                        
                        <h4>Categories</h4>
                        <div class="category-list">
                            <button class="category-btn ${!category ? 'active' : ''}" onclick="app.filterByCategory('')">All Categories</button>
                            ${this.constants.categories?.map(cat => `
                                <button class="category-btn ${category === cat ? 'active' : ''}" onclick="app.filterByCategory('${cat}')">${cat}</button>
                            `).join('') || ''}
                        </div>
                    </div>

                    <div class="items-section">
                        <h2>${category ? `${category} Items` : 'All Items'} (${data.total})</h2>
                        <div class="items-grid">
                            ${data.items.length > 0 ? 
                                data.items.map(item => this.renderItemCard(item)).join('') :
                                '<p>No items found</p>'
                            }
                        </div>
                    </div>
                </div>
            `;

            document.getElementById('app-content').innerHTML = html;

            // Setup search on Enter key
            document.getElementById('searchInput')?.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.performSearch();
            });
        } catch (error) {
            console.error('Error rendering browse:', error);
            this.showError('Error loading browse page');
        }
    }

    performSearch() {
        const searchInput = document.getElementById('searchInput');
        const search = searchInput?.value.trim() || '';
        if (search) {
            this.renderBrowse();
        }
    }

    filterByCategory(category) {
        this.renderBrowse();
    }

    renderItemCard(item) {
        return `
            <div class="item-card" onclick="app.navigateTo('item-detail', {itemId: ${item.id}})">
                <div class="item-image">
                    <div class="placeholder">IMG</div>
                </div>
                <div class="item-content">
                    <h3>${this.escapeHtml(item.title)}</h3>
                    <p class="item-category">${item.category}</p>
                    <p class="item-condition">${item.condition}</p>
                    <p class="item-seller">by ${this.escapeHtml(item.seller.username)}</p>
                    <div class="item-footer">
                        <span class="price">$${item.price.toFixed(2)}</span>
                        <span class="status">${item.is_sold ? 'Sold' : 'Available'}</span>
                    </div>
                </div>
            </div>
        `;
    }

    // ============================================
    // Page: Item Detail
    // ============================================

    async renderItemDetail(itemId) {
        try {
            const response = await fetch(`/api/items/${itemId}`);
            const data = await response.json();

            if (!data.success) {
                this.showError('Item not found');
                return;
            }

            const item = data.item;
            this.currentItem = item;

            let purchaseButton = '';
            if (this.currentUser && this.currentUser.id !== item.seller.id) {
                purchaseButton = `<button class="btn btn-primary" onclick="app.handlePurchase(${item.id})">Buy Now - $${item.price.toFixed(2)}</button>`;
            } else if (this.currentUser && this.currentUser.id === item.seller.id) {
                purchaseButton = '<p class="info-text">This is your item</p>';
            } else {
                purchaseButton = `<button class="btn btn-primary" onclick="app.navigateTo('login')">Login to Buy</button>`;
            }

            let html = `
                <div class="item-detail-container">
                    <div class="item-image-section">
                        <div class="item-image-large">IMG</div>
                    </div>

                    <div class="item-info-section">
                        <h1>${this.escapeHtml(item.title)}</h1>
                        
                        <div class="item-meta">
                            <span class="badge">${item.category}</span>
                            <span class="badge">${item.condition}</span>
                            <span class="badge">${item.is_sold ? 'Sold' : 'Available'}</span>
                        </div>

                        <div class="seller-card">
                            <h3>Seller</h3>
                            <p><strong>${this.escapeHtml(item.seller.full_name)}</strong></p>
                            <p>@${this.escapeHtml(item.seller.username)}</p>
                            <p class="seller-bio">${this.escapeHtml(item.seller.bio || 'No bio')}</p>
                        </div>

                        <div class="pricing-section">
                            <h2>$${item.price.toFixed(2)}</h2>
                            ${!item.is_sold ? purchaseButton : '<p class="sold-text">This item has been sold</p>'}
                        </div>
                    </div>
                </div>

                <div class="item-description-section">
                    <h2>Description</h2>
                    <p>${this.escapeHtml(item.description)}</p>
                    <p class="date-posted">Posted on ${new Date(item.created_at).toLocaleDateString()}</p>
                </div>

                <div class="back-button">
                    <button class="btn btn-secondary" onclick="app.navigateTo('browse')">← Back to Browse</button>
                </div>
            `;

            document.getElementById('app-content').innerHTML = html;
        } catch (error) {
            console.error('Error rendering item detail:', error);
            this.showError('Error loading item details');
        }
    }

    async handlePurchase(itemId) {
        if (!this.currentUser) {
            this.navigateTo('login');
            return;
        }

        if (!confirm('Are you sure you want to purchase this item?')) {
            return;
        }

        try {
            const response = await fetch(`/api/purchase/${itemId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const data = await response.json();

            if (data.success) {
                this.showSuccess('Purchase successful! Check your dashboard for details.');
                setTimeout(() => this.navigateTo('dashboard'), 2000);
            } else {
                this.showError(data.error || 'Purchase failed');
            }
        } catch (error) {
            console.error('Error during purchase:', error);
            this.showError('Error processing purchase');
        }
    }

    // ============================================
    // Page: Login
    // ============================================

    renderLogin() {
        let html = `
            <div class="auth-container">
                <div class="auth-card">
                    <h1>Login</h1>
                    <form onsubmit="return app.handleLogin(event)">
                        <div class="form-group">
                            <label for="username">Username</label>
                            <input type="text" id="username" name="username" required>
                        </div>

                        <div class="form-group">
                            <label for="password">Password</label>
                            <input type="password" id="password" name="password" required>
                        </div>

                        <button type="submit" class="btn btn-primary">Login</button>
                    </form>

                    <p class="auth-link">
                        Don't have an account? <a href="#" onclick="app.navigateTo('register'); return false;">Register here</a>
                    </p>

                    <div id="loginError" class="error-message" style="display: none;"></div>
                </div>
            </div>
        `;

        document.getElementById('app-content').innerHTML = html;
    }

    async handleLogin(event) {
        event.preventDefault();

        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value;

        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            const data = await response.json();

            if (data.success) {
                this.currentUser = data.user;
                this.updateNavigation();
                this.showSuccess('Logged in successfully!');
                setTimeout(() => this.navigateTo('home'), 1500);
            } else {
                document.getElementById('loginError').textContent = data.error;
                document.getElementById('loginError').style.display = 'block';
            }
        } catch (error) {
            console.error('Login error:', error);
            document.getElementById('loginError').textContent = 'An error occurred during login';
            document.getElementById('loginError').style.display = 'block';
        }

        return false;
    }

    // ============================================
    // Page: Register
    // ============================================

    renderRegister() {
        let html = `
            <div class="auth-container">
                <div class="auth-card">
                    <h1>Register</h1>
                    <form onsubmit="return app.handleRegister(event)">
                        <div class="form-group">
                            <label for="fullName">Full Name</label>
                            <input type="text" id="fullName" name="fullName" required>
                        </div>

                        <div class="form-group">
                            <label for="regUsername">Username</label>
                            <input type="text" id="regUsername" name="username" required>
                        </div>

                        <div class="form-group">
                            <label for="email">Email</label>
                            <input type="email" id="email" name="email" required>
                        </div>

                        <div class="form-group">
                            <label for="regPassword">Password</label>
                            <input type="password" id="regPassword" name="password" required>
                        </div>

                        <button type="submit" class="btn btn-primary">Register</button>
                    </form>

                    <p class="auth-link">
                        Already have an account? <a href="#" onclick="app.navigateTo('login'); return false;">Login here</a>
                    </p>

                    <div id="registerError" class="error-message" style="display: none;"></div>
                </div>
            </div>
        `;

        document.getElementById('app-content').innerHTML = html;
    }

    async handleRegister(event) {
        event.preventDefault();

        const fullName = document.getElementById('fullName').value.trim();
        const username = document.getElementById('regUsername').value.trim();
        const email = document.getElementById('email').value.trim();
        const password = document.getElementById('regPassword').value;

        try {
            const response = await fetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, email, password, full_name: fullName })
            });

            const data = await response.json();

            if (data.success) {
                this.showSuccess('Registration successful! Please login.');
                setTimeout(() => this.navigateTo('login'), 1500);
            } else {
                document.getElementById('registerError').textContent = data.error;
                document.getElementById('registerError').style.display = 'block';
            }
        } catch (error) {
            console.error('Registration error:', error);
            document.getElementById('registerError').textContent = 'An error occurred during registration';
            document.getElementById('registerError').style.display = 'block';
        }

        return false;
    }

    // ============================================
    // Page: Sell Item
    // ============================================

    renderSell() {
        let html = `
            <div class="form-container">
                <h1>List a New Item</h1>
                <form onsubmit="return app.handleSellItem(event)">
                    <div class="form-group">
                        <label for="itemTitle">Item Title</label>
                        <input type="text" id="itemTitle" name="title" required>
                    </div>

                    <div class="form-group">
                        <label for="itemDescription">Description</label>
                        <textarea id="itemDescription" name="description" rows="6" required></textarea>
                    </div>

                    <div class="form-row">
                        <div class="form-group">
                            <label for="itemPrice">Price ($)</label>
                            <input type="number" id="itemPrice" name="price" step="0.01" min="0" required>
                        </div>

                        <div class="form-group">
                            <label for="itemCategory">Category</label>
                            <select id="itemCategory" name="category" required>
                                <option value="">Select a category</option>
                                ${this.constants.categories?.map(cat => `<option value="${cat}">${cat}</option>`).join('') || ''}
                            </select>
                        </div>

                        <div class="form-group">
                            <label for="itemCondition">Condition</label>
                            <select id="itemCondition" name="condition" required>
                                <option value="">Select condition</option>
                                ${this.constants.conditions?.map(cond => `<option value="${cond}">${cond}</option>`).join('') || ''}
                            </select>
                        </div>
                    </div>

                    <button type="submit" class="btn btn-primary">List Item</button>
                    <button type="button" class="btn btn-secondary" onclick="app.navigateTo('dashboard')">Cancel</button>
                </form>

                <div id="sellError" class="error-message" style="display: none;"></div>
            </div>
        `;

        document.getElementById('app-content').innerHTML = html;
    }

    async handleSellItem(event) {
        event.preventDefault();

        const title = document.getElementById('itemTitle').value.trim();
        const description = document.getElementById('itemDescription').value.trim();
        const price = parseFloat(document.getElementById('itemPrice').value);
        const category = document.getElementById('itemCategory').value;
        const condition = document.getElementById('itemCondition').value;

        try {
            const response = await fetch('/api/items', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, description, price, category, condition })
            });

            const data = await response.json();

            if (data.success) {
                this.showSuccess('Item listed successfully!');
                setTimeout(() => this.navigateTo('dashboard'), 1500);
            } else {
                document.getElementById('sellError').textContent = data.error;
                document.getElementById('sellError').style.display = 'block';
            }
        } catch (error) {
            console.error('Error listing item:', error);
            document.getElementById('sellError').textContent = 'An error occurred while listing the item';
            document.getElementById('sellError').style.display = 'block';
        }

        return false;
    }

    // ============================================
    // Page: Dashboard
    // ============================================

    async renderDashboard() {
        if (!this.currentUser) {
            this.navigateTo('login');
            return;
        }

        try {
            const response = await fetch('/api/dashboard');
            const data = await response.json();

            if (!data.success) {
                this.showError('Failed to load dashboard');
                return;
            }

            const dashboard = data.dashboard;

            let html = `
                <div class="dashboard-container">
                    <h1>Dashboard - ${this.escapeHtml(dashboard.user.full_name)}</h1>

                    <div class="dashboard-menu">
                        <button class="btn btn-secondary" onclick="app.navigateTo('sell')">+ List New Item</button>
                        <button class="btn btn-secondary" onclick="app.navigateTo('browse')">Browse Items</button>
                    </div>

                    <!-- Listings Section -->
                    <div class="dashboard-section">
                        <h2>My Listings (${dashboard.listings.length})</h2>
                        ${dashboard.listings.length > 0 ? `
                            <table class="dashboard-table">
                                <thead>
                                    <tr>
                                        <th>Title</th>
                                        <th>Price</th>
                                        <th>Category</th>
                                        <th>Status</th>
                                        <th>Posted</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${dashboard.listings.map(item => `
                                        <tr>
                                            <td>${this.escapeHtml(item.title)}</td>
                                            <td>$${item.price.toFixed(2)}</td>
                                            <td>${item.category}</td>
                                            <td><span class="badge ${item.is_sold ? 'sold' : 'available'}">${item.is_sold ? 'Sold' : 'Available'}</span></td>
                                            <td>${new Date(item.created_at).toLocaleDateString()}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        ` : '<p>You haven\'t listed any items yet. <a href="#" onclick="app.navigateTo(\'sell\'); return false;">Get started</a></p>'}
                    </div>

                    <!-- Purchases Section -->
                    <div class="dashboard-section">
                        <h2>My Purchases (${dashboard.purchases.length})</h2>
                        ${dashboard.purchases.length > 0 ? `
                            <table class="dashboard-table">
                                <thead>
                                    <tr>
                                        <th>Item</th>
                                        <th>Seller</th>
                                        <th>Price</th>
                                        <th>Status</th>
                                        <th>Date</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${dashboard.purchases.map(purchase => `
                                        <tr>
                                            <td>${this.escapeHtml(purchase.item.title)}</td>
                                            <td>${this.escapeHtml(purchase.seller.username)}</td>
                                            <td>$${purchase.item.price.toFixed(2)}</td>
                                            <td><span class="badge">${purchase.status}</span></td>
                                            <td>${new Date(purchase.created_at).toLocaleDateString()}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        ` : '<p>You haven\'t purchased anything yet. <a href="#" onclick="app.navigateTo(\'browse\'); return false;">Browse items</a></p>'}
                    </div>

                    <!-- Sales Section -->
                    <div class="dashboard-section">
                        <h2>My Sales (${dashboard.sales.length})</h2>
                        ${dashboard.sales.length > 0 ? `
                            <table class="dashboard-table">
                                <thead>
                                    <tr>
                                        <th>Item</th>
                                        <th>Buyer</th>
                                        <th>Price</th>
                                        <th>Status</th>
                                        <th>Date</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${dashboard.sales.map(sale => `
                                        <tr>
                                            <td>${this.escapeHtml(sale.item.title)}</td>
                                            <td>${this.escapeHtml(sale.buyer.username)}</td>
                                            <td>$${sale.item.price.toFixed(2)}</td>
                                            <td><span class="badge">${sale.status}</span></td>
                                            <td>${new Date(sale.created_at).toLocaleDateString()}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        ` : '<p>You haven\'t made any sales yet.</p>'}
                    </div>
                </div>
            `;

            document.getElementById('app-content').innerHTML = html;
        } catch (error) {
            console.error('Error rendering dashboard:', error);
            this.showError('Error loading dashboard');
        }
    }

    // ============================================
    // Authentication Handlers
    // ============================================

    async handleLogout() {
        try {
            const response = await fetch('/api/auth/logout', { method: 'POST' });
            const data = await response.json();

            if (data.success) {
                this.currentUser = null;
                this.updateNavigation();
                this.showSuccess('Logged out successfully');
                setTimeout(() => this.navigateTo('home'), 1500);
            }
        } catch (error) {
            console.error('Logout error:', error);
            this.showError('Error logging out');
        }
    }

    // ============================================
    // Utility Functions
    // ============================================

    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }

    showError(message) {
        console.error(message);
        const notification = document.createElement('div');
        notification.className = 'notification error';
        notification.textContent = message;
        document.body.appendChild(notification);
        
        setTimeout(() => notification.remove(), 4000);
    }

    showSuccess(message) {
        console.log(message);
        const notification = document.createElement('div');
        notification.className = 'notification success';
        notification.textContent = message;
        document.body.appendChild(notification);
        
        setTimeout(() => notification.remove(), 3000);
    }
}

// ============================================
// Initialize App on Page Load
// ============================================

let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new SecondHandApp();
});
