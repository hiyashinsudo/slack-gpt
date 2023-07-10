import slack
from slackeventsapi import SlackEventAdapter
import os
import openai

# Slack APIトークンとOpenAI APIキーを設定
slack_token = os.environ["SLACK_API_TOKEN"]
openai.api_key = os.environ["OPENAI_API_KEY"]

# Slack Events Adapterを作成
slack_events_adapter = SlackEventAdapter(os.environ["SLACK_SIGNING_SECRET"], "/slack/events")

# メッセージイベントハンドラ
@slack_events_adapter.on("message")
def handle_message(event_data):
    message = event_data["event"]
    if "bot_id" not in message:  # ボットが自身のメッセージに応答しないようにするためのチェック
        # ChatGPTにメッセージを送信
        response = openai.Completion.create(
            engine="davinci",
            prompt=message["text"],
            max_tokens=100
        )
        # ChatGPTの応答をSlackに送信
        client = slack.WebClient(token=slack_token)
        client.chat_postMessage(channel=message["channel"], text=response["choices"][0]["text"])

# イベントアダプタを起動
slack_events_adapter.start(port=3000)
