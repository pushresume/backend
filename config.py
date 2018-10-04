import os
import dotenv

if os.path.exists('.env'):
    dotenv.load_dotenv('.env')

DEBUG = True if os.getenv('DEBUG') == 'True' else False

# REQUIRED APP SETTINGS

FRONTEND_URL = os.getenv('FRONTEND_URL')
BACKEND_URL = os.getenv('BACKEND_URL')

PROVIDERS = ['headhunter', 'superjob']

CLEANUP_PERIOD = 60*60*24  # sec
REAUTH_PERIOD = 60*180  # sec
PUSH_PERIOD = 60*30  # sec

JWT_HEADER_TYPE = 'JWT'
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', os.urandom(64))
JWT_ACCESS_TOKEN_EXPIRES = os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 15)  # min

SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgres://')
SQLALCHEMY_TRACK_MODIFICATIONS = False

REDIS_URL = os.getenv('REDIS_URL', 'redis://')

CACHE_TYPE = 'redis'
CACHE_KEY_PREFIX = 'cache'
CACHE_DEFAULT_TIMEOUT = 300
CACHE_REDIS_URL = os.getenv('REDIS_URL', 'redis://')

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

OTP_LENGTH = 8
OTP_TTL = 60  # sec

NOTIFICATIONS_TTL = 15*60  # sec
NOTIFICATIONS_PERIOD = 60  # sec

# PROVIDERS SETTINGS

HEADHUNTER = {
    'client_id': os.getenv('HH_CLIENT'),
    'client_secret': os.getenv('HH_SECRET'),
    'base_url': os.getenv('HH_BASE_URL'),
    'authorize_url': os.getenv('HH_AUTH_URL'),
    'access_token_url': os.getenv('HH_TOKEN_URL')
}

SUPERJOB = {
    'client_id': os.getenv('SJ_CLIENT'),
    'client_secret': os.getenv('SJ_SECRET'),
    'base_url': os.getenv('SJ_BASE_URL'),
    'authorize_url': os.getenv('SJ_AUTH_URL'),
    'access_token_url': os.getenv('SJ_TOKEN_URL'),
    'refresh_token_url': os.getenv('SJ_TOKEN_REFRESH_URL')
}
