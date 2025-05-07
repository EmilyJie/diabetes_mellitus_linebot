import os
from dotenv import load_dotenv
from firebase_admin import initialize_app, credentials, firestore
from firebase_admin import db as realtime

load_dotenv()

cred = credentials.Certificate({
    "type": os.getenv('GOOGLE_FIREBASE_CREDENTIALS_TYPE'),
    "project_id": os.getenv('GOOGLE_FIREBASE_CREDENTIALS_PROJECT_ID'),
    "private_key_id": os.getenv('GOOGLE_FIREBASE_CREDENTIALS_PRIVATE_KEY_ID'),
    "private_key": os.getenv('GOOGLE_FIREBASE_CREDENTIALS_PRIVATE_KEY').replace('\\n', '\n'),
    "client_email": os.getenv('GOOGLE_FIREBASE_CREDENTIALS_CLIENT_EMAIL'),
    "client_id": os.getenv('GOOGLE_FIREBASE_CREDENTIALS_CLIENT_ID'),
    "auth_uri": os.getenv('GOOGLE_FIREBASE_CREDENTIALS_AUTH_URI'),
    "token_uri": os.getenv('GOOGLE_FIREBASE_CREDENTIALS_TOKEN_URI'),
    "auth_provider_x509_cert_url": os.getenv('GOOGLE_FIREBASE_CREDENTIALS_AUTH_PROVIDER_X509_CERT_URL'),
    "client_x509_cert_url": os.getenv('GOOGLE_FIREBASE_CREDENTIALS_CLIENT_X509_CERT_URL'),
    "universe_domain": os.getenv('GOOGLE_FIREBASE_CREDENTIALS_UNIVERSE_DOMAIN')
})

# 初始化 firebase app
initialize_app(cred, {
    'databaseURL': os.getenv('GOOGLE_FIREBASE_DATABASE_URL')
})
db = firestore.client()
realtime_db = realtime