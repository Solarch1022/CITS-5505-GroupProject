from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from datetime import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from config import config
from models import db, User, Item, Transaction


def create_app(config_name='development'):
    """Application factory"""
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    
    login_manager = LoginManager()
    login_manager.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    @login_manager.unauthorized_handler
    def unauthorized():
        """Handle unauthorized API requests"""
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Unauthorized. Please login first.'}), 401
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    # ============================================
    # STATIC PAGE SERVING (for index/landing)
    # ============================================
    
    @app.route('/')
    def index():
        """Serve the main SPA (Single Page Application) shell"""
        return render_template('index.html')
    
    @app.route('/app')
    def app_shell():
        """Serve the app shell"""
        return render_template('app.html')
    
    # ============================================
    # FALLBACK ROUTES (from old architecture)
    # ============================================
    # These routes redirect to the SPA for backward compatibility
    
    @app.route('/browse')
    @app.route('/items')
    def browse_fallback():
        """Redirect old browse route to SPA"""
        return redirect('/app')
    
    @app.route('/login')
    def auth_login_fallback():
        """Redirect old login route to SPA"""
        return redirect('/app')
    
    @app.route('/register')
    def auth_register_fallback():
        """Redirect old register route to SPA"""
        return redirect('/app')
    
    @app.route('/sell')
    def sell_item_fallback():
        """Redirect old sell route to SPA"""
        return redirect('/app')
    
    @app.route('/dashboard')
    def dashboard_fallback():
        """Redirect old dashboard route to SPA"""
        return redirect('/app')
    
    @app.route('/item/<int:item_id>')
    def item_detail_fallback(item_id):
        """Redirect old item detail route to SPA"""
        return redirect('/app')
    
    @app.route('/logout')
    def auth_logout_fallback():
        """Redirect old logout route to SPA"""
        session.clear()
        logout_user()
        return redirect('/app')
    
    # ============================================
    # API: AUTHENTICATION ENDPOINTS
    # ============================================
    
    @app.route('/api/auth/register', methods=['POST'])
    def api_auth_register():
        """Register a new user"""
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON'}), 400
        
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        full_name = data.get('full_name', '').strip()
        
        # Validation
        if not username or not email or not password or not full_name:
            return jsonify({'success': False, 'error': 'All fields are required'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Password must be at least 6 characters'}), 400
        
        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'error': 'Username already exists'}), 400
        
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'error': 'Email already exists'}), 400
        
        # Create user
        user = User(username=username, email=email, full_name=full_name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'User registered successfully',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.full_name
            }
        }), 201
    
    @app.route('/api/auth/login', methods=['POST'])
    def api_auth_login():
        """Login user and create session"""
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON'}), 400
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Username and password required'}), 400
        
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            return jsonify({'success': False, 'error': 'Invalid username or password'}), 401
        
        login_user(user)
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.full_name
            }
        }), 200
    
    @app.route('/api/auth/logout', methods=['POST'])
    def api_auth_logout():
        """Logout current user"""
        session.clear()
        logout_user()
        
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        }), 200
    
    @app.route('/api/auth/current-user', methods=['GET'])
    def api_current_user():
        """Get current authenticated user"""
        if current_user.is_authenticated:
            return jsonify({
                'success': True,
                'user': {
                    'id': current_user.id,
                    'username': current_user.username,
                    'email': current_user.email,
                    'full_name': current_user.full_name,
                    'is_authenticated': True
                }
            }), 200
        
        return jsonify({
            'success': True,
            'user': None,
            'is_authenticated': False
        }), 200
    
    # ============================================
    # API: ITEM ENDPOINTS
    # ============================================
    
    @app.route('/api/items', methods=['GET'])
    def api_get_items():
        """Get all items with optional filters"""
        category = request.args.get('category', '').strip()
        search = request.args.get('search', '').strip()
        limit = int(request.args.get('limit', 12))
        offset = int(request.args.get('offset', 0))
        
        # Build query
        query = Item.query.filter_by(is_sold=False)
        
        if category:
            query = query.filter_by(category=category)
        
        if search:
            query = query.filter(
                (Item.title.ilike(f'%{search}%')) |
                (Item.description.ilike(f'%{search}%'))
            )
        
        total = query.count()
        items = query.order_by(Item.created_at.desc()).offset(offset).limit(limit).all()
        
        return jsonify({
            'success': True,
            'items': [
                {
                    'id': item.id,
                    'title': item.title,
                    'description': item.description,
                    'price': item.price,
                    'category': item.category,
                    'condition': item.condition,
                    'is_sold': item.is_sold,
                    'created_at': item.created_at.isoformat(),
                    'seller': {
                        'id': item.seller.id,
                        'username': item.seller.username,
                        'full_name': item.seller.full_name
                    }
                }
                for item in items
            ],
            'total': total,
            'limit': limit,
            'offset': offset
        }), 200
    
    @app.route('/api/items/<int:item_id>', methods=['GET'])
    def api_get_item(item_id):
        """Get single item details"""
        item = Item.query.get(item_id)
        
        if not item:
            return jsonify({'success': False, 'error': 'Item not found'}), 404
        
        return jsonify({
            'success': True,
            'item': {
                'id': item.id,
                'title': item.title,
                'description': item.description,
                'price': item.price,
                'category': item.category,
                'condition': item.condition,
                'is_sold': item.is_sold,
                'created_at': item.created_at.isoformat(),
                'seller': {
                    'id': item.seller.id,
                    'username': item.seller.username,
                    'full_name': item.seller.full_name,
                    'bio': item.seller.bio or ''
                }
            }
        }), 200
    
    @app.route('/api/items', methods=['POST'])
    @login_required
    def api_create_item():
        """Create new item listing"""
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON'}), 400
        
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        price = data.get('price')
        category = data.get('category', '').strip()
        condition = data.get('condition', '').strip()
        
        # Validation
        if not all([title, description, price, category, condition]):
            return jsonify({'success': False, 'error': 'All fields are required'}), 400
        
        try:
            price = float(price)
            if price < 0:
                raise ValueError()
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid price'}), 400
        
        # Create item
        item = Item(
            title=title,
            description=description,
            price=price,
            category=category,
            condition=condition,
            seller_id=current_user.id
        )
        
        db.session.add(item)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Item listed successfully',
            'item': {
                'id': item.id,
                'title': item.title,
                'price': item.price,
                'seller_id': item.seller_id
            }
        }), 201
    
    # ============================================
    # API: TRANSACTION ENDPOINTS
    # ============================================
    
    @app.route('/api/purchase/<int:item_id>', methods=['POST'])
    @login_required
    def api_purchase(item_id):
        """Purchase an item"""
        item = Item.query.get(item_id)
        
        if not item:
            return jsonify({'success': False, 'error': 'Item not found'}), 404
        
        if item.is_sold:
            return jsonify({'success': False, 'error': 'Item already sold'}), 400
        
        if item.seller_id == current_user.id:
            return jsonify({'success': False, 'error': 'Cannot buy your own item'}), 400
        
        # Create transaction
        transaction = Transaction(
            item_id=item.id,
            seller_id=item.seller_id,
            buyer_id=current_user.id,
            price=item.price,
            status='completed'
        )
        
        item.is_sold = True
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Purchase completed successfully',
            'transaction': {
                'id': transaction.id,
                'item_id': transaction.item_id,
                'price': transaction.price,
                'status': transaction.status,
                'created_at': transaction.created_at.isoformat()
            }
        }), 200
    
    # ============================================
    # API: DASHBOARD ENDPOINTS
    # ============================================
    
    @app.route('/api/dashboard', methods=['GET'])
    @login_required
    def api_dashboard():
        """Get user dashboard data"""
        user_items = Item.query.filter_by(seller_id=current_user.id).order_by(Item.created_at.desc()).all()
        purchases = Transaction.query.filter_by(buyer_id=current_user.id).order_by(Transaction.created_at.desc()).all()
        sales = Transaction.query.filter_by(seller_id=current_user.id).order_by(Transaction.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'dashboard': {
                'user': {
                    'id': current_user.id,
                    'username': current_user.username,
                    'full_name': current_user.full_name,
                    'email': current_user.email,
                    'bio': current_user.bio or ''
                },
                'listings': [
                    {
                        'id': item.id,
                        'title': item.title,
                        'description': item.description[:50] + '...' if len(item.description) > 50 else item.description,
                        'price': item.price,
                        'category': item.category,
                        'condition': item.condition,
                        'is_sold': item.is_sold,
                        'created_at': item.created_at.isoformat()
                    }
                    for item in user_items
                ],
                'purchases': [
                    {
                        'id': t.id,
                        'item': {
                            'id': t.item.id,
                            'title': t.item.title,
                            'price': t.price
                        },
                        'seller': {
                            'id': t.seller.id,
                            'username': t.seller.username,
                            'full_name': t.seller.full_name
                        },
                        'status': t.status,
                        'created_at': t.created_at.isoformat()
                    }
                    for t in purchases
                ],
                'sales': [
                    {
                        'id': t.id,
                        'item': {
                            'id': t.item.id,
                            'title': t.item.title,
                            'price': t.price
                        },
                        'buyer': {
                            'id': t.buyer.id,
                            'username': t.buyer.username,
                            'full_name': t.buyer.full_name
                        },
                        'status': t.status,
                        'created_at': t.created_at.isoformat()
                    }
                    for t in sales
                ]
            }
        }), 200
    
    # ============================================
    # CONSTANTS (for frontend)
    # ============================================
    
    @app.route('/api/constants', methods=['GET'])
    def api_constants():
        """Get constants like categories and conditions"""
        return jsonify({
            'success': True,
            'constants': {
                'categories': ['Electronics', 'Furniture', 'Clothing', 'Books', 'Sports', 'Other'],
                'conditions': ['New', 'Like New', 'Good', 'Fair']
            }
        }), 200
    
    return app


if __name__ == '__main__':
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    port = int(os.environ.get('PORT', 8000))
    app.run(debug=True, host='0.0.0.0', port=port)

