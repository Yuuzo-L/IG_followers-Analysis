from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

import instaloader
import pandas as pd
import datetime
import os

# ---------------- LINE 設定 ----------------
ACCESS_TOKEN = "B799OHjuXJ9+mFFz53Jvlct37fZuOOv1eJq8yY4QZPOZ96GAAChnkrsJGPoGEF9gU4mjKXiZrMNl+FTegJYKH5hPctXrlVvjkbGkhUNDfj0q0DVf22B5or9azKw3DNpeERyJ7JhO5F/Wba9EnvW+GgdB04t89/1O/w1cDnyilFU="
SECRET = "22a7b9ed4003a08778308b10e7d0047a"

line_bot_api = LineBotApi(ACCESS_TOKEN)
handler = WebhookHandler(SECRET)

# ---------------- Instagram 抓粉絲 ----------------
def get_followers(username):
    L = instaloader.Instaloader()
    profile = instaloader.Profile.from_username(L.context, username)
    return profile.followers

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

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    if text.lower() == "抓粉絲":
        username = "the_firsttake"  # 目標 IG 帳號
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

# ---------------- Render 部署 ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
