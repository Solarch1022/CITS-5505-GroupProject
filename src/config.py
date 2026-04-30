import os
import re
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(basedir, '.env'))

instance_dir = os.path.join(basedir, 'instance')

# Create instance directory if it doesn't exist
os.makedirs(instance_dir, exist_ok=True)


def _is_windows_absolute_path(path):
    return bool(re.match(r'^[A-Za-z]:[\\/]', path))


def resolve_database_uri():
    default_path = os.path.join(instance_dir, 'app.db')
    database_url = os.environ.get('DATABASE_URL')

    if not database_url:
        normalized_default_path = default_path.replace('\\', '/')
        return f'sqlite:///{normalized_default_path}'

    if database_url == 'sqlite:///:memory:':
        return database_url

    if database_url.startswith('sqlite:///'):
        db_path = database_url[len('sqlite:///'):]

        if not os.path.isabs(db_path) and not _is_windows_absolute_path(db_path):
            db_path = os.path.join(basedir, db_path)

        db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        normalized_db_path = db_path.replace('\\', '/')
        return f'sqlite:///{normalized_db_path}'

    return database_url

class Config:
    """Base configuration"""
    SQLALCHEMY_DATABASE_URI = resolve_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SESSION_TYPE = 'filesystem'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Email configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', True)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = ('UWA Student Marketplace', os.environ.get('MAIL_USERNAME', 'noreply@uwastudentmarketplace.local'))


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
