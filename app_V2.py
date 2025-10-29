# ig_line_bot_render.py
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import datetime
import os

# ---------------- LINE 設定 ----------------
ACCESS_TOKEN = "B799OHjuXJ9+mFFz53Jvlct37fZuOOv1eJq8yY4QZPOZ96GAAChnkrsJGPoGEF9gU4mjKXiZrMNl+FTegJYKH5hPctXrlVvjkbGkhUNDfj0q0DVf22B5or9azKw3DNpeERyJ7JhO5F/Wba9EnvW+GgdB04t89/1O/w1cDnyilFU="
SECRET = "22a7b9ed4003a08778308b10e7d0047a"

line_bot_api = LineBotApi(ACCESS_TOKEN)
handler = WebhookHandler(SECRET)

# ---------------- Instagram 抓粉絲 ----------------
def parse_followers(followers_str):
    followers_str = followers_str.replace(',', '').strip()
    if '萬' in followers_str:
        return int(float(followers_str.replace('萬','')) * 10000)
    elif 'K' in followers_str:
        return int(float(followers_str.replace('K','')) * 1000)
    elif 'M' in followers_str:
        return int(float(followers_str.replace('M','')) * 1000000)
    else:
        return int(float(followers_str))

def get_followers(username):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/141.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(f"https://www.instagram.com/{username}/")
    followers_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, '//span[@title]'))
    )
    followers_count = followers_element.get_attribute("title")
    driver.quit()
    return parse_followers(followers_count)

def save_date(username, followers):
    today = datetime.date.today()
    try:
        df = pd.read_csv("followers.csv")
    except FileNotFoundError:
        df = pd.DataFrame(columns=["date", "username", "followers"])

    mask = (df["date"] == str(today)) & (df["username"] == username)
    if mask.any():
        df.loc[mask, "followers"] = followers
    else:
        new_row = pd.DataFrame([[str(today), username, followers]], columns=["date", "username", "followers"])
        df = pd.concat([df, new_row], ignore_index=True)

    df = df.drop_duplicates(subset=["date", "username"], keep="last")
    df.to_csv("followers.csv", index=False)

def get_difference(username, today_followers):
    try:
        df = pd.read_csv("followers.csv")
        df_user = df[df["username"] == username]
        if len(df_user) < 2:
            return "首次紀錄，無法比較昨日資料。"
        yesterday_followers = df_user.iloc[-2]["followers"]
        diff = today_followers - yesterday_followers
        if diff > 0:
            return f"較昨日增加 {diff} 位粉絲 🎉"
        elif diff < 0:
            return f"較昨日減少 {-diff} 位粉絲 😢"
        else:
            return "與昨日持平 👍"
    except:
        return "無法比較昨日資料"

# ---------------- LINE Webhook ----------------
app = Flask(__name__)

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    if text.lower() == "抓粉絲":
        username = "the_firsttake"  # 可改成你要抓的帳號
        try:
            followers = get_followers(username)
            save_date(username, followers)
            diff_msg = get_difference(username, followers)
            reply = f"帳號：{username}\n粉絲數：{followers}\n{diff_msg}"
        except Exception as e:
            reply = f"抓取失敗：{e}"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請傳 '抓粉絲' 來查詢粉絲數。"))

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ---------------- Render 部署設定 ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
