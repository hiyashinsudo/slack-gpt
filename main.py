import slack
from flask import Flask
from slackeventsapi import SlackEventAdapter
import os
import openai

# Slack APIトークンとOpenAI APIキーを設定
slack_token = os.environ["SLACK_API_TOKEN"]
openai.api_key = os.environ["OPENAI_API_KEY"]
slack_signing_secret = os.environ["SLACK_SIGNING_SECRET"]

app = Flask(__name__)


# APiレスポンステスト用
@app.route("/test")
def hello():
    return "Hello there!"


# Slack Events Adapterを作成
slack_events_adapter = SlackEventAdapter(slack_signing_secret, "/slack/events", app)


# メッセージイベントハンドラ
@slack_events_adapter.on("message")
def handle_message(event_data):
    message = event_data["event"]
    print("got slack msg details:", message)
    if "bot_id" not in message:  # ボットが自身のメッセージに応答しないようにするためのチェック
        # ChatGPTにメッセージを送信
        response = openai.ChatCompletion.create(
            model='gpt-3.5-turbo',
            messages=[{"role": "user", "content": message["text"]}],
            max_tokens=500
        )
        print("response msg:", response["choices"][0]["message"]["content"])
        # ChatGPTの応答をSlackに送信
        client = slack.WebClient(token=slack_token)
        client.chat_postMessage(channel=message["channel"], text=response["choices"][0]["message"]["content"])
    else:
        print("human msg: ", message)


# chatGPT疎通テスト用
@app.route('/chat', methods=['GET', 'POST'])
def chat():
    response = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=[
            {"role": "user", "content": "Who won the world series in 2020?"}],
        max_tokens=300,
        temperature=0,
    )
    print("response msg:", response)
    return response["choices"][0]["message"]["content"]


# Slack msg投稿テスト用
@app.route('/postmsg', methods=['GET', 'POST'])
def respond_message():
    post_text = 'あいうえおabc'
    post_channel = 'test_channel'
    # トークンを指定してWebClientのインスタンスを生成
    client = slack.WebClient(token=slack_token)
    # chat_postMessageメソッドでメッセージ投稿
    client.chat_postMessage(channel=post_channel, text=post_text)
    return post_channel + 'チャンネルにメッセージ：' + post_text + 'を投稿しました'


# イベントアダプタを起動
if __name__ == "__main__":
    app.run(port=3000)
