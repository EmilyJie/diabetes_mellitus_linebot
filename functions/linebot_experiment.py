# Environment import
import os
from dotenv import load_dotenv
import traceback
from datetime import datetime

# LineBot import
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (MessageEvent, TextMessage, TextSendMessage, PostbackEvent, PostbackAction, TemplateSendMessage, ButtonsTemplate, FlexSendMessage, BubbleContainer, BoxComponent, TextComponent, SeparatorComponent)

# OpenAI import
from openai import OpenAI

# Firebase import
from firebase_functions import https_fn
from firebase_admin import firestore
from firebase import db, realtime_db

# Other modules import
import time
import re

# Load environment variables
load_dotenv()

# LineBot Initialization
channel_access_token = os.getenv('CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('CHANNEL_SECRET')

if not channel_access_token or not channel_secret:
    raise ValueError(
        "LINE Bot credentials are not properly configured. "
        "Please check CHANNEL_ACCESS_TOKEN and CHANNEL_SECRET in your .env file."
    )

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

# OpenAI API Initialization
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
ASSISTANT_ID = os.getenv('ASSISTANT_ID')


# ====== GPT Assistant Functions ======
def create_thread():
    thread = client.beta.threads.create()
    return thread.id

def add_message_to_thread(thread_id, user_message):
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_message
    )

def run_assistant(thread_id):
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=ASSISTANT_ID
    )

    # Poll for Run completion
    timeout_counter = 0
    MAX_RETRIES = 30  # Set maximum retry count
    while True:
        run_status = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
        if run_status.status == 'completed':
            break
        elif run_status.status == 'cancelled':
            print(f"Run {run.id} was cancelled.")
            return "CANCELLED"
        elif run_status.status in ['failed']:
            raise Exception("Assistant run failed.")
        time.sleep(1)  # Add delay to avoid excessive requests
        timeout_counter += 1
        if timeout_counter > MAX_RETRIES:
            raise Exception("Assistant run timeout")
    
    # Get reply message
    messages = client.beta.threads.messages.list(thread_id=thread_id)
    return messages.data[0].content[0].text.value

def remove_markdown(text):
    # Turn markdown to plain text
    # Remove bold and italic tags
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # **粗體**
    text = re.sub(r'\*(.*?)\*', r'\1', text)      # *斜體*
    
    # Remove title tags
    text = re.sub(r'^#+\s', '', text, flags=re.MULTILINE)  # # 標題
    
    # Remove link tags
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'\1 (\2)', text)  # [文字](連結)
    
    # Remove code block tags
    text = re.sub(r'```(.*?)```', r'\1', text, flags=re.DOTALL)  # ```程式碼區塊```
    text = re.sub(r'`(.*?)`', r'\1', text)  # `行內程式碼`
    
    # Remove quote tags
    text = re.sub(r'^>\s', '', text, flags=re.MULTILINE)  # > 引用
    
    return text


# Main Firebase Function handler
def linebot_experiment_handler(req: https_fn.Request) -> https_fn.Response:
    # Verify signature
    signature = req.headers.get('X-Line-Signature', '')
    body = req.data.decode('utf-8')

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print(traceback.format_exc())
        print("Invalid signature. Please check your channel access token and secret.")
        return https_fn.Response(response="Invalid signature", status=400)
    except Exception as e:
        print(traceback.format_exc())
        print(f"An error occurred: {e}")
        return https_fn.Response(response="Internal error", status=500)
    
    return https_fn.Response(response="OK", status=200)

