"""
Django settings for autozone project.
"""

import os
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
env_file = BASE_DIR / '.env'
if env_file.exists():
    load_dotenv(env_file, override=True)

# ====================== ENVIRONMENT ======================
DJANGO_ENV = os.getenv('DJANGO_ENV', 'local').strip().lower()
DEBUG = DJANGO_ENV != 'production'

# ====================== SECURITY ======================
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')

if not SECRET_KEY:
    raise ValueError("DJANGO_SECRET_KEY is not set in .env file!")

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Production domains from .env
allowed_hosts = os.getenv('DJANGO_ALLOWED_HOSTS', '')
if allowed_hosts:
    ALLOWED_HOSTS += [host.strip() for host in allowed_hosts.split(',') if host.strip()]

# Also allow server IP in production
if DJANGO_ENV == 'production':
    ALLOWED_HOSTS += ['185.27.135.97']

# ====================== APPLICATION ======================
INSTALLED_APPS = [
    'website',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'autozone.urls'
WSGI_APPLICATION = 'autozone.wsgi.application'

# ====================== DATABASE ======================
if all(os.getenv(key) for key in ['DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_HOST']):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.getenv('DB_NAME'),
            'USER': os.getenv('DB_USER'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('DB_HOST'),
            'PORT': os.getenv('DB_PORT', '3306'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ====================== TEMPLATES & STATIC ======================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# ====================== INTERNATIONALIZATION ======================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ====================== SECURITY (Production) ======================
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

# ====================== ERPNEXT INTEGRATION ======================
ERPNEXT_BASE_URL = os.getenv('ERPNEXT_BASE_URL', '').rstrip('/')
ERPNEXT_AUTH_TOKEN = os.getenv('ERPNEXT_AUTH_TOKEN', '').strip()
ERPNEXT_API_KEY = os.getenv('ERPNEXT_API_KEY', os.getenv('ERP_API_KEY', '')).strip()
ERPNEXT_API_SECRET = os.getenv('ERPNEXT_API_SECRET', os.getenv('ERP_API_SECRET', '')).strip()
ERPNEXT_ITEM_PRICE_LIST = os.getenv('ERPNEXT_ITEM_PRICE_LIST', '').strip()
ERPNEXT_ITEM_MODEL_FIELD = os.getenv('ERPNEXT_ITEM_MODEL_FIELD', 'item_group').strip() or 'item_group'
ERPNEXT_CATALOG_CACHE_TIMEOUT = int(os.getenv('ERPNEXT_CATALOG_CACHE_TIMEOUT', '300'))
ERPNEXT_VERIFY_SSL = os.getenv('ERPNEXT_VERIFY_SSL', 'false').strip().lower() in ('1', 'true', 'yes')