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
    login_manager.login_view = 'auth_login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    # Blueprint: Authentication
    @app.route('/')
    def index():
        items = Item.query.filter_by(is_sold=False).order_by(Item.created_at.desc()).limit(12).all()
        return render_template('index.html', items=items)
    
    @app.route('/register', methods=['GET', 'POST'])
    def auth_register():
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            full_name = request.form.get('full_name')
            
            if User.query.filter_by(username=username).first():
                return render_template('register.html', error='Username already exists')
            
            if User.query.filter_by(email=email).first():
                return render_template('register.html', error='Email already exists')
            
            user = User(username=username, email=email, full_name=full_name)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            return redirect(url_for('auth_login'))
        
        return render_template('register.html')
    
    @app.route('/login', methods=['GET', 'POST'])
    def auth_login():
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                session['user_id'] = user.id
                login_user(user)
                return redirect(url_for('dashboard'))
            
            return render_template('login.html', error='Invalid username or password')
        
        return render_template('login.html')
    
    @app.route('/logout')
    def auth_logout():
        session.clear()
        logout_user()
        return redirect(url_for('index'))
    
    # Blueprint: Dashboard
    @app.route('/dashboard')
    @login_required
    def dashboard():
        user_items = Item.query.filter_by(seller_id=current_user.id).order_by(Item.created_at.desc()).all()
        purchases = Transaction.query.filter_by(buyer_id=current_user.id).order_by(Transaction.created_at.desc()).all()
        sales = Transaction.query.filter_by(seller_id=current_user.id).order_by(Transaction.created_at.desc()).all()
        
        return render_template('dashboard.html', user_items=user_items, purchases=purchases, sales=sales)
    
    # Blueprint: Items
    @app.route('/browse')
    def browse_items():
        category = request.args.get('category', '')
        search = request.args.get('search', '')
        
        query = Item.query.filter_by(is_sold=False)
        
        if category:
            query = query.filter_by(category=category)
        
        if search:
            query = query.filter(Item.title.ilike(f'%{search}%') | Item.description.ilike(f'%{search}%'))
        
        items = query.order_by(Item.created_at.desc()).all()
        categories = ['Electronics', 'Furniture', 'Clothing', 'Books', 'Sports', 'Other']
        
        return render_template('items.html', items=items, categories=categories, current_category=category, search=search)
    
    @app.route('/item/<int:item_id>')
    def item_detail(item_id):
        item = Item.query.get_or_404(item_id)
        return render_template('item_detail.html', item=item)
    
    @app.route('/sell', methods=['GET', 'POST'])
    @login_required
    def sell_item():
        if request.method == 'POST':
            title = request.form.get('title')
            description = request.form.get('description')
            price = float(request.form.get('price'))
            category = request.form.get('category')
            condition = request.form.get('condition')
            
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
            
            return redirect(url_for('dashboard'))
        
        categories = ['Electronics', 'Furniture', 'Clothing', 'Books', 'Sports', 'Other']
        conditions = ['New', 'Like New', 'Good', 'Fair']
        
        return render_template('sell_item.html', categories=categories, conditions=conditions)
    
    @app.route('/api/purchase/<int:item_id>', methods=['POST'])
    @login_required
    def api_purchase(item_id):
        item = Item.query.get_or_404(item_id)
        
        if item.is_sold:
            return jsonify({'error': 'Item already sold'}), 400
        
        if item.seller_id == current_user.id:
            return jsonify({'error': 'Cannot buy your own item'}), 400
        
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
        
        return jsonify({'success': True, 'message': 'Purchase completed'})
    
    return app


if __name__ == '__main__':
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    app.run(debug=True, host='0.0.0.0', port=5000)
