import pandas as pd
import requests
from selenium import webdriver #webdriver 網頁驅動程式
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
# 模組裡面包含了 UI 相關的支援工具，像是等待元素出現、表單操作等。
from selenium.webdriver.support import expected_conditions as EC
# webdriver → 控制瀏覽器
# By → 找網頁元素
# Keys → 模擬鍵盤
import datetime

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
    chrome_options.add_argument("--headless")  # 不開視窗
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    """抓取 Instagram 粉絲數"""
    driver = webdriver.Chrome()
    driver.get(f"https://www.instagram.com/{username}/")
    # 等待頁面載入粉絲數元素
    # visibility_of_element_located(locator) 等元素「可見」
    followers_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, '//span[@title]'))
    )
    followers_count = followers_element.get_attribute("title")
    driver.quit()
    print('粉絲數量 :', followers_count)
    return  followers_count

def save_date(username, followers):
    """儲存今日日期與粉絲數（若當日已有紀錄則覆寫）"""
    today = datetime.date.today()

    try:
        df = pd.read_csv("followers.csv")
    except FileNotFoundError:
        df = pd.DataFrame(columns=["date", "username", "followers"])

    # 找出相同日期 + 使用者的資料
    mask = (df["date"] == str(today)) & (df["username"] == username)

    if mask.any():
        df.loc[mask, "followers"] = followers
        print("今日已有紀錄，已覆寫更新。")
    else:
        new_row = pd.DataFrame([[str(today), username, followers]], columns=["date", "username", "followers"])
        df = pd.concat([df, new_row], ignore_index=True)

    # 移除重複紀錄（以 date+username 為基準）
    df = df.drop_duplicates(subset=["date", "username"], keep="last")
    df.to_csv("followers.csv", index=False)
    print("已儲存（或更新）今日粉絲數。")



def get_difference(username, today_followers):
    """比對昨日粉絲數差異"""
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

    except Exception as e:
        return f"無法比較昨日資料：{e}"

def send_line_message(user_id, message, access_token):
    """使用 LINE Messaging API 傳送訊息"""
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    data = {
        "to": user_id,  # 接收者 LINE User ID
        "messages": [{"type": "text","text": message}]
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        print("訊息發送成功")
    else:
        print("訊息發送失敗:", response.status_code, response.text)


def main():
    username = "the_firsttake"
    today = datetime.date.today()
    followers = get_followers(username)  # 抓取粉絲數
    save_date(username, followers)       # 儲存今日紀錄
    diff_message = get_difference(username, followers) # 計算粉絲變化

    # Messaging API Token & User ID
    ACCESS_TOKEN = "B799OHjuXJ9+mFFz53Jvlct37fZuOOv1eJq8yY4QZPOZ96GAAChnkrsJGPoGEF9gU4mjKXiZrMNl+FTegJYKH5hPctXrlVvjkbGkhUNDfj0q0DVf22B5or9azKw3DNpeERyJ7JhO5F/Wba9EnvW+GgdB04t89/1O/w1cDnyilFU="
    USER_ID = "Udf1b03cb03e5931d7cd8bfb2135b11a4"

    message = f"帳號：{username}\n日期：{today}\n粉絲數：{followers}\n{diff_message}"
    send_line_message(USER_ID, message, ACCESS_TOKEN)

main()

