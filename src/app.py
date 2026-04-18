from datetime import datetime
from functools import wraps
import os
import secrets
import sys

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user

sys.path.insert(0, os.path.dirname(__file__))

from config import config
from models import Conversation, Item, Message, Transaction, User, db


ITEM_CATEGORIES = ['Electronics', 'Furniture', 'Clothing', 'Books', 'Sports', 'Other']
ITEM_CONDITIONS = ['New', 'Like New', 'Good', 'Fair']
UWA_STUDENT_DOMAIN = '@student.uwa.edu.au'
MAX_MESSAGE_LENGTH = 600


def is_valid_uwa_student_email(email):
    return email.lower().endswith(UWA_STUDENT_DOMAIN)


def create_app(config_name='development'):
    """Application factory."""
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config[config_name])

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({'success': False, 'error': 'Unauthorized. Please login first.'}), 401

    def ensure_csrf_token():
        token = session.get('csrf_token')
        if not token:
            token = secrets.token_hex(16)
            session['csrf_token'] = token
        return token

    def rotate_csrf_token():
        token = secrets.token_hex(16)
        session['csrf_token'] = token
        return token

    def csrf_protect(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            expected = ensure_csrf_token()
            provided = request.headers.get('X-CSRF-Token')
            if not provided or provided != expected:
                return jsonify({'success': False, 'error': 'Invalid CSRF token'}), 403
            return view(*args, **kwargs)

        return wrapped

    def redirect_to_spa(fragment=''):
        target = url_for('index')
        return redirect(f'{target}#{fragment}' if fragment else target)

    def get_user_reputation(user):
        completed_sales = Transaction.query.filter_by(seller_id=user.id, status='completed').count()
        completed_purchases = Transaction.query.filter_by(buyer_id=user.id, status='completed').count()
        active_listings = Item.query.filter_by(seller_id=user.id, is_sold=False).count()
        total_deals = completed_sales + completed_purchases

        if total_deals == 0:
            score = 0.0
            label = 'New member'
        else:
            score = round(min(5.0, 4.0 + min(0.7, completed_sales * 0.1) + min(0.3, completed_purchases * 0.05)), 1)
            label = 'Trusted trader' if score >= 4.7 else 'Active trader'

        return {
            'score': score,
            'label': label,
            'completed_sales': completed_sales,
            'completed_purchases': completed_purchases,
            'active_listings': active_listings,
        }

    def serialize_user(user, include_email=False):
        payload = {
            'id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'bio': user.bio or '',
            'is_uwa_verified': is_valid_uwa_student_email(user.email),
            'reputation': get_user_reputation(user),
        }
        if include_email:
            payload['email'] = user.email
        return payload

    def serialize_item(item, include_description=True):
        payload = {
            'id': item.id,
            'title': item.title,
            'price': item.price,
            'category': item.category,
            'condition': item.condition,
            'is_sold': item.is_sold,
            'created_at': item.created_at.isoformat(),
            'seller': serialize_user(item.seller),
        }
        if include_description:
            payload['description'] = item.description
        return payload

    def serialize_message(message):
        return {
            'id': message.id,
            'body': message.body,
            'created_at': message.created_at.isoformat(),
            'sender': {
                'id': message.sender.id,
                'username': message.sender.username,
                'full_name': message.sender.full_name,
            },
        }

    def serialize_conversation(conversation, viewer_id=None, include_messages=False):
        messages = (
            Message.query
            .filter_by(conversation_id=conversation.id)
            .order_by(Message.created_at.asc())
            .all()
        )
        latest_message = messages[-1] if messages else None
        counterpart = conversation.seller if viewer_id == conversation.buyer_id else conversation.buyer

        payload = {
            'id': conversation.id,
            'created_at': conversation.created_at.isoformat(),
            'updated_at': conversation.updated_at.isoformat(),
            'item': {
                'id': conversation.item.id,
                'title': conversation.item.title,
                'price': conversation.item.price,
                'is_sold': conversation.item.is_sold,
            },
            'seller_id': conversation.seller_id,
            'buyer_id': conversation.buyer_id,
            'counterpart': serialize_user(counterpart),
            'latest_message': serialize_message(latest_message) if latest_message else None,
            'message_count': len(messages),
        }

        if include_messages:
            payload['messages'] = [serialize_message(message) for message in messages]

        return payload

    def get_item_or_404(item_id):
        item = db.session.get(Item, item_id)
        if not item:
            return None, (jsonify({'success': False, 'error': 'Item not found'}), 404)
        return item, None

    def get_conversation_or_404(conversation_id):
        conversation = db.session.get(Conversation, conversation_id)
        if not conversation:
            return None, (jsonify({'success': False, 'error': 'Conversation not found'}), 404)

        if current_user.id not in {conversation.seller_id, conversation.buyer_id}:
            return None, (jsonify({'success': False, 'error': 'Forbidden'}), 403)

        return conversation, None

    @app.before_request
    def bootstrap_session():
        ensure_csrf_token()

    with app.app_context():
        db.create_all()

    @app.route('/')
    def index():
        """Serve the main SPA shell."""
        return render_template('app.html', csrf_token=ensure_csrf_token())

    @app.route('/app')
    def app_shell():
        """Serve the SPA shell on the legacy /app route."""
        return render_template('app.html', csrf_token=ensure_csrf_token())

    @app.route('/browse')
    @app.route('/items')
    def browse_fallback():
        return redirect_to_spa('/browse')

    @app.route('/login')
    def auth_login_fallback():
        return redirect_to_spa('/login')

    @app.route('/register')
    def auth_register_fallback():
        return redirect_to_spa('/register')

    @app.route('/sell')
    def sell_item_fallback():
        return redirect_to_spa('/sell')

    @app.route('/dashboard')
    def dashboard_fallback():
        return redirect_to_spa('/dashboard')

    @app.route('/item/<int:item_id>')
    def item_detail_fallback(item_id):
        return redirect_to_spa(f'/item/{item_id}')

    @app.route('/logout')
    def auth_logout_fallback():
        logout_user()
        session.clear()
        rotate_csrf_token()
        return redirect_to_spa('/login')

    @app.route('/api/auth/register', methods=['POST'])
    @csrf_protect
    def api_auth_register():
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON'}), 400

        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        full_name = data.get('full_name', '').strip()

        if not username or not email or not password or not full_name:
            return jsonify({'success': False, 'error': 'All fields are required'}), 400

        if len(username) < 3:
            return jsonify({'success': False, 'error': 'Username must be at least 3 characters'}), 400

        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Password must be at least 6 characters'}), 400

        if not is_valid_uwa_student_email(email):
            return jsonify({
                'success': False,
                'error': 'Only verified UWA student emails are allowed. Use your @student.uwa.edu.au address.'
            }), 400

        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'error': 'Username already exists'}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'error': 'Email already exists'}), 400

        user = User(username=username, email=email, full_name=full_name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Registration successful. Your UWA student account is now verified.',
            'user': serialize_user(user, include_email=True),
            'csrf_token': ensure_csrf_token(),
        }), 201

    @app.route('/api/auth/login', methods=['POST'])
    @csrf_protect
    def api_auth_login():
        data = request.get_json(silent=True)
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
            'user': serialize_user(user, include_email=True),
            'csrf_token': ensure_csrf_token(),
        }), 200

    @app.route('/api/auth/logout', methods=['POST'])
    @csrf_protect
    def api_auth_logout():
        logout_user()
        session.clear()
        csrf_token = rotate_csrf_token()

        return jsonify({
            'success': True,
            'message': 'Logged out successfully',
            'csrf_token': csrf_token,
        }), 200

    @app.route('/api/auth/current-user', methods=['GET'])
    def api_current_user():
        if current_user.is_authenticated:
            return jsonify({
                'success': True,
                'user': serialize_user(current_user, include_email=True),
                'is_authenticated': True,
                'csrf_token': ensure_csrf_token(),
            }), 200

        return jsonify({
            'success': True,
            'user': None,
            'is_authenticated': False,
            'csrf_token': ensure_csrf_token(),
        }), 200

    @app.route('/api/items', methods=['GET'])
    def api_get_items():
        category = request.args.get('category', '').strip()
        search = request.args.get('search', '').strip()
        limit = max(1, min(int(request.args.get('limit', 12)), 48))
        offset = max(0, int(request.args.get('offset', 0)))
        include_sold = request.args.get('include_sold', 'false').lower() == 'true'

        query = Item.query
        if not include_sold:
            query = query.filter_by(is_sold=False)
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
            'items': [serialize_item(item) for item in items],
            'total': total,
            'limit': limit,
            'offset': offset,
        }), 200

    @app.route('/api/items/<int:item_id>', methods=['GET'])
    def api_get_item(item_id):
        item, error_response = get_item_or_404(item_id)
        if error_response:
            return error_response

        seller_conversation_count = Conversation.query.filter_by(seller_id=item.seller_id).count()

        return jsonify({
            'success': True,
            'item': {
                **serialize_item(item),
                'seller': {
                    **serialize_user(item.seller),
                    'conversation_count': seller_conversation_count,
                },
            },
        }), 200

    @app.route('/api/items', methods=['POST'])
    @login_required
    @csrf_protect
    def api_create_item():
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON'}), 400

        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        price = data.get('price')
        category = data.get('category', '').strip()
        condition = data.get('condition', '').strip()

        if not all([title, description, price, category, condition]):
            return jsonify({'success': False, 'error': 'All fields are required'}), 400

        if len(title) < 4:
            return jsonify({'success': False, 'error': 'Item title must be at least 4 characters'}), 400

        if len(description) < 15:
            return jsonify({'success': False, 'error': 'Description should be at least 15 characters'}), 400

        if category not in ITEM_CATEGORIES:
            return jsonify({'success': False, 'error': 'Invalid category'}), 400

        if condition not in ITEM_CONDITIONS:
            return jsonify({'success': False, 'error': 'Invalid condition'}), 400

        try:
            price = float(price)
            if price <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'Price must be a positive number'}), 400

        item = Item(
            title=title,
            description=description,
            price=price,
            category=category,
            condition=condition,
            seller_id=current_user.id,
        )
        db.session.add(item)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Item listed successfully',
            'item': serialize_item(item),
        }), 201

    @app.route('/api/purchase/<int:item_id>', methods=['POST'])
    @login_required
    @csrf_protect
    def api_purchase(item_id):
        item, error_response = get_item_or_404(item_id)
        if error_response:
            return error_response

        if item.is_sold:
            return jsonify({'success': False, 'error': 'Item already sold'}), 400

        if item.seller_id == current_user.id:
            return jsonify({'success': False, 'error': 'Cannot buy your own item'}), 400

        transaction = Transaction(
            item_id=item.id,
            seller_id=item.seller_id,
            buyer_id=current_user.id,
            price=item.price,
            status='completed',
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
                'created_at': transaction.created_at.isoformat(),
            },
        }), 200

    @app.route('/api/dashboard', methods=['GET'])
    @login_required
    def api_dashboard():
        user_items = Item.query.filter_by(seller_id=current_user.id).order_by(Item.created_at.desc()).all()
        purchases = Transaction.query.filter_by(buyer_id=current_user.id).order_by(Transaction.created_at.desc()).all()
        sales = Transaction.query.filter_by(seller_id=current_user.id).order_by(Transaction.created_at.desc()).all()

        return jsonify({
            'success': True,
            'dashboard': {
                'user': serialize_user(current_user, include_email=True),
                'listings': [
                    {
                        **serialize_item(item),
                        'description_preview': (
                            item.description[:90] + '...' if len(item.description) > 90 else item.description
                        ),
                    }
                    for item in user_items
                ],
                'purchases': [
                    {
                        'id': transaction.id,
                        'item': {
                            'id': transaction.item.id,
                            'title': transaction.item.title,
                            'price': transaction.price,
                        },
                        'seller': serialize_user(transaction.seller),
                        'status': transaction.status,
                        'created_at': transaction.created_at.isoformat(),
                    }
                    for transaction in purchases
                ],
                'sales': [
                    {
                        'id': transaction.id,
                        'item': {
                            'id': transaction.item.id,
                            'title': transaction.item.title,
                            'price': transaction.price,
                        },
                        'buyer': serialize_user(transaction.buyer),
                        'status': transaction.status,
                        'created_at': transaction.created_at.isoformat(),
                    }
                    for transaction in sales
                ],
            },
        }), 200

    @app.route('/api/items/<int:item_id>/conversation', methods=['GET'])
    @login_required
    def api_get_item_conversation(item_id):
        item, error_response = get_item_or_404(item_id)
        if error_response:
            return error_response

        if current_user.id == item.seller_id:
            conversations = (
                Conversation.query
                .filter_by(item_id=item.id)
                .order_by(Conversation.updated_at.desc())
                .all()
            )
            return jsonify({
                'success': True,
                'mode': 'seller',
                'conversations': [
                    serialize_conversation(conversation, viewer_id=current_user.id)
                    for conversation in conversations
                ],
            }), 200

        conversation = Conversation.query.filter_by(item_id=item.id, buyer_id=current_user.id).first()
        return jsonify({
            'success': True,
            'mode': 'buyer',
            'conversation': (
                serialize_conversation(conversation, viewer_id=current_user.id, include_messages=True)
                if conversation else None
            ),
        }), 200

    @app.route('/api/items/<int:item_id>/conversations', methods=['POST'])
    @login_required
    @csrf_protect
    def api_create_or_resume_conversation(item_id):
        item, error_response = get_item_or_404(item_id)
        if error_response:
            return error_response

        if current_user.id == item.seller_id:
            return jsonify({'success': False, 'error': 'Sellers cannot create a chat with themselves'}), 400

        data = request.get_json(silent=True) or {}
        message_body = data.get('message', '').strip()
        if message_body and len(message_body) > MAX_MESSAGE_LENGTH:
            return jsonify({'success': False, 'error': f'Messages must be {MAX_MESSAGE_LENGTH} characters or fewer'}), 400

        conversation = Conversation.query.filter_by(item_id=item.id, buyer_id=current_user.id).first()
        if not conversation:
            conversation = Conversation(item_id=item.id, seller_id=item.seller_id, buyer_id=current_user.id)
            db.session.add(conversation)
            db.session.flush()

        if message_body:
            db.session.add(Message(conversation_id=conversation.id, sender_id=current_user.id, body=message_body))

        conversation.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Conversation ready',
            'conversation': serialize_conversation(conversation, viewer_id=current_user.id, include_messages=True),
        }), 200

    @app.route('/api/conversations', methods=['GET'])
    @login_required
    def api_get_conversations():
        conversations = (
            Conversation.query
            .filter(
                (Conversation.seller_id == current_user.id) |
                (Conversation.buyer_id == current_user.id)
            )
            .order_by(Conversation.updated_at.desc())
            .all()
        )

        return jsonify({
            'success': True,
            'conversations': [
                serialize_conversation(conversation, viewer_id=current_user.id)
                for conversation in conversations
            ],
        }), 200

    @app.route('/api/conversations/<int:conversation_id>', methods=['GET'])
    @login_required
    def api_get_conversation(conversation_id):
        conversation, error_response = get_conversation_or_404(conversation_id)
        if error_response:
            return error_response

        return jsonify({
            'success': True,
            'conversation': serialize_conversation(conversation, viewer_id=current_user.id, include_messages=True),
        }), 200

    @app.route('/api/conversations/<int:conversation_id>/messages', methods=['POST'])
    @login_required
    @csrf_protect
    def api_send_message(conversation_id):
        conversation, error_response = get_conversation_or_404(conversation_id)
        if error_response:
            return error_response

        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON'}), 400

        body = data.get('message', '').strip()
        if not body:
            return jsonify({'success': False, 'error': 'Message cannot be empty'}), 400

        if len(body) > MAX_MESSAGE_LENGTH:
            return jsonify({'success': False, 'error': f'Messages must be {MAX_MESSAGE_LENGTH} characters or fewer'}), 400

        message = Message(conversation_id=conversation.id, sender_id=current_user.id, body=body)
        conversation.updated_at = datetime.utcnow()
        db.session.add(message)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Message sent',
            'sent_message': serialize_message(message),
            'conversation': serialize_conversation(conversation, viewer_id=current_user.id, include_messages=True),
        }), 201

    @app.route('/api/constants', methods=['GET'])
    def api_constants():
        return jsonify({
            'success': True,
            'constants': {
                'categories': ITEM_CATEGORIES,
                'conditions': ITEM_CONDITIONS,
                'allowed_email_domain': UWA_STUDENT_DOMAIN,
                'chat_enabled': True,
            },
        }), 200

    return app


if __name__ == '__main__':
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    port = int(os.environ.get('PORT', 8000))
    app.run(debug=app.config.get('DEBUG', False), host='0.0.0.0', port=port)
