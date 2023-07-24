import os
import threading

import requests
from flask import Flask, request, jsonify
from requests.auth import HTTPBasicAuth
from slackeventsapi import SlackEventAdapter

from status import Status

# 環境変数の設定
slack_token = os.environ["SLACK_API_TOKEN"]
slack_signing_secret = os.environ["SLACK_SIGNING_SECRET"]
twilio_username = os.environ["TWILIO_USERNAME"]
twilio_password = os.environ["TWILIO_PASSWORD"]

app = Flask(__name__)

# かつてキャッチしたユーザーイベントを追跡する変数
previous_user_events = []

# Slack Events Adapterを作成
slack_events_adapter = SlackEventAdapter(slack_signing_secret, "/slack/events", app)


####################################
# インタビュー実施系
####################################

# メッセージイベントハンドラ
@slack_events_adapter.on("message")
def handle_message(event_data):
    event = event_data["event"]
    user_id = event_data["event"]["user"]
    response = None
    global previous_user_events
    print("event triggerd: ", event)
    # 不要なイベントに発火しないためのバリデーション
    if event_data in previous_user_events:
        return
    if "bot_id" in event:  # ボットが自身のメッセージに応答しないようにするためのチェック
        return
    url = f'https://interviewer-bot-api-dot-project-slack-gpt.dt.r.appspot.com/interviews/{user_id}'
    jung_response = requests.post(url, data={'message': event["text"]})
    print(f"jung_response = {jung_response.json()}")
    # ResponseをSlackに送信
    send_message(target=user_id, message=jung_response.json()['message'])
    # 最後のユーザーイベントとしてを追加
    previous_user_events.append(event_data)


def begin_interview(subject, approach, target):
    print(f"begin_interview: subject={subject}, approach={approach}, target={target}")
    # slack, phone以外の入力はだめ
    if approach not in ['slack', 'phone']:
        print(f"unexpected approach={approach}")
        return jsonify({'status': Status.NG.value, 'data': 'Unexpected approach=' + approach})
    # newエンドポイントからIDの初期登録、最初の質問文を取得
    url = f'https://interviewer-bot-api-dot-project-slack-gpt.dt.r.appspot.com/interviews/{target}/new'
    response = requests.post(url, data={'subject': subject})
    first_question = response.json()['message']
    print("J res: " + response.text)
    # 異常系のレスポンスの場合
    if not response.json()['ok']:
        return jsonify(
            {'status': Status.NG.value, 'data': {'ok': response.json()['ok'], 'reason': response.json()['reason']}}
        )
    # approachによって処理を切り分け
    if approach == 'slack':
        print("slack mode")
        # 回答者に最初のメッセージを送信
        send_message(target, first_question)
        # Slackの回答者に最初のメッセージが送信できれば成功でレスポンス
        return jsonify({'status': Status.OK.value,
                        'data': {'result': 'Interview In progress by slack...',
                                 'subject_id': response.json()['id']}})
    elif approach == 'phone':
        print("phone mode")
        if target not in ['+817031792233', '+818079581088', '+818072369925']:  # ['J', 'Yo, 'Ya']
            print(f"unexpected phone number={target}")
            return jsonify({'status': Status.NG.value, 'data': f'Unexpected phone number={target}'})
        url = 'https://studio.twilio.com/v2/Flows/FW664a13438c90f5c9c08ae66949795755/Executions'
        response = requests.post(url, data={'To': target,
                                            'From': '+15733832320',
                                            'Parameters': '{"message":"' + first_question + '"}'},
                                 auth=requests.auth.HTTPBasicAuth(twilio_username, twilio_password))
        print(f"Yo response: {response.text}")
        return jsonify({'status': Status.OK.value, 'data': 'test'})


@app.route('/start_from_command', methods=['POST'])
def start_from_command():
    # 各種変数受け取り
    allowed_user_ids = ['U05GCA6R3QC', 'U05HRSNAX6X', 'U05H9NTA1S7']  # 事務局のuser_id
    command = request.form.get('command')  # Slackコマンド
    paras = [ele.strip() for ele in request.form.get('text').split(',')]  # Slackコマンド引数 [subject, approach, target]
    response_url = request.form.get('response_url')  # メッセージ応答の生成に使用できる一時的なWebhook URL。
    user_id = request.form.get('user_id')  # コマンド実行ユーザ
    print(f"REQUEST: command={command}, text={request.form.get('text')}, user_id={user_id}")
    # バリデーション実施
    if command != '/start_interview':
        return jsonify({'status': Status.NG.value, 'data': 'invalid command'})
    if user_id not in allowed_user_ids:
        return jsonify({'status': Status.NG.value, 'data': 'invalid user'})
    if len(paras) != 3:
        return jsonify({'status': Status.NG.value, 'data': 'invalid params num'})
    # slackの operation timeout問題対応として、return後にslackメッセージを送信する
    t = threading.Thread(target=begin_interview_and_send_to_slack, args=[response_url, paras])
    t.start()
    return "インタビュー開始中。。。"


####################################
# サマリ取得系
####################################

def get_summary():
    print("get_summary")
    url = "https://interviewer-bot-api-dot-project-slack-gpt.dt.r.appspot.com/collect"
    response = requests.get(url)
    print("J res: " + response.text)
    # レスポンスNGのケース
    if not response.json()['ok']:
        return jsonify(
            {'status': Status.NG.value, 'data': {'ok': response.json()['ok'], 'reason': response.json()['reason']}})
    return response.json()['message']


# slackのコマンド実行時は以下のエンドポイントがコールされる
@app.route('/get_summary_from_command', methods=['POST'])
def get_summary_from_command():
    allowed_user_ids = ['U05GCA6R3QC', 'U05HRSNAX6X', 'U05H9NTA1S7']  # 事務局のuser_id
    command = request.form.get('command')  # Slackコマンド
    user_id = request.form.get('user_id')  # コマンド実行ユーザ
    response_url = request.form.get('response_url')
    print(f"response_url={response_url}")
    if command != '/get_summary':
        return jsonify({'status': Status.NG.value, 'data': 'invalid command'})
    if user_id not in allowed_user_ids:
        return jsonify({'status': Status.NG.value, 'data': 'invalid user'})
    # slackの operation timeout問題対応として、return後にslackメッセージを送信する
    t = threading.Thread(target=get_summary_and_send_to_slack, args=[response_url])
    t.start()
    return "要約中。。。"


def send_message(target, message):
    url = 'https://slack.com/api/chat.postMessage'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + slack_token
    }
    data = {
        'channel': target,
        'text': message
    }
    response = requests.post(url, headers=headers, json=data)
    print(response)


def send_message_url(url, target, message):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + slack_token
    }
    data = {
        'channel': target,
        'text': message
    }
    response = requests.post(url, headers=headers, json=data)
    print(response)


def begin_interview_and_send_to_slack(url, paras):
    result = begin_interview(subject=paras[0], approach=paras[1], target=paras[2])
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + slack_token
    }
    data = {
        'text': result
    }
    response = requests.post(url, headers=headers, json=data)
    print(response)


def get_summary_and_send_to_slack(url):
    result = get_summary()
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + slack_token
    }
    data = {
        'text': result
    }
    response = requests.post(url, headers=headers, json=data)
    print(response)


if __name__ == "__main__":
    app.run(port=3000)