# Handle user message
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    profile = line_bot_api.get_profile(user_id)
    display_name = profile.display_name
    user_message = event.message.text
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current_date = datetime.now().strftime("%Y/%m/%d")
    print(event.message)

    names_ref = realtime_db.reference('name')
    names = names_ref.get() or []
    if display_name in names:
        message = realtime_db.reference('message').get()
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=message or "您好！糖安心小幫手目前休息中，會盡快回覆您的訊息～")
        )
        return

    # If user message contains "聯繫研究人員" or "糖安心介紹", just return
    if user_message == "聯繫研究人員" or user_message == "糖安心介紹":
        return
    
    # 處理「飲食小知識專區」關鍵字
    elif user_message == "飲食小知識專區":
        line_bot_api.reply_message(
            event.reply_token,
            TemplateSendMessage(
                alt_text='糖尿病飲食小知識',
                template=ButtonsTemplate(
                    thumbnail_image_url='https://firebasestorage.googleapis.com/v0/b/diabetes-mellitus-linebot.firebasestorage.app/o/Linebot%2F%E7%B3%96%E5%B0%BF%E7%97%85%E6%82%A3%E9%A3%B2%E9%A3%9F.png?alt=media&token=195fd80f-bfb9-48e6-9528-8dd739b3c0b9',
                    title='糖尿病飲食小知識',
                    text='了解糖尿病飲食相關知識',
                    actions=[
                        PostbackAction(
                            label='糖尿病飲食原則',
                            data='糖尿病飲食原則'
                        ),
                        PostbackAction(
                            label='六大類食物與代換原則',
                            data='六大類食物與代換原則'
                        ),
                        PostbackAction(
                            label='低醣飲食原則',
                            data='低醣飲食原則'
                        )
                    ]
                )
            )
        )
        return

    # If user message is a Line emoji, return nothing
    if hasattr(event.message, 'emojis') and event.message.emojis and re.match(r'^\(.*\)$', user_message):
        print(f"Received emoji-only message: {user_message}")
        return

    # Check if user message is "今日飲食規劃" or "今日飲食記錄"
    if user_message == "今日飲食規劃":
        user_message = f"今日飲食規劃 - {current_date}"
    elif user_message == "今日飲食記錄":
        user_message = f"今日飲食記錄 - {current_date}"

    try:
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        # Initialize messages list
        messages = []
        is_processing = False
        
        if user_doc.exists:
            # If user exists, get thread_id and update messages
            user_data = user_doc.to_dict()
            thread_id = user_data.get('thread_id')
            is_processing = user_data.get('is_processing', False)
            messages = user_data.get('messages', [])
            pending_messages = user_data.get('pending_messages', [])

            if is_processing:
                pending_messages.append({
                    'role': 'user',
                    'content': user_message,
                    'create_at': current_time
                })
                user_ref.update({
                    'pending_messages': pending_messages,
                    'last_active': firestore.SERVER_TIMESTAMP
                })
                print("Pending message added")
                return
        else:
            # If user does not exist, create a new thread
            thread_id = create_thread()
            user_ref.set({
                'thread_id': thread_id,
                'is_processing': False,
                'last_active': firestore.SERVER_TIMESTAMP,
                'create_at': firestore.SERVER_TIMESTAMP,
                'user_info': {
                    'display_name': display_name,
                    'language': profile.language if hasattr(profile, 'language') else 'zh-Hant'
                },
                'messages': [],
                'pending_messages': []
            })

        # Update user message status
        user_ref.update({
            'is_processing': True,
            'last_active': firestore.SERVER_TIMESTAMP,
        })
        
        # Immediately update Firestore with user message
        messages.append({
            'role': 'user',
            'content': user_message,
            'create_at': current_time
        })
        user_ref.update({
            'messages': messages,
            'last_active': firestore.SERVER_TIMESTAMP
        })
        
        # Send user message to Assistant
        add_message_to_thread(thread_id, user_message)
        assistant_reply = run_assistant(thread_id)
        assistant_reply = remove_markdown(assistant_reply)
        
        # Add assistant reply
        messages.append({
            'role': 'assistant',
            'content': assistant_reply,
            'create_at': current_time
        })

        pending_messages = user_ref.get().to_dict().get('pending_messages', [])
        if pending_messages:
            combined_message = "\n".join([msg['content'] for msg in pending_messages])
            add_message_to_thread(thread_id, combined_message)
            assistant_reply = run_assistant(thread_id)
            assistant_reply = remove_markdown(assistant_reply)
            messages.append({
                'role': 'user',
                'content': combined_message,
                'create_at': current_time
            })
            messages.append({
                'role': 'assistant',
                'content': assistant_reply,
                'create_at': current_time
            })
            pending_messages = []

        # Update with new message
        user_ref.update({
            'messages': messages,
            'pending_messages': pending_messages,
            'last_active': firestore.SERVER_TIMESTAMP,
            'is_processing': False
        })

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=assistant_reply)
        )
    except Exception as e:
        print(traceback.format_exc())
        print(f"An error occurred: {e}")
        error_message = "糖安心小幫手已經收到您的訊息囉！正在努力為您解答中"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=error_message)
        )
        # Update with error message
        if 'user_ref' in locals():
            try:
                updated_doc = user_ref.get().to_dict()
                messages = updated_doc.get('messages', [])
                messages.append({
                    'role': 'assistant',
                    'content': error_message,
                    'create_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                user_ref.update({
                    'messages': messages,
                    'last_active': firestore.SERVER_TIMESTAMP,
                    'is_processing': False  # Reset processing status
                })
            except Exception as e:
                print(f"Error updating error message: {e}")


