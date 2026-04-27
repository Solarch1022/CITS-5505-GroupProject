from datetime import datetime
from functools import wraps
import os
import secrets
import sys
from urllib.parse import urlparse

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from sqlalchemy import inspect, or_, text
from werkzeug.utils import secure_filename

sys.path.insert(0, os.path.dirname(__file__))

from config import config
from models import Conversation, Item, ItemImage, Message, Transaction, User, db


ITEM_CATEGORIES = ['Electronics', 'Furniture', 'Clothing', 'Books', 'Sports', 'Other']
ITEM_CONDITIONS = ['New', 'Like New', 'Good', 'Fair']
UWA_STUDENT_DOMAIN = '@student.uwa.edu.au'
MAX_MESSAGE_LENGTH = 600
MAX_IMAGES_PER_ITEM = 6
ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
DRAFT_TITLE_PLACEHOLDER = 'Untitled draft'


def is_valid_uwa_student_email(email):
    return email.lower().endswith(UWA_STUDENT_DOMAIN)


def format_timestamp(value):
    return value.strftime('%d %b %Y, %I:%M %p')


def is_safe_redirect_target(target):
    if not target:
        return False

    parsed = urlparse(target)
    return not parsed.netloc and parsed.path.startswith('/') and not parsed.path.startswith('//')


