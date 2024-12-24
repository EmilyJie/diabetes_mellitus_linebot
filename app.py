from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    MemberJoinedEvent, PostbackEvent
)
import os
import openai
import traceback
import firebase_admin
from firebase_admin import credentials, firestore
import time

# Initialize Flask App
app = Flask(__name__)

# LineBot Initialization
line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))

# OpenAI API Initialization
openai.api_key = os.getenv('OPENAI_API_KEY')
ASSISTANT_ID = os.getenv('ASSISTANT_ID')  # Set your Assistant ID in environment variables

# Initialize Firebase
cred = credentials.Certificate(
    {
        "type": os.getenv('FIREBASE_CREDENTIALS_TYPE'),
        "project_id": os.getenv('FIREBASE_CREDENTIALS_PROJECT_ID'),
        "private_key_id": os.getenv('FIREBASE_CREDENTIALS_PRIVATE_KEY_ID'),
        "private_key": os.getenv('FIREBASE_CREDENTIALS_PRIVATE_KEY').replace('\\n', '\n'),
        "client_email": os.getenv('FIREBASE_CREDENTIALS_CLIENT_EMAIL'),
        "client_id": os.getenv('FIREBASE_CREDENTIALS_CLIENT_ID'),
        "auth_uri": os.getenv('FIREBASE_CREDENTIALS_AUTH_URI'),
        "token_uri": os.getenv('FIREBASE_CREDENTIALS_TOKEN_URI'),
        "auth_provider_x509_cert_url": os.getenv('FIREBASE_CREDENTIALS_AUTH_PROVIDER_X509_CERT_URL'),
        "client_x509_cert_url": os.getenv('FIREBASE_CREDENTIALS_CLIENT_X509_CERT_URL'),
        "universe_domain": os.getenv('FIREBASE_CREDENTIALS_UNIVERSE_DOMAIN')
    }
)
firebase_admin.initialize_app(cred)
db = firestore.client()


# ====== GPT Assistant Functions ======
def create_thread():
    """Create a new conversation Thread"""
    thread = openai.beta.threads.create()
    return thread['id']


def add_message_to_thread(thread_id, user_message):
    """Add user message to Thread"""
    openai.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_message
    )


def run_assistant(thread_id):
    """Run Assistant and get reply"""
    run = openai.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=ASSISTANT_ID
    )

    # Poll for Run completion
    timeout_counter = 0
    MAX_RETRIES = 10  # Set maximum retry count
    while True:
        run_status = openai.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run['id'])
        if run_status['status'] == 'completed':
            break
        elif run_status['status'] in ['failed', 'cancelled']:
            raise Exception("Assistant run failed or was cancelled.")
        time.sleep(1)  # Add delay to avoid excessive requests
        timeout_counter += 1
        if timeout_counter > MAX_RETRIES:
            raise Exception("Assistant run timeout")
    
    # Get reply message
    messages = openai.beta.threads.messages.list(thread_id=thread_id)
    return messages['data'][0]['content'][0]['text']['value']


# ====== LineBot Callback ======
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print(traceback.format_exc())
        print("Invalid signature. Please check your channel access token and secret.")
        abort(400)
    except Exception as e:
        print(traceback.format_exc())
        print(f"An error occurred: {e}")
        abort(500)
    return 'OK'


# ====== Handle User Message ======
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    profile = line_bot_api.get_profile(user_id)
    display_name = profile.display_name
    user_message = event.message.text


    try:
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if user_doc.exists:
            # If user exists, get thread_id and update messages
            user_data = user_doc.to_dict()
            thread_id = user_data.get('thread_id')
            user_ref.update({
                'messages': firestore.ArrayUnion([{
                    'role': 'user',
                    'content': user_message,
                    'create_at': firestore.SERVER_TIMESTAMP
                }])
            })
        else:
            # If user does not exist, create a new thread
            thread_id = create_thread()
            user_ref.set({
                'thread_id': thread_id,
                'last_active': firestore.SERVER_TIMESTAMP,
                'create_at': firestore.SERVER_TIMESTAMP,
                'user_info': {
                    'display_name': display_name,
                    'language': profile.language if hasattr(profile, 'language') else 'zh-TW'
                },
                'messages': []
            })

        add_message_to_thread(thread_id, user_message)
        assistant_reply = run_assistant(thread_id)

        user_ref.update({
            'messages': firestore.ArrayUnion([{
                'role': 'assistant',
                'content': assistant_reply,
                'create_at': firestore.SERVER_TIMESTAMP
            }]),
            'last_active': firestore.SERVER_TIMESTAMP
        })

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=assistant_reply)
        )
    except openai.error.OpenAIError as e:
        # Handle OpenAI API errors
        print(f"OpenAI API error: {e}")
        error_message = "噢！糖安心小幫手暫時無法使用，請稍後再試"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=error_message)
        )
    except firebase_admin.exceptions.FirebaseError as e:
        # Handle Firebase errors
        print(f"Firebase error: {e}")
        error_message = "噢！糖安心小幫手暫時無法使用，請稍後再試"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=error_message)
        )
    except Exception as e:
        print(traceback.format_exc())
        print(f"An error occurred: {e}")
        error_message = "噢！糖安心小幫手暫時無法使用，請稍後再試"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=error_message)
        )
        user_ref = db.collection('users').document(user_id)
        user_ref.update({
            'messages': firestore.ArrayUnion([{
                'role': 'assistant',
                'content': error_message,
                'create_at': firestore.SERVER_TIMESTAMP
            }]),
            'last_active': firestore.SERVER_TIMESTAMP
        })


# ====== Handle Postback Event ======
@handler.add(PostbackEvent)
def handle_postback(event):
    print(event.postback.data)


# ====== Welcome New Member ======
@handler.add(MemberJoinedEvent)
def welcome(event):
    uid = event.joined.members[0].user_id
    gid = event.source.group_id
    profile = line_bot_api.get_group_member_profile(gid, uid)
    name = profile.display_name
    message = TextSendMessage(text=f'{name} 歡迎加入！')
    line_bot_api.reply_message(event.reply_token, message)


# Validate environment variables
def validate_env_vars():
    required_vars = [
        'CHANNEL_ACCESS_TOKEN',
        'CHANNEL_SECRET',
        'OPENAI_API_KEY',
        'ASSISTANT_ID'
    ]
    for var in required_vars:
        if not os.getenv(var):
            raise ValueError(f"Missing required environment variable: {var}")


# ====== Start Flask App ======
if __name__ == "__main__":
    validate_env_vars()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
