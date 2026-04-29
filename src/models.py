import os
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120))
    bio = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    items = db.relationship('Item', backref='seller', lazy=True, foreign_keys='Item.seller_id')
    seller_transactions = db.relationship('Transaction', backref='seller', lazy=True, foreign_keys='Transaction.seller_id')
    buyer_transactions = db.relationship('Transaction', backref='buyer', lazy=True, foreign_keys='Transaction.buyer_id')
    seller_conversations = db.relationship('Conversation', backref='seller', lazy=True, foreign_keys='Conversation.seller_id')
    buyer_conversations = db.relationship('Conversation', backref='buyer', lazy=True, foreign_keys='Conversation.buyer_id')
    sent_messages = db.relationship('Message', backref='sender', lazy=True, foreign_keys='Message.sender_id')
    wallet = db.relationship('Wallet', backref='user', uselist=False, cascade='all, delete-orphan')
    payment_methods = db.relationship(
        'PaymentMethod',
        backref='user',
        lazy=True,
        cascade='all, delete-orphan',
        order_by='PaymentMethod.created_at.desc()'
    )
    wallet_entries = db.relationship(
        'WalletEntry',
        backref='user',
        lazy=True,
        cascade='all, delete-orphan',
        order_by='WalletEntry.created_at.desc()'
    )
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        return str(self.id)
    
    @property
    def is_active(self):
        return True
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_anonymous(self):
        return False
    
    def __repr__(self):
        return f'<User {self.username}>'


class Item(db.Model):
    __tablename__ = 'items'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)
    condition = db.Column(db.String(20), nullable=False)  # new, like_new, good, fair
    quantity = db.Column(db.Integer, default=1, nullable=False)  # Available quantity
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    is_draft = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_sold = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    transactions = db.relationship('Transaction', backref='item', lazy=True)
    conversations = db.relationship('Conversation', backref='item', lazy=True, cascade='all, delete-orphan')
    images = db.relationship(
        'ItemImage',
        backref='item',
        lazy=True,
        cascade='all, delete-orphan',
        order_by='ItemImage.sort_order.asc()'
    )
    
    def __repr__(self):
        return f'<Item {self.title}>'


class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    quantity_bought = db.Column(db.Integer, default=1, nullable=False)  # Quantity purchased in this transaction
    price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, completed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (db.Index('idx_seller_created', 'seller_id', 'created_at'),
                      db.Index('idx_buyer_created', 'buyer_id', 'created_at'),)
    
    def __repr__(self):
        return f'<Transaction {self.id}>'


class Wallet(db.Model):
    __tablename__ = 'wallets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    available_balance = db.Column(db.Float, default=0.0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Wallet user={self.user_id} balance={self.available_balance}>'


class PaymentMethod(db.Model):
    __tablename__ = 'payment_methods'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    provider_name = db.Column(db.String(80), nullable=False)
    account_holder = db.Column(db.String(120), nullable=False)
    masked_details = db.Column(db.String(80), nullable=False)
    last_four = db.Column(db.String(4), nullable=False)
    method_type = db.Column(db.String(30), default='bank_card', nullable=False)
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.Index('idx_payment_method_user_created', 'user_id', 'created_at'),
    )

    def __repr__(self):
        return f'<PaymentMethod user={self.user_id} last4={self.last_four}>'


class WalletEntry(db.Model):
    __tablename__ = 'wallet_entries'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    payment_method_id = db.Column(db.Integer, db.ForeignKey('payment_methods.id'), nullable=True, index=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True, index=True)
    entry_type = db.Column(db.String(40), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    balance_after = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    payment_method = db.relationship('PaymentMethod', backref=db.backref('wallet_entries', lazy=True))
    transaction = db.relationship('Transaction', backref=db.backref('wallet_entries', lazy=True))

    __table_args__ = (
        db.Index('idx_wallet_entry_user_created', 'user_id', 'created_at'),
    )

    def __repr__(self):
        return f'<WalletEntry user={self.user_id} type={self.entry_type} amount={self.amount}>'


class ItemImage(db.Model):
    __tablename__ = 'item_images'

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False, index=True)
    file_path = db.Column(db.String(255), nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.Index('idx_item_image_order', 'item_id', 'sort_order'),
    )

    def __repr__(self):
        return f'<ItemImage item={self.item_id} path={self.file_path}>'


class Conversation(db.Model):
    __tablename__ = 'conversations'

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    messages = db.relationship('Message', backref='conversation', lazy=True, cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('item_id', 'buyer_id', name='uq_conversation_item_buyer'),
        db.Index('idx_conversation_seller_updated', 'seller_id', 'updated_at'),
        db.Index('idx_conversation_buyer_updated', 'buyer_id', 'updated_at'),
    )

    def __repr__(self):
        return f'<Conversation item={self.item_id} buyer={self.buyer_id}>'


class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.Index('idx_message_conversation_created', 'conversation_id', 'created_at'),
    )

    def __repr__(self):
        return f'<Message {self.id} conversation={self.conversation_id}>'


class CartItem(db.Model):
    __tablename__ = 'cart_items'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False, index=True)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    item = db.relationship('Item', backref=db.backref('cart_items', lazy=True))
    user = db.relationship('User', backref=db.backref('cart_items', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'item_id', name='uq_cart_user_item'),
        db.Index('idx_cart_user_created', 'user_id', 'created_at'),
    )

    def __repr__(self):
        return f'<CartItem user={self.user_id} item={self.item_id} qty={self.quantity}>'

