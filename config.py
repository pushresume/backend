import os
import dotenv

if os.path.exists('.env'):
    dotenv.load_dotenv('.env')

DEBUG = True if os.getenv('DEBUG') == 'True' else False

# REQUIRED APP SETTINGS

# files in app/controllers/ without extensions
CONTROLLERS = ['status', 'auth', 'resume', 'notifications']

FRONTEND_URL = os.getenv('FRONTEND_URL')  # https://example.com
BACKEND_URL = os.getenv('BACKEND_URL')  # https://api.example.com:8080

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_WEBHOOK = os.getenv('TELEGRAM_WEBHOOK')  # secret uri, e.g. uuid4

NOTIFICATIONS_TTL = 15 * 60  # sec, not be send after TTL
NOTIFICATIONS_CHANNELS = ['telegram']

OTP_LENGTH = 8  # length of confirm code
OTP_TTL_TELEGRAM = 60  # sec, TTL of confirm code

# heroku limits
MAX_DATABASE_ROWS = 10000
MAX_REDIS_MEMORY = 25000000  # bytes

# periodic jobs
PERIOD_CLEANUP = 60 * 60 * 24  # sec
PERIOD_REAUTH = 60 * 180  # sec
PERIOD_PUSH = 60 * 30  # sec
PERIOD_NOTIFICATIONS = 60  # sec

# extensions
JWT_HEADER_TYPE = 'JWT'
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', os.urandom(64))
JWT_ACCESS_TOKEN_EXPIRES = os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 600)  # sec

SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///')
SQLALCHEMY_TRACK_MODIFICATIONS = False

REDIS_URL = os.getenv('REDIS_URL', 'redis://')
REDIS_MAX_CONNECTIONS = 5

CACHE_TYPE = 'redis'
CACHE_KEY_PREFIX = 'cache'
CACHE_DEFAULT_TIMEOUT = 300
CACHE_REDIS_URL = os.getenv('REDIS_URL', 'redis://')

SENTRY_DSN = os.getenv('SENTRY_DSN')

SCOUT_KEY = os.getenv('SCOUT_KEY')
SCOUT_MONITOR = True
SCOUT_NAME = 'pushresume-dev' if DEBUG else 'pushresume'

# PROVIDERS SETTINGS

PROVIDERS = ['headhunter', 'superjob']

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
