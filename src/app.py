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
from models import Conversation, Item, ItemImage, Message, PaymentMethod, Referral, Transaction, User, Wallet, WalletEntry, CartItem, db


ITEM_CATEGORIES = ['Electronics', 'Furniture', 'Clothing', 'Books', 'Sports', 'Other']
ITEM_CONDITIONS = ['New', 'Like New', 'Good', 'Fair']
UWA_STUDENT_DOMAIN = '@student.uwa.edu.au'
MAX_MESSAGE_LENGTH = 600
MAX_IMAGES_PER_ITEM = 6
ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
DRAFT_TITLE_PLACEHOLDER = 'Untitled draft'
MAX_WALLET_ACTIVITY = 8
MIN_TOP_UP_AMOUNT = 5.0
MAX_TOP_UP_AMOUNT = 2000.0
MIN_WITHDRAWAL_AMOUNT = 5.0
WITHDRAWAL_FEE_RATE = 0.02
WITHDRAWAL_FEE_MINIMUM = 0.50
REFERRAL_REWARD_AMOUNT = 5.0
REFERRAL_REQUIRED_COMPLETED_TRADES = 3
REFERRAL_REQUIRED_REPUTATION = 4.0


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

    def ensure_schema_supports_referrals():
        inspector = inspect(db.engine)
        table_names = inspector.get_table_names()

        if 'users' in table_names:
            user_columns = {column['name'] for column in inspector.get_columns('users')}
            with db.engine.begin() as connection:
                if 'referral_code' not in user_columns:
                    connection.execute(text('ALTER TABLE users ADD COLUMN referral_code VARCHAR(20)'))

        if 'referrals' not in table_names:
            Referral.__table__.create(db.engine)

    def ensure_schema_supports_inventory():
        inspector = inspect(db.engine)
        table_names = inspector.get_table_names()

        with db.engine.begin() as connection:
            if 'items' in table_names:
                item_columns = {column['name'] for column in inspector.get_columns('items')}
                if 'quantity' not in item_columns:
                    connection.execute(text('ALTER TABLE items ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1'))

            if 'transactions' in table_names:
                transaction_columns = {column['name'] for column in inspector.get_columns('transactions')}
                if 'quantity_bought' not in transaction_columns:
                    connection.execute(text('ALTER TABLE transactions ADD COLUMN quantity_bought INTEGER NOT NULL DEFAULT 1'))
    

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

    def round_money(value):
        return round(float(value or 0) + 1e-9, 2)

    def format_money(value):
        return f'{round_money(value):.2f}'

    def calculate_withdrawal_fee(amount):
        return round_money(max(WITHDRAWAL_FEE_MINIMUM, amount * WITHDRAWAL_FEE_RATE))

    def get_or_create_wallet(user, *, commit=False):
        wallet = Wallet.query.filter_by(user_id=user.id).first()
        if wallet:
            return wallet

        wallet = Wallet(user_id=user.id, available_balance=0.0)
        db.session.add(wallet)
        db.session.flush()
        if commit:
            db.session.commit()
        return wallet

    def ensure_existing_users_have_wallets():
        user_ids_with_wallets = {wallet_user_id for wallet_user_id, in db.session.query(Wallet.user_id).all()}
        missing_wallets = []
        for user in User.query.all():
            if user.id not in user_ids_with_wallets:
                missing_wallets.append(Wallet(user_id=user.id, available_balance=0.0))

        if missing_wallets:
            db.session.add_all(missing_wallets)
            db.session.commit()

    def ensure_admin_account_exists():
        admin_user = User.query.filter_by(username='admin').first()
        if admin_user:
            return

        admin = User(
            username='admin',
            email='admin@localhost',
            full_name='Administrator'
        )
        admin.set_password('123456')
        db.session.add(admin)
        db.session.flush()
        
        wallet = Wallet(user_id=admin.id, available_balance=0.0)
        db.session.add(wallet)
        db.session.commit()

    def record_wallet_entry(wallet, entry_type, amount, description, *, payment_method=None, transaction=None):
        entry = WalletEntry(
            user_id=wallet.user_id,
            payment_method_id=payment_method.id if payment_method else None,
            transaction_id=transaction.id if transaction else None,
            entry_type=entry_type,
            amount=round_money(amount),
            balance_after=round_money(wallet.available_balance),
            description=description,
        )
        db.session.add(entry)
        return entry

    def get_user_payment_methods(user):
        methods = PaymentMethod.query.filter_by(user_id=user.id).order_by(
            PaymentMethod.is_default.desc(),
            PaymentMethod.created_at.desc(),
        ).all()
        return methods

    def get_default_payment_method(user):
        return (
            PaymentMethod.query
            .filter_by(user_id=user.id, is_default=True)
            .order_by(PaymentMethod.created_at.desc())
            .first()
        )

    def resolve_payment_method(user, payment_method_id):
        if payment_method_id:
            method = db.session.get(PaymentMethod, payment_method_id)
            if method and method.user_id == user.id:
                return method
            return None

        default_method = get_default_payment_method(user)
        if default_method:
            return default_method

        methods = get_user_payment_methods(user)
        return methods[0] if methods else None

    def mask_payment_number(raw_number):
        digits_only = ''.join(character for character in raw_number if character.isdigit())
        if len(digits_only) < 8:
            return None, None
        return digits_only[-4:], f'•••• {digits_only[-4:]}'

    def add_payment_method(user, provider_name, account_holder, account_number, *, make_default=False):
        provider_name = provider_name.strip()
        account_holder = account_holder.strip()
        last_four, masked_suffix = mask_payment_number(account_number)

        if not provider_name or not account_holder or not last_four:
            return None, 'Provider, cardholder name, and a valid bank card number are required.', 400

        should_be_default = make_default or not PaymentMethod.query.filter_by(user_id=user.id).count()
        if should_be_default:
            PaymentMethod.query.filter_by(user_id=user.id, is_default=True).update({'is_default': False})

        method = PaymentMethod(
            user_id=user.id,
            provider_name=provider_name,
            account_holder=account_holder,
            masked_details=f'{provider_name} {masked_suffix}',
            last_four=last_four,
            method_type='bank_card',
            is_default=should_be_default,
        )
        db.session.add(method)
        db.session.commit()
        return method, None, 201

    def top_up_wallet(user, payment_method_id, amount_raw):
        method = resolve_payment_method(user, payment_method_id)
        if not method:
            return None, None, 'Link a bank card before topping up your wallet.', 400

        try:
            amount = round_money(float(amount_raw))
        except (TypeError, ValueError):
            return None, None, 'Top-up amount must be a valid number.', 400

        if amount < MIN_TOP_UP_AMOUNT or amount > MAX_TOP_UP_AMOUNT:
            return None, None, f'Top-ups must be between ${format_money(MIN_TOP_UP_AMOUNT)} and ${format_money(MAX_TOP_UP_AMOUNT)}.', 400

        wallet = get_or_create_wallet(user)
        wallet.available_balance = round_money(wallet.available_balance + amount)
        entry = record_wallet_entry(
            wallet,
            'top_up',
            amount,
            f'Top-up from {method.masked_details}',
            payment_method=method,
        )
        db.session.commit()
        return wallet, entry, None, 200

    def withdraw_from_wallet(user, payment_method_id, amount_raw):
        method = resolve_payment_method(user, payment_method_id)
        if not method:
            return None, None, None, 'Link a bank card before requesting a withdrawal.', 400

        try:
            amount = round_money(float(amount_raw))
        except (TypeError, ValueError):
            return None, None, None, 'Withdrawal amount must be a valid number.', 400

        if amount < MIN_WITHDRAWAL_AMOUNT:
            return None, None, None, f'Withdrawals must be at least ${format_money(MIN_WITHDRAWAL_AMOUNT)}.', 400

        wallet = get_or_create_wallet(user)
        fee = calculate_withdrawal_fee(amount)
        total_deduction = round_money(amount + fee)
        if wallet.available_balance < total_deduction:
            return None, None, None, (
                f'Insufficient wallet balance. You need ${format_money(total_deduction)} '
                f'available to withdraw ${format_money(amount)} after the fee.'
            ), 400

        wallet.available_balance = round_money(wallet.available_balance - amount)
        withdrawal_entry = record_wallet_entry(
            wallet,
            'withdrawal',
            -amount,
            f'Withdrawal to {method.masked_details}',
            payment_method=method,
        )
        wallet.available_balance = round_money(wallet.available_balance - fee)
        fee_entry = record_wallet_entry(
            wallet,
            'withdrawal_fee',
            -fee,
            'Withdrawal processing fee',
            payment_method=method,
        )
        db.session.commit()
        return wallet, withdrawal_entry, fee_entry, None, 200

    def serialize_payment_method(method):
        return {
            'id': method.id,
            'provider_name': method.provider_name,
            'account_holder': method.account_holder,
            'masked_details': method.masked_details,
            'last_four': method.last_four,
            'method_type': method.method_type,
            'is_default': method.is_default,
            'created_at': method.created_at.isoformat(),
            'created_at_display': format_timestamp(method.created_at),
        }

    def serialize_wallet_entry(entry):
        amount = round_money(entry.amount)
        return {
            'id': entry.id,
            'entry_type': entry.entry_type,
            'description': entry.description,
            'amount': amount,
            'amount_display': format_money(amount),
            'amount_sign': '+' if amount > 0 else '-',
            'balance_after': round_money(entry.balance_after),
            'balance_after_display': format_money(entry.balance_after),
            'created_at': entry.created_at.isoformat(),
            'created_at_display': format_timestamp(entry.created_at),
            'payment_method': serialize_payment_method(entry.payment_method) if entry.payment_method else None,
        }

    def build_wallet_payload(user):
        wallet = get_or_create_wallet(user, commit=True)
        methods = get_user_payment_methods(user)
        entries = (
            WalletEntry.query
            .filter_by(user_id=user.id)
            .order_by(WalletEntry.created_at.desc())
            .limit(MAX_WALLET_ACTIVITY)
            .all()
        )
        return {
            'available_balance': round_money(wallet.available_balance),
            'available_balance_display': format_money(wallet.available_balance),
            'payment_methods': [serialize_payment_method(method) for method in methods],
            'default_payment_method_id': methods[0].id if methods else None,
            'recent_entries': [serialize_wallet_entry(entry) for entry in entries],
            'min_top_up_amount': MIN_TOP_UP_AMOUNT,
            'max_top_up_amount': MAX_TOP_UP_AMOUNT,
            'min_withdrawal_amount': MIN_WITHDRAWAL_AMOUNT,
            'withdrawal_fee_rate_percent': int(WITHDRAWAL_FEE_RATE * 100),
            'withdrawal_fee_minimum': WITHDRAWAL_FEE_MINIMUM,
            'sensitive_hidden_by_default': True,
        }

    def build_purchase_wallet_context(user, item_price):
        wallet = get_or_create_wallet(user, commit=True)
        balance = round_money(wallet.available_balance)
        item_total = round_money(item_price)
        return {
            'available_balance': balance,
            'available_balance_display': format_money(balance),
            'has_enough_funds': balance >= item_total,
            'shortfall': round_money(max(0, item_total - balance)),
            'shortfall_display': format_money(max(0, item_total - balance)),
            'linked_payment_methods': len(get_user_payment_methods(user)),
        }

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
    
    def is_referral_eligible(user):
        reputation = get_user_reputation(user)
        completed_trades = reputation['completed_sales'] + reputation['completed_purchases']

        return (
            completed_trades >= REFERRAL_REQUIRED_COMPLETED_TRADES
            or reputation['score'] >= REFERRAL_REQUIRED_REPUTATION
        )


    def generate_referral_code_for_user(user):
        if user.referral_code:
            return user.referral_code

        while True:
            code = f'UWA{secrets.token_hex(4).upper()}'
            existing_user = User.query.filter_by(referral_code=code).first()

            if not existing_user:
                user.referral_code = code
                db.session.commit()
                return code


    def apply_referral_reward(new_user, referral_code):
        if not referral_code:
            return

        code = referral_code.strip().upper()
        if not code:
            return

        referrer = User.query.filter_by(referral_code=code).first()

        if not referrer:
            return

        if referrer.id == new_user.id:
            return

        existing_referral = Referral.query.filter_by(referred_user_id=new_user.id).first()
        if existing_referral:
            return

        referrer_wallet = get_or_create_wallet(referrer)

        referrer_wallet.available_balance = round_money(
            referrer_wallet.available_balance + REFERRAL_REWARD_AMOUNT
        )

        referral = Referral(
            referrer_id=referrer.id,
            referred_user_id=new_user.id,
            referral_code=code,
            reward_amount=REFERRAL_REWARD_AMOUNT,
        )

        db.session.add(referral)

        record_wallet_entry(
            referrer_wallet,
            'referral_reward',
            REFERRAL_REWARD_AMOUNT,
            f'Referral reward for inviting {new_user.username}',
        )

        db.session.commit()

    def serialize_user(user, include_email=False):
        payload = {
            'id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'bio': user.bio or '',
            'is_uwa_verified': is_valid_uwa_student_email(user.email),
            'reputation': get_user_reputation(user),
            'referral_code': user.referral_code,
            'referral_eligible': is_referral_eligible(user),
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
            'quantity': item.quantity,
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
            'wallet': build_wallet_payload(user),
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

    def select_active_conversation(conversations, requested_id, *, default_to_first=True):
        if not conversations:
            return None

        if requested_id:
            for conversation in conversations:
                if conversation.id == requested_id:
                    return conversation

        return conversations[0] if default_to_first else None

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
        active = select_active_conversation(
            conversations,
            request.args.get('conversation', type=int),
            default_to_first=False,
        )
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
        db.session.flush()
        db.session.add(Wallet(user_id=user.id, available_balance=0.0))
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

    def normalize_listing_payload(title, description, price, category, condition, quantity, *, allow_partial):
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

            if quantity in (None, ''):
                quantity_value = 1
            else:
                try:
                    quantity_value = int(quantity)
                    if quantity_value < 1:
                        raise ValueError
                except (TypeError, ValueError):
                    return None, 'Draft quantity must be a positive number', 400

            return {
                'title': title,
                'description': description,
                'price': price_value,
                'category': category,
                'condition': condition,
                'quantity': quantity_value,
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

        if quantity in (None, ''):
            quantity_value = 1
        else:
            try:
                quantity_value = int(quantity)
                if quantity_value < 1:
                    raise ValueError
            except (TypeError, ValueError):
                return None, 'Quantity must be a positive number', 400

        return {
            'title': title,
            'description': description,
            'price': price_value,
            'category': category,
            'condition': condition,
            'quantity': quantity_value,
        }, None, 200

    def save_listing(item, title, description, price, category, condition, quantity, seller, image_files, *, publish):
        image_files = image_files or []

        normalized, error, status = normalize_listing_payload(
            title,
            description,
            price,
            category,
            condition,
            quantity,
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
            item.quantity = normalized['quantity']
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

    def complete_purchase(item, buyer, quantity=1):
        if item.is_draft:
            return None, 'Draft listings cannot be purchased', 400

        if item.quantity <= 0:
            return None, 'Item out of stock', 400

        if item.seller_id == buyer.id:
            return None, 'Cannot buy your own item', 400

        try:
            quantity = int(quantity)
            if quantity < 1:
                raise ValueError
        except (TypeError, ValueError):
            return None, 'Quantity must be a positive number', 400

        if quantity > item.quantity:
            return None, f'Only {item.quantity} item{"s" if item.quantity != 1 else ""} available in stock', 400

        buyer_wallet = get_or_create_wallet(buyer)
        seller_wallet = get_or_create_wallet(item.seller)
        item_price = round_money(item.price * quantity)
        if buyer_wallet.available_balance < item_price:
            shortfall = round_money(item_price - buyer_wallet.available_balance)
            return None, (
                f'Insufficient wallet balance. Top up ${format_money(shortfall)} more '
                'from your linked bank card before purchasing this item.'
            ), 400

        transaction = Transaction(
            item_id=item.id,
            seller_id=item.seller_id,
            buyer_id=buyer.id,
            price=item_price,
            quantity_bought=quantity,
            status='completed',
        )

        item.quantity -= quantity
        if item.quantity == 0:
            item.is_sold = True
        buyer_wallet.available_balance = round_money(buyer_wallet.available_balance - item_price)
        seller_wallet.available_balance = round_money(seller_wallet.available_balance + item_price)
        db.session.add(transaction)
        db.session.flush()
        record_wallet_entry(
            buyer_wallet,
            'purchase',
            -item_price,
            f'Purchased {quantity} unit{"s" if quantity != 1 else ""} of {item.title}',
            transaction=transaction,
        )
        record_wallet_entry(
            seller_wallet,
            'sale_proceeds',
            item_price,
            f'Sale proceeds held in wallet for {item.title}',
            transaction=transaction,
        )
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
        ensure_schema_supports_referrals()
        ensure_schema_supports_inventory()
        ensure_existing_users_have_wallets()
        ensure_admin_account_exists()

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

    @app.route('/cart')
    @login_required
    def cart_page():
        return render_template('cart.html')

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

            apply_referral_reward(user, request.form.get('referral_code', ''))

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
                request.form.get('quantity', ''),
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
                request.form.get('quantity', ''),
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

        quantity = request.form.get('quantity', '1')
        transaction, error, _ = complete_purchase(item, current_user, quantity=quantity)
        if error:
            flash(error, 'error')
            return redirect(url_for('item_detail_page', item_id=item.id))

        flash(
            f'Purchase completed for {transaction.quantity_bought} unit{"s" if transaction.quantity_bought != 1 else ""} of {transaction.item.title}. '
            f'${format_money(transaction.price)} was paid from your wallet and moved into the seller wallet.',
            'success',
        )
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

        purchase_wallet = None
        contact_conversation = None
        if current_user.is_authenticated and current_user.id != item.seller_id:
            purchase_wallet = build_purchase_wallet_context(current_user, item.price)
            contact_conversation = Conversation.query.filter_by(item_id=item.id, buyer_id=current_user.id).first()

        return render_template(
            'item_detail.html',
            item=serialize_item(item),
            contact_conversation_id=contact_conversation.id if contact_conversation else None,
            purchase_wallet=purchase_wallet,
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
            return redirect(url_for('item_detail_page', item_id=item.id) + '#contact-seller')

        flash('Conversation ready.', 'success')
        return redirect(url_for('dashboard_page', conversation=conversation.id) + '#inbox')

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

        return redirect(url_for('dashboard_page', conversation=conversation.id) + '#inbox')

    @app.route('/wallet/payment-methods', methods=['POST'])
    @login_required
    @csrf_protect
    def wallet_payment_methods_page():
        method, error, _ = add_payment_method(
            current_user,
            request.form.get('provider_name', ''),
            request.form.get('account_holder', ''),
            request.form.get('account_number', ''),
            make_default=request.form.get('is_default') == 'on',
        )
        if error:
            flash(error, 'error')
            return redirect(url_for('dashboard_page') + '#wallet')

        flash(f'Linked {method.masked_details}. Only masked payment details are stored in this demo.', 'success')
        return redirect(url_for('dashboard_page') + '#wallet')

    @app.route('/wallet/top-up', methods=['POST'])
    @login_required
    @csrf_protect
    def wallet_top_up_page():
        wallet, entry, error, _ = top_up_wallet(
            current_user,
            request.form.get('payment_method_id', type=int),
            request.form.get('amount', ''),
        )
        if error:
            flash(error, 'error')
            return redirect(url_for('dashboard_page') + '#wallet')

        flash(
            f'Wallet topped up by ${format_money(entry.amount)}. '
            f'Available balance is now ${format_money(wallet.available_balance)}.',
            'success',
        )
        return redirect(url_for('dashboard_page') + '#wallet')

    @app.route('/wallet/withdraw', methods=['POST'])
    @login_required
    @csrf_protect
    def wallet_withdraw_page():
        wallet, withdrawal_entry, fee_entry, error, _ = withdraw_from_wallet(
            current_user,
            request.form.get('payment_method_id', type=int),
            request.form.get('amount', ''),
        )
        if error:
            flash(error, 'error')
            return redirect(url_for('dashboard_page') + '#wallet')

        flash(
            f'Withdrawal of ${format_money(abs(withdrawal_entry.amount))} requested to '
            f'{withdrawal_entry.payment_method.masked_details}. Fee charged: ${format_money(abs(fee_entry.amount))}.',
            'success',
        )
        return redirect(url_for('dashboard_page') + '#wallet')

    @app.route('/dashboard')
    @login_required
    def dashboard_page():
        return render_template('dashboard.html', **resolve_dashboard_context(current_user))

    @app.route('/referral/generate', methods=['POST'])
    @login_required
    @csrf_protect
    def generate_referral_code_route():
        if not is_referral_eligible(current_user):
            flash(
                'You need at least 3 completed trades or a reputation score of 4.0+ to generate a referral code.',
                'error'
            )
            return redirect(url_for('dashboard_page'))

        code = generate_referral_code_for_user(current_user)
        flash(f'Your referral code has been generated: {code}', 'success')
        return redirect(url_for('dashboard_page'))

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
            data.get('quantity', ''),
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

        data = request.get_json(silent=True) or {}
        quantity = data.get('quantity', 1)

        transaction, error, status = complete_purchase(item, current_user, quantity=quantity)
        if error:
            return jsonify({'success': False, 'error': error}), status

        return jsonify({
            'success': True,
            'message': 'Purchase completed successfully using wallet funds',
            'transaction': {
                'id': transaction.id,
                'item_id': transaction.item_id,
                'quantity_bought': transaction.quantity_bought,
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
                'wallet_enabled': True,
                'min_top_up_amount': MIN_TOP_UP_AMOUNT,
                'min_withdrawal_amount': MIN_WITHDRAWAL_AMOUNT,
                'withdrawal_fee_rate_percent': int(WITHDRAWAL_FEE_RATE * 100),
            },
        }), 200

    @app.route('/api/cart', methods=['GET'])
    @login_required
    def api_get_cart():
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        items = []
        total_price = 0.0
        for cart_item in cart_items:
            item = cart_item.item
            if item.is_sold or item.is_draft:
                continue
            item_total = round_money(item.price * cart_item.quantity)
            total_price = round_money(total_price + item_total)
            items.append({
                'cart_item_id': cart_item.id,
                'item': serialize_item(item),
                'quantity': cart_item.quantity,
                'item_total': item_total,
            })
        return jsonify({
            'success': True,
            'cart': {
                'items': items,
                'total_items': len(items),
                'total_price': total_price,
            }
        }), 200

    @app.route('/api/cart/add', methods=['POST'])
    @login_required
    def api_add_to_cart():
        data = request.get_json() or {}
        item_id = data.get('item_id')
        quantity = int(data.get('quantity', 1))

        if not item_id or quantity < 1:
            return jsonify({'success': False, 'error': 'Invalid item or quantity'}), 400

        item = get_item_or_none(item_id)
        if not item or item.is_sold or item.is_draft:
            return jsonify({'success': False, 'error': 'Item not available'}), 404

        if quantity > item.quantity:
            return jsonify({'success': False, 'error': f'Only {item.quantity} units available'}), 400

        cart_item = CartItem.query.filter_by(user_id=current_user.id, item_id=item_id).first()
        if cart_item:
            cart_item.quantity += quantity
        else:
            cart_item = CartItem(user_id=current_user.id, item_id=item_id, quantity=quantity)
            db.session.add(cart_item)
        
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Item added to cart',
            'cart_item': {
                'id': cart_item.id,
                'item_id': item_id,
                'quantity': cart_item.quantity,
            }
        }), 201

    @app.route('/api/cart/items/<int:item_id>', methods=['PATCH'])
    @login_required
    def api_update_cart_item(item_id):
        data = request.get_json() or {}
        quantity = int(data.get('quantity', 1))

        if quantity < 1:
            return jsonify({'success': False, 'error': 'Quantity must be at least 1'}), 400

        item = get_item_or_none(item_id)
        if not item or item.is_sold or item.is_draft:
            return jsonify({'success': False, 'error': 'Item not available'}), 404

        if quantity > item.quantity:
            return jsonify({'success': False, 'error': f'Only {item.quantity} units available'}), 400

        cart_item = CartItem.query.filter_by(user_id=current_user.id, item_id=item_id).first()
        if not cart_item:
            return jsonify({'success': False, 'error': 'Item not in cart'}), 404

        cart_item.quantity = quantity
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Cart item updated',
            'cart_item': {
                'id': cart_item.id,
                'item_id': item_id,
                'quantity': cart_item.quantity,
            }
        }), 200

    @app.route('/api/cart/items/<int:item_id>', methods=['DELETE'])
    @login_required
    def api_remove_from_cart(item_id):
        cart_item = CartItem.query.filter_by(user_id=current_user.id, item_id=item_id).first()
        if not cart_item:
            return jsonify({'success': False, 'error': 'Item not in cart'}), 404

        db.session.delete(cart_item)
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Item removed from cart'
        }), 200

    @app.route('/api/cart/checkout', methods=['POST'])
    @login_required
    def api_checkout_cart():
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        if not cart_items:
            return jsonify({'success': False, 'error': 'Cart is empty'}), 400

        transactions = []
        errors = []

        for cart_item in cart_items:
            item = cart_item.item
            if item.is_sold or item.is_draft:
                errors.append(f'{item.title} is no longer available')
                continue

            if cart_item.quantity > item.quantity:
                errors.append(f'Only {item.quantity} units of {item.title} available')
                continue

            transaction, error, _ = complete_purchase(item, current_user, quantity=cart_item.quantity)
            if error:
                errors.append(f'{item.title}: {error}')
            else:
                transactions.append(transaction)
                db.session.delete(cart_item)

        if errors:
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': 'Some items could not be purchased',
                'errors': errors,
                'transactions': [{'id': t.id, 'item': t.item.title} for t in transactions]
            }), 400

        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'Successfully purchased {len(transactions)} item{"s" if len(transactions) != 1 else ""}',
            'transactions': [
                {
                    'id': t.id,
                    'item_id': t.item_id,
                    'item_title': t.item.title,
                    'quantity': t.quantity_bought,
                    'price': t.price,
                }
                for t in transactions
            ]
        }), 200

    return app


if __name__ == '__main__':
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=app.config.get('DEBUG', False), host='0.0.0.0', port=port)