@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    
    # 處理不同的 postback 資料
    if data == "糖尿病飲食原則":
        # --- Create Flex Message ---
        bubble = BubbleContainer(
            body=BoxComponent(
                layout='vertical',
                spacing='md', # Add some space between components
                contents=[
                    # Main Title
                    TextComponent(text='【糖尿病飲食原則】', weight='bold', size='lg', align='center', margin='md'),
                    SeparatorComponent(margin='lg'), # Add a line separator
                    
                    # Point 1
                    TextComponent(text='1. 均衡飲食、定時定量：', weight='bold', wrap=True, margin='lg'),
                    TextComponent(text='這是穩定血糖的基礎，建議諮詢營養師，規劃個人化的飲食計畫，均衡攝取六大類食物，並固定用餐時間與份量。', wrap=True, size='sm', margin='sm'),
                    
                    # Point 2
                    TextComponent(text='2. 控制醣類（碳水化合物）攝取：', weight='bold', wrap=True, margin='lg'),
                    TextComponent(text='醣類是影響血糖最主要的因素，應學習計算醣類份量，並將總量平均分配於各餐。', wrap=True, size='sm', margin='sm'),
                    
                    # Point 3
                    TextComponent(text='3. 選擇高纖維食物：', weight='bold', wrap=True, margin='lg'),
                    TextComponent(text='多攝取蔬菜、全穀類（如糙米、燕麥）及適量水果，有助於增加飽足感、穩定血糖。', wrap=True, size='sm', margin='sm'),

                    # Point 4
                    TextComponent(text='4. 避免精緻糖與加糖食物：', weight='bold', wrap=True, margin='lg'),
                    TextComponent(text='少喝含糖飲料、少吃甜點、蛋糕、零食等，這些食物易使血糖快速升高，且常含高油脂。', wrap=True, size='sm', margin='sm'),

                    # Point 5
                    TextComponent(text='5. 採低油烹調、選好油：', weight='bold', wrap=True, margin='lg'),
                    TextComponent(text='多用清蒸、水煮、涼拌、烤、滷等方式。減少油炸、油煎。少吃含飽和脂肪（如肥肉、豬油、奶油）及反式脂肪（如酥油、奶精）的食物，選擇健康的植物油。', wrap=True, size='sm', margin='sm'),

                    # Point 6
                    TextComponent(text='6. 少鹽、少加工食品：', weight='bold', wrap=True, margin='lg'),
                    TextComponent(text='減少鹽分攝取，注意加工食品（如香腸、罐頭）的鈉含量。', wrap=True, size='sm', margin='sm'),

                    # Point 7
                    TextComponent(text='7. 節制飲酒：', weight='bold', wrap=True, margin='lg'),
                    TextComponent(text='若飲酒需適量，且避免空腹飲酒，以免引起低血糖。', wrap=True, size='sm', margin='sm'),

                    # Point 8
                    TextComponent(text='8. 維持理想體重：', weight='bold', wrap=True, margin='lg'),
                    TextComponent(text='體重過重或肥胖者，建議減重以改善血糖、血壓及血脂。', wrap=True, size='sm', margin='sm'),
                ]
            )
        )
        
        # --- Send Flex Message ---
        line_bot_api.reply_message(
            event.reply_token,
            FlexSendMessage(
                alt_text='糖尿病飲食原則', # Fallback text for notifications and unsupported clients
                contents=bubble
            )
        )
    
    elif data == "六大類食物與代換原則":
        # You would need to convert this response to FlexSendMessage as well
        # ... (similar structure as above, potentially splitting into two Flex Messages)
        # Example for the first message:
        bubble1 = BubbleContainer(
            body=BoxComponent(
                layout='vertical',
                spacing='md',
                contents=[
                    TextComponent(text='【認識六大類食物】', weight='bold', size='lg', align='center', margin='md'),
                    SeparatorComponent(margin='lg'),
                    TextComponent(text='健康飲食應均衡攝取六大類食物，包含：', wrap=True, margin='md'),
                    # Point 1
                    TextComponent(text='1. 全穀雜糧類：', weight='bold', wrap=True, margin='lg'),
                    TextComponent(text='如：米飯、麵食、地瓜、玉米等。', wrap=True, size='sm', margin='sm'),
                    # Point 2
                    TextComponent(text='2. 豆魚蛋肉類：', weight='bold', wrap=True, margin='lg'),
                    TextComponent(text='如：黃豆製品、魚、海鮮、蛋、禽畜肉等。', wrap=True, size='sm', margin='sm'),
                    # Point 3
                    TextComponent(text='3. 乳品類：', weight='bold', wrap=True, margin='lg'),
                    TextComponent(text='如：牛奶、優格、起司等。', wrap=True, size='sm', margin='sm'),
                    # Point 4
                    TextComponent(text='4. 蔬菜類：', weight='bold', wrap=True, margin='lg'),
                    TextComponent(text='如：各種葉菜、菇類、筍類等。', wrap=True, size='sm', margin='sm'),
                    # Point 5
                    TextComponent(text='5. 水果類：', weight='bold', wrap=True, margin='lg'),
                    TextComponent(text='如：各種新鮮水果。', wrap=True, size='sm', margin='sm'),
                    # Point 6
                    TextComponent(text='6. 油脂與堅果種子類：', weight='bold', wrap=True, margin='lg'),
                    TextComponent(text='如：植物油、堅果、種子等。', wrap=True, size='sm', margin='sm'),
                    
                    SeparatorComponent(margin='lg'),
                    TextComponent(text='醣類食物來源：', weight='bold', wrap=True, margin='lg'),
                    TextComponent(text='主要影響血糖的含醣食物來自 全穀雜糧類、水果類、乳品類。攝取這些食物需注意份量與定時定量。', wrap=True, size='sm', margin='sm'),
                ]
            )
        )
        # Example for the second message:
        bubble2 = BubbleContainer(
             body=BoxComponent(
                layout='vertical',
                spacing='md',
                contents=[
                    TextComponent(text='【食物代換原則】', weight='bold', size='lg', align='center', margin='md'),
                    SeparatorComponent(margin='lg'),
                    TextComponent(text='食物代換原則：', weight='bold', wrap=True, margin='lg'),
                    TextComponent(text='「相同種類」的食物，只要「份量」相當（通常指醣類含量接近），就可以互相替換，讓飲食更有變化。學習食物代換有助於在固定醣量的前提下，選擇想吃的食物！', wrap=True, size='sm', margin='sm'),
                    SeparatorComponent(margin='lg'),
                    TextComponent(text='六大類食物代換份量表：', weight='bold', wrap=True, margin='lg'),
                    TextComponent(text='https://www.hpa.gov.tw/Pages/Detail.aspx?nodeid=543&pid=8382', wrap=True, size='sm', margin='sm', color='#666666', action={'type': 'uri', 'uri': 'https://www.hpa.gov.tw/Pages/Detail.aspx?nodeid=543&pid=8382'}), # Make link clickable
                ]
            )
        )

        line_bot_api.reply_message(
            event.reply_token,
            [
                FlexSendMessage(alt_text='認識六大類食物', contents=bubble1),
                FlexSendMessage(alt_text='食物代換原則', contents=bubble2)
            ]
        )
    
    elif data == "低醣飲食原則":
        # You would need to convert this response to FlexSendMessage as well
        # ... (similar structure, splitting into multiple Flex Messages)
        # Example for the first message:
        bubble1 = BubbleContainer(
            body=BoxComponent(
                layout='vertical',
                spacing='md',
                contents=[
                    TextComponent(text='【低醣飲食原則】', weight='bold', size='lg', align='center', margin='md'),
                    SeparatorComponent(margin='lg'),
                    TextComponent(text='低醣飲食就是減少飲食中「醣類」（也就是碳水化合物）的份量。目標是讓身體少一點需要處理的糖份，幫助穩定血糖。這是一種管理糖尿病的飲食方法選擇。', wrap=True, margin='md'),
                    SeparatorComponent(margin='lg'),
                    TextComponent(text='要多吃什麼？', weight='bold', size='lg', margin='lg'),
                    # Point 1
                    TextComponent(text='1. 大量的蔬菜：', weight='bold', wrap=True, margin='md'),
                    TextComponent(text='特別是葉菜類（像菠菜、空心菜）、花椰菜、菇類、瓜類等「非」根莖類的蔬菜。', wrap=True, size='sm', margin='sm'),
                    # Point 2
                    TextComponent(text='2. 足夠的蛋白質：', weight='bold', wrap=True, margin='md'),
                    TextComponent(text='像是魚、海鮮、雞蛋、雞肉、瘦肉、豆腐等都是好來源。', wrap=True, size='sm', margin='sm'),
                    # Point 3
                    TextComponent(text='3. 健康的脂肪：', weight='bold', wrap=True, margin='md'),
                    TextComponent(text='可以來自堅果、種子（如芝麻、奇亞籽）、酪梨，以及好的植物油（像橄欖油、苦茶油）。', wrap=True, size='sm', margin='sm'),
                ]
            )
        )
        # Example for the second message:
        bubble2 = BubbleContainer(
            body=BoxComponent(
                layout='vertical',
                spacing='md',
                contents=[
                    TextComponent(text='要少吃或避免什麼？', weight='bold', size='lg', margin='lg'),
                    # Point 1
                    TextComponent(text='1. 主食類要減量：', weight='bold', wrap=True, margin='md'),
                    TextComponent(text='米飯、麵條、麵包、饅頭、地瓜、馬鈴薯、玉米等都要明顯減少，不管是白米或糙米都一樣。', wrap=True, size='sm', margin='sm'),
                    # Point 2
                    TextComponent(text='2. 大部分水果要限制：', weight='bold', wrap=True, margin='md'),
                    TextComponent(text='因為水果含天然糖分，通常會建議少吃，或只選擇醣量較低的莓果類（如草莓、藍莓）。', wrap=True, size='sm', margin='sm'),
                    # Point 3
                    TextComponent(text='3. 豆類要注意：', weight='bold', wrap=True, margin='md'),
                    TextComponent(text='像紅豆、綠豆、皇帝豆等澱粉含量高的豆類也要少吃。', wrap=True, size='sm', margin='sm'),
                    # Point 4
                    TextComponent(text='4. 含糖飲料和甜點：', weight='bold', wrap=True, margin='md'),
                    TextComponent(text='像是含糖飲料、蛋糕、冰淇淋、甜甜圈等，都要避免。', wrap=True, size='sm', margin='sm'),
                    
                    SeparatorComponent(margin='lg'),
                    TextComponent(text='低醣飲食跟「生酮飲食」一樣嗎？', weight='bold', size='lg', margin='lg'),
                    TextComponent(text='不太一樣。一般的低醣飲食對醣類的限制，沒有像生酮飲食那麼嚴格 (生酮飲食醣類攝取非常非常少)。', wrap=True, size='sm', margin='sm'),
                ]
            )
        )
        # Example for the third message:
        bubble3 = BubbleContainer(
            body=BoxComponent(
                layout='vertical',
                spacing='md',
                contents=[
                    TextComponent(text='【低醣飲食的注意事項】', weight='bold', size='lg', margin='lg'),
                    # Point 1
                    TextComponent(text='1. 營養均衡：', weight='bold', wrap=True, margin='md'),
                    TextComponent(text='因為少吃了一些食物種類，要注意營養是不是還均衡。', wrap=True, size='sm', margin='sm'),
                    # Point 2
                    TextComponent(text='2. 油脂選擇：', weight='bold', wrap=True, margin='md'),
                    TextComponent(text='可能會吃比較多肉類和油脂，要聰明選，避免吃太多肥肉或紅肉的脂肪。', wrap=True, size='sm', margin='sm'),
                    # Point 3
                    TextComponent(text='3. 諮詢專業：', weight='bold', wrap=True, margin='md'),
                    TextComponent(
                        text='低醣飲食「不是」唯一適合糖尿病的飲食，也不是人人都適合。想嘗試之前，一定要先跟您的醫師或營養師討論，看看您的身體狀況能不能執行，以及怎麼吃才安全又有效喔！',
                        wrap=True, size='sm', margin='sm',
                    )
                ]
            )
        )

        line_bot_api.reply_message(
            event.reply_token,
            [
                FlexSendMessage(alt_text='低醣飲食原則(1/3)', contents=bubble1),
                FlexSendMessage(alt_text='低醣飲食原則(2/3)', contents=bubble2),
                FlexSendMessage(alt_text='低醣飲食原則(3/3)', contents=bubble3)
            ]
        )
    
    # 可以繼續添加更多的 postback 處理邏輯
    elif data == "返回小知識選單":
        # 返回小知識選單
        line_bot_api.reply_message(
            event.reply_token,
            TemplateSendMessage(
                alt_text='糖尿病飲食小知識',
                template=ButtonsTemplate(
                    thumbnail_image_url='https://firebasestorage.googleapis.com/v0/b/diabetes-mellitus-linebot.firebasestorage.app/o/Linebot%2F%E7%B3%96%E5%B0%BF%E7%97%85%E6%82%A3%E9%A3%B2%E9%A3%9F.png?alt=media&token=195fd80f-bfb9-48e6-9528-8dd739b3c0b9',
                    title='糖尿病飲食小知識',
                    text='了解糖尿病飲食相關知識',
                    actions=[
                        PostbackAction(
                            label='糖尿病飲食原則',
                            data='糖尿病飲食原則'
                        ),
                        PostbackAction(
                            label='六大類食物與代換原則',
                            data='六大類食物與代換原則'
                        ),
                        PostbackAction(
                            label='低醣飲食原則',
                            data='低醣飲食原則'
                        )
                    ]
                )
            )
        )
    
    # 如果不是特定的 postback 資料，可以記錄下來
    else:
        print(f"Received postback: {data}")