def create_app(config_name='development'):
    """Application factory."""
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config[config_name])

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login_page'

    upload_root = os.path.join(app.static_folder, 'uploads', 'items')
    os.makedirs(upload_root, exist_ok=True)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Unauthorized. Please login first.'}), 401

        next_target = request.full_path if request.query_string else request.path
        flash('Please login first.', 'error')
        return redirect(url_for('login_page', next=next_target))

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

    def normalize_uploaded_files(uploaded_files):
        return [uploaded_file for uploaded_file in uploaded_files if uploaded_file and uploaded_file.filename]

    def is_allowed_image_filename(filename):
        extension = os.path.splitext(filename)[1].lower()
        return extension in ALLOWED_IMAGE_EXTENSIONS

    def remove_saved_files(saved_paths):
        for saved_path in saved_paths:
            if os.path.exists(saved_path):
                os.remove(saved_path)

        visited_dirs = set()
        for saved_path in saved_paths:
            parent_dir = os.path.dirname(saved_path)
            if parent_dir and parent_dir not in visited_dirs and os.path.isdir(parent_dir):
                visited_dirs.add(parent_dir)
                if not os.listdir(parent_dir):
                    os.rmdir(parent_dir)

    def get_absolute_upload_path(relative_path):
        return os.path.join(app.static_folder, *relative_path.split('/'))

    def get_item_saved_paths(item):
        return [get_absolute_upload_path(image.file_path) for image in item.images]

    def delete_item_and_assets(item):
        saved_paths = get_item_saved_paths(item)
        db.session.delete(item)
        db.session.commit()
        remove_saved_files(saved_paths)

    def ensure_schema_supports_drafts():
        inspector = inspect(db.engine)
        if 'items' not in inspector.get_table_names():
            return

        column_names = {column['name'] for column in inspector.get_columns('items')}
        if 'is_draft' in column_names:
            return

        with db.engine.begin() as connection:
            connection.execute(text('ALTER TABLE items ADD COLUMN is_draft BOOLEAN NOT NULL DEFAULT 0'))

    def save_item_images(item, image_files):
        image_records = []
        saved_paths = []
        item_upload_dir = os.path.join(upload_root, str(item.id))
        os.makedirs(item_upload_dir, exist_ok=True)

        for sort_order, image_file in enumerate(image_files):
            original_filename = image_file.filename or ''
            if not is_allowed_image_filename(original_filename):
                allowed_formats = ', '.join(sorted(ext.lstrip('.') for ext in ALLOWED_IMAGE_EXTENSIONS))
                raise ValueError(f'Only {allowed_formats} image files are supported')

            extension = os.path.splitext(original_filename)[1].lower()
            safe_stem = secure_filename(os.path.splitext(original_filename)[0])[:48] or 'item-image'
            generated_name = f'{sort_order + 1}-{secrets.token_hex(8)}-{safe_stem}{extension}'
            absolute_path = os.path.join(item_upload_dir, generated_name)
            image_file.save(absolute_path)
            saved_paths.append(absolute_path)

            relative_path = '/'.join(['uploads', 'items', str(item.id), generated_name])
            image_records.append(ItemImage(
                item_id=item.id,
                file_path=relative_path,
                sort_order=sort_order,
            ))

        return image_records, saved_paths

    def csrf_failure():
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Invalid CSRF token'}), 403

        flash('Your session expired. Please try again.', 'error')
        return redirect(request.referrer or url_for('index'))

    def csrf_protect(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if request.method in {'GET', 'HEAD', 'OPTIONS'}:
                return view(*args, **kwargs)

            expected = ensure_csrf_token()
            provided = request.headers.get('X-CSRF-Token')

            if not provided:
                provided = request.form.get('csrf_token')

            if not provided and request.is_json:
                payload = request.get_json(silent=True) or {}
                provided = payload.get('csrf_token')

            if not provided or provided != expected:
                return csrf_failure()

            return view(*args, **kwargs)

        return wrapped

    def get_user_reputation(user):
        completed_sales = Transaction.query.filter_by(seller_id=user.id, status='completed').count()
        completed_purchases = Transaction.query.filter_by(buyer_id=user.id, status='completed').count()
        active_listings = Item.query.filter_by(seller_id=user.id, is_sold=False, is_draft=False).count()
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
        title = item.title.strip() if item.title else ''
        description = item.description or ''
        image_payload = [
            {
                'id': image.id,
                'url': url_for('static', filename=image.file_path),
                'sort_order': image.sort_order,
            }
            for image in item.images
        ]
        payload = {
            'id': item.id,
            'title': title or DRAFT_TITLE_PLACEHOLDER,
            'raw_title': title,
            'price': item.price,
            'category': item.category,
            'condition': item.condition,
            'is_draft': item.is_draft,
            'is_sold': item.is_sold,
            'status_label': 'Draft' if item.is_draft else ('Sold' if item.is_sold else 'Active'),
            'created_at': item.created_at.isoformat(),
            'created_at_display': format_timestamp(item.created_at),
            'seller': serialize_user(item.seller),
            'images': image_payload,
            'primary_image_url': image_payload[0]['url'] if image_payload else None,
            'description_preview': description[:90] + '...' if len(description) > 90 else (description or 'No description yet.'),
        }
        if include_description:
            payload['description'] = description
        return payload

    def serialize_message(message):
        return {
            'id': message.id,
            'body': message.body,
            'created_at': message.created_at.isoformat(),
            'created_at_display': format_timestamp(message.created_at),
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
            'created_at_display': format_timestamp(conversation.created_at),
            'updated_at': conversation.updated_at.isoformat(),
            'updated_at_display': format_timestamp(conversation.updated_at),
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

    def get_filtered_item_query(category='', search='', include_sold=False):
        query = Item.query
        query = query.filter_by(is_draft=False)
        if not include_sold:
            query = query.filter_by(is_sold=False)
        if category:
            query = query.filter_by(category=category)
        if search:
            query = query.filter(
                or_(
                    Item.title.ilike(f'%{search}%'),
                    Item.description.ilike(f'%{search}%'),
                )
            )
        return query

    def build_dashboard_payload(user):
        user_items = (
            Item.query
            .filter_by(seller_id=user.id, is_draft=False)
            .order_by(Item.created_at.desc())
            .all()
        )
        drafts = (
            Item.query
            .filter_by(seller_id=user.id, is_draft=True)
            .order_by(Item.updated_at.desc(), Item.created_at.desc())
            .all()
        )
        purchases = Transaction.query.filter_by(buyer_id=user.id).order_by(Transaction.created_at.desc()).all()
        sales = Transaction.query.filter_by(seller_id=user.id).order_by(Transaction.created_at.desc()).all()

        return {
            'user': serialize_user(user, include_email=True),
            'listings': [serialize_item(item) for item in user_items],
            'drafts': [serialize_item(item) for item in drafts],
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
                    'created_at_display': format_timestamp(transaction.created_at),
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
                    'created_at_display': format_timestamp(transaction.created_at),
                }
                for transaction in sales
            ],
        }

    def select_active_conversation(conversations, requested_id):
        if not conversations:
            return None

        if requested_id:
            for conversation in conversations:
                if conversation.id == requested_id:
                    return conversation

        return conversations[0]

    def get_item_or_none(item_id):
        return db.session.get(Item, item_id)

    def get_item_or_json_404(item_id):
        item = get_item_or_none(item_id)
        if not item:
            return None, (jsonify({'success': False, 'error': 'Item not found'}), 404)
        return item, None

    def get_owned_item_or_404(item_id, *, allow_sold=False):
        item = get_item_or_none(item_id)
        if not item or item.seller_id != current_user.id:
            abort(404)

        if item.is_sold and not allow_sold:
            flash('Sold listings can no longer be edited.', 'error')
            return None

        return item

    def get_conversation_or_none(conversation_id):
        conversation = db.session.get(Conversation, conversation_id)
        if not conversation:
            return None

        if not current_user.is_authenticated:
            return None

        if current_user.id not in {conversation.seller_id, conversation.buyer_id}:
            return None

        return conversation

    def get_conversation_or_json_error(conversation_id):
        conversation = db.session.get(Conversation, conversation_id)
        if not conversation:
            return None, (jsonify({'success': False, 'error': 'Conversation not found'}), 404)

        if current_user.id not in {conversation.seller_id, conversation.buyer_id}:
            return None, (jsonify({'success': False, 'error': 'Forbidden'}), 403)

        return conversation, None

    def resolve_item_chat_context(item):
        chat_context = {
            'viewer_mode': 'anonymous',
            'conversation_summaries': [],
            'active_conversation': None,
        }

        if not current_user.is_authenticated:
            return chat_context

        if current_user.id == item.seller_id:
            conversations = (
                Conversation.query
                .filter_by(item_id=item.id)
                .order_by(Conversation.updated_at.desc())
                .all()
            )
            active = select_active_conversation(conversations, request.args.get('conversation', type=int))
            chat_context['viewer_mode'] = 'seller'
            chat_context['conversation_summaries'] = [
                serialize_conversation(conversation, viewer_id=current_user.id)
                for conversation in conversations
            ]
            chat_context['active_conversation'] = (
                serialize_conversation(active, viewer_id=current_user.id, include_messages=True)
                if active else None
            )
            return chat_context

        conversation = Conversation.query.filter_by(item_id=item.id, buyer_id=current_user.id).first()
        chat_context['viewer_mode'] = 'buyer'
        chat_context['active_conversation'] = (
            serialize_conversation(conversation, viewer_id=current_user.id, include_messages=True)
            if conversation else None
        )
        return chat_context

    def resolve_dashboard_context(user):
        dashboard = build_dashboard_payload(user)
        conversations = (
            Conversation.query
            .filter(
                or_(
                    Conversation.seller_id == user.id,
                    Conversation.buyer_id == user.id,
                )
            )
            .order_by(Conversation.updated_at.desc())
            .all()
        )
        active = select_active_conversation(conversations, request.args.get('conversation', type=int))
        return {
            'dashboard': dashboard,
            'conversation_summaries': [
                serialize_conversation(conversation, viewer_id=user.id)
                for conversation in conversations
            ],
            'active_conversation': (
                serialize_conversation(active, viewer_id=user.id, include_messages=True)
                if active else None
            ),
        }

    def build_listing_form_data(item=None, overrides=None):
        price_value = ''
        if item and not (item.is_draft and item.price == 0):
            price_value = item.price

        form_data = {
            'title': item.title if item else '',
            'description': item.description if item else '',
            'price': price_value,
            'category': item.category if item else '',
            'condition': item.condition if item else '',
        }

        if overrides:
            for key, value in overrides.items():
                form_data[key] = value

        return form_data

    def create_user_account(username, email, password, full_name):
        username = username.strip()
        email = email.strip().lower()
        full_name = full_name.strip()

        if not username or not email or not password or not full_name:
            return None, 'All fields are required', 400

        if len(username) < 3:
            return None, 'Username must be at least 3 characters', 400

        if len(password) < 6:
            return None, 'Password must be at least 6 characters', 400

        if not is_valid_uwa_student_email(email):
            return None, 'Only verified UWA student emails are allowed. Use your @student.uwa.edu.au address.', 400

        if User.query.filter_by(username=username).first():
            return None, 'Username already exists', 400

        if User.query.filter_by(email=email).first():
            return None, 'Email already exists', 400

        user = User(username=username, email=email, full_name=full_name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user, None, 201

    def authenticate_user(username, password):
        username = username.strip()

        if not username or not password:
            return None, 'Username and password required', 400

        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            return None, 'Invalid username or password', 401

        return user, None, 200

    def normalize_listing_payload(title, description, price, category, condition, *, allow_partial):
        title = title.strip()
        description = description.strip()
        category = category.strip()
        condition = condition.strip()

        if allow_partial:
            if category and category not in ITEM_CATEGORIES:
                return None, 'Invalid category', 400
            if condition and condition not in ITEM_CONDITIONS:
                return None, 'Invalid condition', 400

            if price in (None, ''):
                price_value = 0.0
            else:
                try:
                    price_value = float(price)
                    if price_value < 0:
                        raise ValueError
                except (TypeError, ValueError):
                    return None, 'Draft price must be a valid number', 400

            return {
                'title': title,
                'description': description,
                'price': price_value,
                'category': category,
                'condition': condition,
            }, None, 200

        if not all([title, description, price, category, condition]):
            return None, 'All fields are required to publish a listing', 400

        if len(title) < 4:
            return None, 'Item title must be at least 4 characters', 400

        if len(description) < 15:
            return None, 'Description should be at least 15 characters', 400

        if category not in ITEM_CATEGORIES:
            return None, 'Invalid category', 400

        if condition not in ITEM_CONDITIONS:
            return None, 'Invalid condition', 400

        try:
            price_value = float(price)
            if price_value <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return None, 'Price must be a positive number', 400

        return {
            'title': title,
            'description': description,
            'price': price_value,
            'category': category,
            'condition': condition,
        }, None, 200

    def save_listing(item, title, description, price, category, condition, seller, image_files, *, publish):
        image_files = image_files or []

        normalized, error, status = normalize_listing_payload(
            title,
            description,
            price,
            category,
            condition,
            allow_partial=not publish,
        )
        if error:
            return None, error, status

        if len(image_files) > MAX_IMAGES_PER_ITEM:
            return None, f'You can upload up to {MAX_IMAGES_PER_ITEM} images per listing', 400

        is_new = item is None
        if item is None:
            item = Item(seller_id=seller.id)
        elif item.seller_id != seller.id:
            return None, 'You cannot edit this listing', 403

        if item.is_sold:
            return None, 'Sold listings can no longer be edited', 400

        new_saved_paths = []
        old_saved_paths = []
        try:
            item.title = normalized['title']
            item.description = normalized['description']
            item.price = normalized['price']
            item.category = normalized['category']
            item.condition = normalized['condition']
            item.is_draft = not publish

            if is_new:
                db.session.add(item)
                db.session.flush()

            if image_files:
                old_saved_paths = get_item_saved_paths(item)
                for existing_image in list(item.images):
                    db.session.delete(existing_image)

                image_records, new_saved_paths = save_item_images(item, image_files)
                db.session.add_all(image_records)

            db.session.commit()
            if old_saved_paths:
                remove_saved_files(old_saved_paths)
            return item, None, 201 if is_new else 200
        except ValueError as error:
            db.session.rollback()
            remove_saved_files(new_saved_paths)
            return None, str(error), 400
        except OSError:
            db.session.rollback()
            remove_saved_files(new_saved_paths)
            return None, 'Uploaded images could not be saved', 500

    def complete_purchase(item, buyer):
        if item.is_draft:
            return None, 'Draft listings cannot be purchased', 400

        if item.is_sold:
            return None, 'Item already sold', 400

        if item.seller_id == buyer.id:
            return None, 'Cannot buy your own item', 400

        transaction = Transaction(
            item_id=item.id,
            seller_id=item.seller_id,
            buyer_id=buyer.id,
            price=item.price,
            status='completed',
        )

        item.is_sold = True
        db.session.add(transaction)
        db.session.commit()
        return transaction, None, 200

    def create_or_resume_conversation(item, buyer, message_body=''):
        if item.is_draft:
            return None, 'Draft listings are not visible to buyers yet', 400

        if item.is_sold:
            return None, 'Sold listings cannot receive new enquiries', 400

        if buyer.id == item.seller_id:
            return None, 'Sellers cannot create a chat with themselves', 400

        message_body = message_body.strip()
        if message_body and len(message_body) > MAX_MESSAGE_LENGTH:
            return None, f'Messages must be {MAX_MESSAGE_LENGTH} characters or fewer', 400

        conversation = Conversation.query.filter_by(item_id=item.id, buyer_id=buyer.id).first()
        if not conversation:
            conversation = Conversation(item_id=item.id, seller_id=item.seller_id, buyer_id=buyer.id)
            db.session.add(conversation)
            db.session.flush()

        if message_body:
            db.session.add(Message(conversation_id=conversation.id, sender_id=buyer.id, body=message_body))

        conversation.updated_at = datetime.utcnow()
        db.session.commit()
        return conversation, None, 200

    def send_conversation_message(conversation, sender, body):
        body = body.strip()
        if not body:
            return None, 'Message cannot be empty', 400

        if len(body) > MAX_MESSAGE_LENGTH:
            return None, f'Messages must be {MAX_MESSAGE_LENGTH} characters or fewer', 400

        message = Message(conversation_id=conversation.id, sender_id=sender.id, body=body)
        conversation.updated_at = datetime.utcnow()
        db.session.add(message)
        db.session.commit()
        return message, None, 201

    def logout_current_session():
        if current_user.is_authenticated:
            logout_user()
        session.clear()
        return rotate_csrf_token()

    @app.before_request
    def bootstrap_session():
        ensure_csrf_token()

    @app.context_processor
    def inject_template_globals():
        return {
            'csrf_token': ensure_csrf_token(),
            'item_categories': ITEM_CATEGORIES,
            'item_conditions': ITEM_CONDITIONS,
            'uwa_student_domain': UWA_STUDENT_DOMAIN,
            'max_images_per_item': MAX_IMAGES_PER_ITEM,
            'current_year': datetime.utcnow().year,
        }

    with app.app_context():
        db.create_all()
        ensure_schema_supports_drafts()

    @app.route('/')
    def index():
        latest_items = (
            Item.query
            .filter_by(is_sold=False, is_draft=False)
            .order_by(Item.created_at.desc())
            .limit(6)
            .all()
        )
        return render_template('index.html', latest_items=[serialize_item(item) for item in latest_items])

    @app.route('/app')
    def legacy_app_redirect():
        return redirect(url_for('index'))

    @app.route('/browse')
    @app.route('/items')
    def browse_items():
        category = request.args.get('category', '').strip()
        search = request.args.get('search', '').strip()
        query = get_filtered_item_query(category=category, search=search)
        items = query.order_by(Item.created_at.desc()).all()
        return render_template(
            'items.html',
            items=[serialize_item(item) for item in items],
            filters={'category': category, 'search': search},
            total=len(items),
        )

    @app.route('/login', methods=['GET', 'POST'])
    @csrf_protect
    def login_page():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard_page'))

        next_url = request.args.get('next', '')
        if request.method == 'POST':
            next_url = request.form.get('next', '')
            user, error, status = authenticate_user(
                request.form.get('username', ''),
                request.form.get('password', ''),
            )
            if error:
                flash(error, 'error')
                return render_template('login.html', next_url=next_url, form_data=request.form.to_dict()), status

            login_user(user)
            flash('Login successful.', 'success')
            if is_safe_redirect_target(next_url):
                return redirect(next_url)
            return redirect(url_for('dashboard_page'))

        return render_template('login.html', next_url=next_url, form_data={})

    @app.route('/register', methods=['GET', 'POST'])
    @csrf_protect
    def register_page():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard_page'))

        if request.method == 'POST':
            user, error, status = create_user_account(
                request.form.get('username', ''),
                request.form.get('email', ''),
                request.form.get('password', ''),
                request.form.get('full_name', ''),
            )
            if error:
                flash(error, 'error')
                return render_template('register.html', form_data=request.form.to_dict()), status

            flash('Registration successful. Please login with your new account.', 'success')
            return redirect(url_for('login_page', username=user.username))

        return render_template('register.html', form_data={})

    @app.route('/logout', methods=['POST'])
    @csrf_protect
    def logout_page():
        logout_current_session()
        flash('Logged out.', 'success')
        return redirect(url_for('index'))

    @app.route('/sell', methods=['GET', 'POST'])
    @login_required
    @csrf_protect
    def sell_item_page():
        if request.method == 'POST':
            publish = request.form.get('intent', 'publish') == 'publish'
            item, error, status = save_listing(
                None,
                request.form.get('title', ''),
                request.form.get('description', ''),
                request.form.get('price', ''),
                request.form.get('category', ''),
                request.form.get('condition', ''),
                current_user,
                normalize_uploaded_files(request.files.getlist('images')),
                publish=publish,
            )
            if error:
                flash(error, 'error')
                return render_template(
                    'sell_item.html',
                    form_data=request.form.to_dict(),
                    listing=None,
                    is_edit_mode=False,
                ), status

            if publish:
                flash('Item listed successfully.', 'success')
                return redirect(url_for('item_detail_page', item_id=item.id))

            flash('Draft saved to your draft box.', 'success')
            return redirect(url_for('dashboard_page') + '#drafts')

        return render_template('sell_item.html', form_data={}, listing=None, is_edit_mode=False)

    @app.route('/sell/<int:item_id>/edit', methods=['GET', 'POST'])
    @login_required
    @csrf_protect
    def edit_listing_page(item_id):
        item = get_owned_item_or_404(item_id)
        if item is None:
            return redirect(url_for('dashboard_page'))

        if request.method == 'POST':
            publish = request.form.get('intent', 'publish') == 'publish'
            updated_item, error, status = save_listing(
                item,
                request.form.get('title', ''),
                request.form.get('description', ''),
                request.form.get('price', ''),
                request.form.get('category', ''),
                request.form.get('condition', ''),
                current_user,
                normalize_uploaded_files(request.files.getlist('images')),
                publish=publish,
            )
            if error:
                flash(error, 'error')
                return render_template(
                    'sell_item.html',
                    form_data=request.form.to_dict(),
                    listing=serialize_item(item),
                    is_edit_mode=True,
                ), status

            if publish:
                flash('Listing updated and published.', 'success')
                return redirect(url_for('item_detail_page', item_id=updated_item.id))

            flash('Draft updated.', 'success')
            return redirect(url_for('dashboard_page') + '#drafts')

        return render_template(
            'sell_item.html',
            form_data=build_listing_form_data(item),
            listing=serialize_item(item),
            is_edit_mode=True,
        )

    @app.route('/listings/<int:item_id>/unlist', methods=['POST'])
    @login_required
    @csrf_protect
    def unlist_listing_page(item_id):
        item = get_owned_item_or_404(item_id, allow_sold=True)
        if item is None:
            return redirect(url_for('dashboard_page'))

        if item.is_draft:
            flash('This listing is already in your draft box.', 'error')
            return redirect(url_for('dashboard_page') + '#drafts')

        if item.is_sold:
            flash('Sold listings cannot be moved back to drafts or deleted.', 'error')
            return redirect(url_for('dashboard_page'))

        decision = request.form.get('decision', '').strip().lower()
        if decision == 'draft':
            item.is_draft = True
            db.session.commit()
            flash('Listing moved to your draft box.', 'success')
            return redirect(url_for('dashboard_page') + '#drafts')

        if decision == 'delete':
            delete_item_and_assets(item)
            flash('Listing deleted permanently.', 'success')
            return redirect(url_for('dashboard_page'))

        flash('Choose whether to move the listing into drafts or delete it.', 'error')
        return redirect(url_for('dashboard_page'))

    @app.route('/listings/<int:item_id>/delete', methods=['POST'])
    @login_required
    @csrf_protect
    def delete_listing_page(item_id):
        item = get_owned_item_or_404(item_id, allow_sold=True)
        if item is None:
            return redirect(url_for('dashboard_page'))

        if item.is_sold:
            flash('Sold listings cannot be deleted.', 'error')
            return redirect(url_for('dashboard_page'))

        delete_item_and_assets(item)
        flash('Listing deleted permanently.', 'success')
        return redirect(url_for('dashboard_page'))

    @app.route('/purchase/<int:item_id>', methods=['POST'])
    @login_required
    @csrf_protect
    def purchase_page(item_id):
        item = get_item_or_none(item_id)
        if not item:
            abort(404)

        transaction, error, _ = complete_purchase(item, current_user)
        if error:
            flash(error, 'error')
            return redirect(url_for('item_detail_page', item_id=item.id))

        flash(f'Purchase completed for {transaction.item.title}.', 'success')
        return redirect(url_for('dashboard_page'))

    @app.route('/item/<int:item_id>')
    def item_detail_page(item_id):
        item = get_item_or_none(item_id)
        if not item:
            abort(404)

        if item.is_draft:
            if not current_user.is_authenticated or current_user.id != item.seller_id:
                abort(404)

            flash('This listing is currently saved as a draft. Edit it to publish or continue working on it.', 'error')
            return redirect(url_for('edit_listing_page', item_id=item.id))

        return render_template(
            'item_detail.html',
            item=serialize_item(item),
            chat=resolve_item_chat_context(item),
        )

    @app.route('/item/<int:item_id>/conversation', methods=['POST'])
    @login_required
    @csrf_protect
    def item_conversation_page(item_id):
        item = get_item_or_none(item_id)
        if not item:
            abort(404)

        conversation, error, _ = create_or_resume_conversation(
            item,
            current_user,
            request.form.get('message', ''),
        )
        if error:
            flash(error, 'error')
            return redirect(url_for('item_detail_page', item_id=item.id) + '#chat')

        flash('Conversation ready.', 'success')
        return redirect(url_for('item_detail_page', item_id=item.id, conversation=conversation.id) + '#chat')

    @app.route('/conversations/<int:conversation_id>/reply', methods=['POST'])
    @login_required
    @csrf_protect
    def conversation_reply_page(conversation_id):
        conversation = get_conversation_or_none(conversation_id)
        if not conversation:
            flash('Conversation could not be found.', 'error')
            return redirect(url_for('dashboard_page'))

        _, error, _ = send_conversation_message(conversation, current_user, request.form.get('message', ''))
        if error:
            flash(error, 'error')
        else:
            flash('Message sent.', 'success')

        next_url = request.form.get('next', '')
        if is_safe_redirect_target(next_url):
            return redirect(next_url)

        if conversation.item.seller_id == current_user.id:
            return redirect(url_for('item_detail_page', item_id=conversation.item.id, conversation=conversation.id) + '#chat')
        return redirect(url_for('dashboard_page', conversation=conversation.id) + '#inbox')

    @app.route('/dashboard')
    @login_required
    def dashboard_page():
        return render_template('dashboard.html', **resolve_dashboard_context(current_user))

    @app.route('/profile')
    @login_required
    def profile_page():
        return render_template('profile.html', user=current_user)

    @app.route('/api/auth/register', methods=['POST'])
    @csrf_protect
    def api_auth_register():
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON'}), 400

        user, error, status = create_user_account(
            data.get('username', ''),
            data.get('email', ''),
            data.get('password', ''),
            data.get('full_name', ''),
        )
        if error:
            return jsonify({'success': False, 'error': error}), status

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

        user, error, status = authenticate_user(
            data.get('username', ''),
            data.get('password', ''),
        )
        if error:
            return jsonify({'success': False, 'error': error}), status

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
        csrf_token = logout_current_session()
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

        query = get_filtered_item_query(category=category, search=search, include_sold=include_sold)
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
        item, error_response = get_item_or_json_404(item_id)
        if error_response:
            return error_response

        if item.is_draft and (not current_user.is_authenticated or current_user.id != item.seller_id):
            return jsonify({'success': False, 'error': 'Item not found'}), 404

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
        image_files = []
        if request.is_json:
            data = request.get_json(silent=True)
        else:
            data = request.form.to_dict()
            image_files = normalize_uploaded_files(request.files.getlist('images'))

        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON'}), 400

        item, error, status = save_listing(
            None,
            data.get('title', ''),
            data.get('description', ''),
            data.get('price', ''),
            data.get('category', ''),
            data.get('condition', ''),
            current_user,
            image_files,
            publish=True,
        )
        if error:
            return jsonify({'success': False, 'error': error}), status

        return jsonify({
            'success': True,
            'message': 'Item listed successfully',
            'item': serialize_item(item),
        }), 201

    @app.route('/api/purchase/<int:item_id>', methods=['POST'])
    @login_required
    @csrf_protect
    def api_purchase(item_id):
        item, error_response = get_item_or_json_404(item_id)
        if error_response:
            return error_response

        transaction, error, status = complete_purchase(item, current_user)
        if error:
            return jsonify({'success': False, 'error': error}), status

        return jsonify({
            'success': True,
            'message': 'Purchase completed successfully',
            'transaction': {
                'id': transaction.id,
                'item_id': transaction.item_id,
                'price': transaction.price,
                'status': transaction.status,
                'created_at': transaction.created_at.isoformat(),
                'created_at_display': format_timestamp(transaction.created_at),
            },
        }), 200

    @app.route('/api/dashboard', methods=['GET'])
    @login_required
    def api_dashboard():
        return jsonify({
            'success': True,
            'dashboard': build_dashboard_payload(current_user),
        }), 200

    @app.route('/api/items/<int:item_id>/conversation', methods=['GET'])
    @login_required
    def api_get_item_conversation(item_id):
        item, error_response = get_item_or_json_404(item_id)
        if error_response:
            return error_response

        if item.is_draft:
            return jsonify({'success': False, 'error': 'Draft listings do not have conversations'}), 400

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
        item, error_response = get_item_or_json_404(item_id)
        if error_response:
            return error_response

        data = request.get_json(silent=True) or {}
        conversation, error, status = create_or_resume_conversation(item, current_user, data.get('message', ''))
        if error:
            return jsonify({'success': False, 'error': error}), status

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
                or_(
                    Conversation.seller_id == current_user.id,
                    Conversation.buyer_id == current_user.id,
                )
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
        conversation, error_response = get_conversation_or_json_error(conversation_id)
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
        conversation, error_response = get_conversation_or_json_error(conversation_id)
        if error_response:
            return error_response

        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON'}), 400

        message, error, status = send_conversation_message(conversation, current_user, data.get('message', ''))
        if error:
            return jsonify({'success': False, 'error': error}), status

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
                'max_images_per_item': MAX_IMAGES_PER_ITEM,
            },
        }), 200

    return app


if __name__ == '__main__':
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    port = int(os.environ.get('PORT', 8000))
    app.run(debug=app.config.get('DEBUG', False), host='0.0.0.0', port=port)
