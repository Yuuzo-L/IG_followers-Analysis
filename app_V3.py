# app_V3.py
from flask import Flask, request, abort
import os
import datetime
import pandas as pd
import instaloader
from instaloader.exceptions import BadResponseException, ConnectionException, QueryReturnedNotFoundException
import time, random

# LINE SDK v3
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.webhook import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError

# ---------------- LINE 設定 ----------------
ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN", "B799OHjuXJ9+mFFz53Jvlct37fZuOOv1eJq8yY4QZPOZ96GAAChnkrsJGPoGEF9gU4mjKXiZrMNl+FTegJYKH5hPctXrlVvjkbGkhUNDfj0q0DVf22B5or9azKw3DNpeERyJ7JhO5F/Wba9EnvW+GgdB04t89/1O/w1cDnyilFU=")
SECRET = os.environ.get("LINE_SECRET", "22a7b9ed4003a08778308b10e7d0047a")

# 建立 Flask
app = Flask(__name__)
parser = WebhookParser(SECRET)

# 列印 LINE SDK 版本 (不用 pip)
import linebot
try:
    print("LINE SDK version:", linebot.__version__)
except AttributeError:
    import pkg_resources
    version = pkg_resources.get_distribution("line-bot-sdk").version
    print("LINE SDK version (via pkg_resources):", version)

# ---------------- Instagram 設定 ----------------
IG_LOGIN_USER = os.environ.get("oscarpersons@gmail.com")
IG_LOGIN_PASSWORD = os.environ.get("rainpersons")

def make_instaloader():
    L = instaloader.Instaloader(
        dirname_pattern=".",
        download_pictures=False,
        download_video_thumbnails=False,
        download_videos=False,
        save_metadata=False,
        compress_json=False
    )
    if IG_LOGIN_USER:
        try:
            L.load_session_from_file(IG_LOGIN_USER)
        except FileNotFoundError:
            if IG_LOGIN_PASSWORD:
                L.login(IG_LOGIN_USER, IG_LOGIN_PASSWORD)
                L.save_session_to_file()
    return L

L_global = make_instaloader()

# ---------------- CSV 快取 ----------------
def cached_today_followers(username):
    today = str(datetime.date.today())
    try:
        df = pd.read_csv("followers.csv")
    except FileNotFoundError:
        return None
    mask = (df["date"] == today) & (df["username"] == username)
    if mask.any():
        return int(df.loc[mask, "followers"].iloc[-1])
    return None

# ---------------- Instagram 抓粉絲 ----------------
def get_followers_with_retry(username, L=None, max_retries=5, base_backoff=5):
    cached = cached_today_followers(username)
    if cached is not None:
        return cached

    if L is None:
        L = L_global

    attempt = 0
    while attempt < max_retries:
        try:
            profile = instaloader.Profile.from_username(L.context, username)
            return int(profile.followers)
        except (ConnectionException, BadResponseException) as e:
            attempt += 1
            time.sleep(base_backoff * (2 ** (attempt - 1)) + random.uniform(0.5, 2.0))
        except QueryReturnedNotFoundException:
            raise Exception(f"帳號不存在或無法存取：{username}")
        except Exception:
            attempt += 1
            time.sleep(base_backoff * (2 ** (attempt - 1)) + random.uniform(0.5, 2.0))
    raise Exception("已重試多次但仍無法取得 Instagram 資料，請稍後再試或檢查登入/網路/IP。")

def get_followers(username):
    return get_followers_with_retry(username, L=L_global)

# ---------------- CSV 存檔 ----------------
def save_date(username, followers):
    today = str(datetime.date.today())
    try:
        df = pd.read_csv("followers.csv")
    except FileNotFoundError:
        df = pd.DataFrame(columns=["date", "username", "followers"])

    mask = (df["date"] == today) & (df["username"] == username)
    if mask.any():
        df.loc[mask, "followers"] = followers
    else:
        new_row = pd.DataFrame([[today, username, followers]], columns=["date", "username", "followers"])
        df = pd.concat([df, new_row], ignore_index=True)

    df = df.drop_duplicates(subset=["date", "username"], keep="last")
    df.to_csv("followers.csv", index=False)

# ---------------- 粉絲數差異 ----------------
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
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    try:
        events = parser.parse(body, signature)
        for event in events:
            handle_event(event)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

def handle_event(event):
    if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
        text = event.message.text.strip()
        parts = text.split(maxsplit=1)

        if parts[0].lower() == "抓粉絲":
            username = parts[1].strip() if len(parts) > 1 else "the_firsttake"

            try:
                followers = get_followers(username)
                save_date(username, followers)
                diff_msg = get_difference(username, followers)
                reply = f"帳號：{username}\n粉絲數：{followers}\n{diff_msg}"
            except Exception as e:
                reply = f"抓取失敗：{e}"
        else:
            reply = "請傳『抓粉絲 帳號名稱』來查詢粉絲數。"

        # MessagingApi 回覆訊息
        with ApiClient(Configuration(access_token=ACCESS_TOKEN)) as api_client:
            messaging_api = MessagingApi(api_client)
            messaging_api.reply_message(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )

# ---------------- Render 部署 ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
