# Environment import
from dotenv import load_dotenv

# Firebase import
from firebase_functions import https_fn

# Linebot import
from linebot_experiment import linebot_experiment_handler
from linebot_control import linebot_control_handler

# Load environment variables
load_dotenv()

# Main Firebase Function handler
@https_fn.on_request(region="asia-east1")
def linebot_control(req: https_fn.Request) -> https_fn.Response:
    return linebot_control_handler(req)

@https_fn.on_request(region="asia-east1")
def linebot(req: https_fn.Request) -> https_fn.Response:
    return linebot_experiment_handler(req)