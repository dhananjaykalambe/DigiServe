import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'digiserve-secret-key-2026')
    
    # MongoDB Configuration
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/digiserve')
    
    # File Upload Configuration
    UPLOAD_FOLDER = 'uploads/'
    DOCUMENT_FOLDER = 'uploads/documents/'
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'txt'}
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Admin Configuration
    ADMIN_PHONE = os.environ.get('ADMIN_PHONE', '9999999999')
    ADMIN_NAME = 'Administrator'
    ADMIN_EMAIL = 'admin@digiserve.com'
    
    # Pagination
    ITEMS_PER_PAGE = 10
    
    # Company Info
    COMPANY_NAME = 'DigiSoft'
    COPYRIGHT_YEAR = '2026'
    COPYRIGHT_HOLDER = 'DK'

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}