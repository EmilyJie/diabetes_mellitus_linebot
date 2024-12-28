# Diabetes Management LINE Bot with AI-Powered Diet Suggestions

生成式 AI 的糖尿病飲食管理 LINE Bot

## 📍 Research Purpose | 研究目的

This project develops an interactive LINE Bot with generative AI capabilities to provide dietary suggestions and evaluate its impact on dietary management behavior of diabetes patients.

開發生成式 AI 互動式飲食建議的 LINE Bot，評估其對糖尿病患者飲食管理行為的影響與成效。

## 📚 Experimental Design | 實驗設計

### Phase 1 (1 month) | 第一階段（1 個月）

-   Participants maintain their regular dietary habits\
    受測者維持原本的日常飲食習慣
-   Daily reminder at 7:00 PM to record dietary intake\
    每日晚上 7:00 提醒記錄當天飲食內容
-   Access to educational materials about diabetes self-management through image-based forms\
    可使用圖文表單了解糖尿病自我管理相關知識

### Phase 2 (Intervention, 1 month) | 第二階段（干預期，1 個月）

-   Daily reminder at 7:00 AM to discuss daily meal planning\
    每日早上 7:00 提醒討論當天飲食計畫
-   Daily reminder at 7:00 PM to record dietary intake and self-management satisfaction\
    每日晚上 7:00 提醒記錄當天飲食內容以及對自己當天的健康管理滿意度
-   Access to educational materials about diabetes self-management\
    可使用圖文表單了解糖尿病自我管理相關知識
-   Daily self-management satisfaction rating (Scale 1-10)\
    每日健康管理滿意度評分（1-10 分）

## 🛠 Development Setup | 開發環境設定

### Prerequisites | 前置需求

-   Python 3.x (via Anaconda)
-   Flask
-   LINE Messaging API
-   ngrok

### Installation Steps | 安裝步驟

#### 1. Install Anaconda | 安裝 Anaconda

1. Download Anaconda from the official website:

    - Windows: https://www.anaconda.com/download#windows
    - macOS: https://www.anaconda.com/download#macos
    - Linux: https://www.anaconda.com/download#linux

2. Create and activate a new environment:

```bash
conda create -n [your-env-name]
conda activate [your-env-name]
```

#### 2. Install ngrok | 安裝 ngrok

1. Create an account at https://ngrok.com/
2. Download ngrok:
    - Windows: Download the ZIP file and extract it
    - macOS: `brew install ngrok/ngrok/ngrok`
    - Linux: `snap install ngrok`
3. Connect your account:

```bash
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

#### 3. Install Required Packages | 安裝所需套件

```bash
pip install -r requirements.txt
```

### Local Development | 本地開發

The LINE Bot requires a public Webhook URL to forward user messages to your Flask application. For local testing, we use ngrok to map the local server to a public URL.

LINE Bot 需要一個公開的 Webhook URL 才能將使用者訊息發送到 Flask 應用程式，本地測試需使用 ngrok 將本地端伺服器映射到公開 URL。

#### Step 1: Start Flask Server | 啟動 Flask 伺服器

```bash
python app.py
```

#### Step 2: Start ngrok Server | 啟動 ngrok 伺服器

```bash
ngrok http 5000
```

#### Step 3: Set Webhook URL | 設定 Webhook URL

-   Go to the LINE Messaging API console and set the Webhook URL to the ngrok URL.
-   The URL should look like: `https://XXXX-XXX-XXX-XXX-XXX.ngrok.io/callback`

### Environment Setup Notes | 環境設定注意事項

-   Make sure to keep your Python environment isolated using Anaconda\
    請使用 Anaconda 保持 Python 環境的獨立性
-   The ngrok URL changes every time you restart ngrok (unless you have a paid account)\
    每次重啟 ngrok 時，URL 都會改變（除非使用付費帳號）
-   Remember to update the webhook URL in LINE Developer Console whenever the ngrok URL changes\
    記得在 ngrok URL 改變時更新 LINE Developer Console 的 webhook URL
