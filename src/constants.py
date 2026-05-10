"""
Application constants and configuration parameters.
Most values can be overridden via environment variables.
"""
import os

# Item Management
ITEM_CATEGORIES = ['Electronics', 'Furniture', 'Clothing', 'Books', 'Sports', 'Other']
ITEM_CONDITIONS = ['New', 'Like New', 'Good', 'Fair']

# User & Authentication
UWA_STUDENT_DOMAIN = '@student.uwa.edu.au'

# Messaging
MAX_MESSAGE_LENGTH = 600

# Item Images
MAX_IMAGES_PER_ITEM = 6
ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}

# Avatar
MAX_AVATAR_UPLOAD_BYTES = 3 * 1024 * 1024

# Listings
DRAFT_TITLE_PLACEHOLDER = 'Untitled draft'

# Wallet & Transactions
MAX_WALLET_ACTIVITY = 8
MIN_TOP_UP_AMOUNT = 5.0
MAX_TOP_UP_AMOUNT = 2000.0
MIN_WITHDRAWAL_AMOUNT = 5.0
WITHDRAWAL_FEE_RATE = 0.02
WITHDRAWAL_FEE_MINIMUM = 0.50

# Referral System
REFERRAL_REWARD_AMOUNT = 5.0
REFERRAL_REQUIRED_COMPLETED_TRADES = 3
REFERRAL_REQUIRED_REPUTATION = 4.0

# Platform Commission
# Can be overridden via PLATFORM_COMMISSION_RATE environment variable
PLATFORM_COMMISSION_RATE = float(os.environ.get('PLATFORM_COMMISSION_RATE', '0.05'))
