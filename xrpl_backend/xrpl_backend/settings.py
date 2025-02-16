from pathlib import Path
import environ
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-bxy=gsw@&!fac-)r(-)w!ujha4^!8t46^!p2d-ej85aye#^8q9'

# Initialize environment variables
env = environ.Env()
env.read_env(".env")  # Adjust path if needed

# Debugging: Check if .env exists at the expected path
env_path = os.path.join(BASE_DIR, ".env")
if not os.path.exists(env_path):
    raise FileNotFoundError(f".env file not found at: {env_path}")

# Load .env file
env.read_env(env_path)

# Set database settings
MY_DATABASES = {
    "postgres": env.db("POSTGRES_DATABASE_URL"),
    "oracle": env.db("ORACLE_DATABASE_URL"),
}

XRP_NETWORK = env("XRP_NETWORK", default="testnet")  # Use a default if not set
APP_SECRET_KEY = env("APP_SECRET_KEY", default="")  # Use a default if not set

XRP_DEV_FAUCET_URL = env("XRP_DEV_FAUCET_URL", default="")  # Use a default if not set
XRPL_DEV_NETWORK_URL = env("XRPL_DEV_NETWORK_URL", default="")  # Use a default if not set
XRPL_DEV_WEB_SOCKET_NETWORK_URL = env("XRPL_DEV_WEB_SOCKET_NETWORK_URL", default="")  # Use a default if not set
XRPL_DEV_CLIO_NETWORK_URL = env("XRPL_DEV_CLIO_NETWORK_URL", default="")  # Use a default if not set
XRPL_DEV_CLIO_WEB_SOCKET_NETWORK_URL = env("XRPL_DEV_CLIO_WEB_SOCKET_NETWORK_URL", default="")  # Use a default if not set

XRP_TEST_FAUCET_URL = env("XRP_TEST_FAUCET_URL", default="")  # Use a default if not set
XRPL_TEST_NETWORK_URL = env("XRPL_TEST_NETWORK_URL", default="")  # Use a default if not set
XRPL_TEST_WEB_SOCKET_NETWORK_URL = env("XRPL_TEST_WEB_SOCKET_NETWORK_URL", default="")  # Use a default if not set

XRPL_TEST_LABS_NETWORK_URL = env("XRPL_TEST_LABS_NETWORK_URL", default="")  # Use a default if not set
XRPL_TEST_LABS_WEB_SOCKET_NETWORK_URL = env("XRPL_TEST_LABS_WEB_SOCKET_NETWORK_URL", default="")  # Use a default if not set
XRPL_TEST_CLIO_NETWORK_URL = env("XRPL_TEST_CLIO_NETWORK_URL", default="")  # Use a default if not set
XRPL_TEST_CLIO_WEB_SOCKET_NETWORK_URL = env("XRPL_TEST_CLIO_WEB_SOCKET_NETWORK_URL", default="")  # Use a default if not set

XRP_PROD_FAUCET_URL = env("XRP_PROD_FAUCET_URL", default="")  # Use a default if not set
XRPL_PROD_NETWORK_URL = env("XRPL_PROD_NETWORK_URL", default="")  # Use a default if not set
XRPL_PROD_WEB_SOCKET_NETWORK_URL = env("XRPL_PROD_WEB_SOCKET_NETWORK_URL", default="")  # Use a default if not set

XRP_ACCOUNT_DELETE_FEE_IN_DROPS = env("XRP_ACCOUNT_DELETE_FEE_IN_DROPS", default="10")  # Use a default if not set
XRP_SEND_ACCOUNT_FEE_IN_DROPS = env("XRP_SEND_ACCOUNT_FEE_IN_DROPS", default="10")  # Use a default if not set
BLACK_HOLE_ADDRESS = env("BLACK_HOLE_ADDRESS", default='')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'xrpl_api',
    'corsheaders',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:4200",  # Add your Angular app's URL
]

CORS_ALLOW_ALL_ORIGINS = True

ROOT_URLCONF = 'xrpl_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'xrpl_backend.wsgi.application'

# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/
STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} [{module} - {funcName}:{lineno}] {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',  # Log all messages (DEBUG and higher)
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'debug.log'),  # Path to the log file
            'formatter': 'verbose',  # Use the verbose formatter
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
        'xrpl_app': {  # Replace with your app name
            'handlers': ['file'],
            'level': 'DEBUG',
        },
    },
}
