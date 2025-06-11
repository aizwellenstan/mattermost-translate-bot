from mattermostdriver import Driver
import json
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
import chinese_converter
from deep_translator import GoogleTranslator
import re

team = "secondteam"

mm = Driver({
    'url': 'your-mattermost-server',
    "token": "your-matttermost-token",
    'scheme': 'https',
    'port': 443
})
mm.login()

channel = ["it-log", "it-support"]
last_id = ""
translate_breake = "\n\n\n\n\n"

def guess_source_language(text):
    # 文単位で分割（句点や改行で分割）
    sentences = re.split(r'[。．.!?\n]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return 'auto'

    lang_count = {}
    total = len(sentences)

    for sentence in sentences:
        try:
            lang = detect(sentence)
        except LangDetectException:
            lang = 'unknown'
        lang_count[lang] = lang_count.get(lang, 0) + 1

    # 50%以上を超える言語を判定
    for lang, count in lang_count.items():
        if count / total >= 0.5:
            if lang.startswith('zh'):
                return 'zh-TW'
            if lang == 'ja':
                return 'ja'
            if lang == 'en':
                return 'en'
            return 'zh-TW'
    return 'zh-TW'


async def my_event_handler(e):
    global last_id, team

    message = json.loads(e)
    event = message.get('event', 'ok')

    if event in ["posted", "post_edited"]:
        print("Create or Edit Post")
        post_data = json.loads(message['data']['post'])
        post_id = post_data['id']

        if "MatterMostTranslate:" in post_data['message']:
            return  # すでに翻訳済み

        if post_id != last_id:
            print(f"Message ID: {post_id}")
            print(f"Last ID: {last_id}")

            raw_message = post_data['message']
            message_end = raw_message.find(translate_breake)
            source_message = raw_message if message_end == -1 else raw_message[:message_end]
            source_message = source_message.replace("\n\n", "\n").replace("@", "")  # クリーンアップ

            print("Source message:", source_message)

            source_lang = guess_source_language(source_message)
            print(f"Detected source language (guess): {source_lang}")

            msg = source_message + translate_breake + "MatterMostTranslate:\n\n"

            targets = {
                "🇬🇧": "en",
                "🇹🇼": "zh-TW",
                "🇯🇵": "ja"
            }

            for flag, target_lang in targets.items():
                # 同じ言語は翻訳不要
                if source_lang.startswith(target_lang.split('-')[0]):
                    continue
                try:
                    translated = GoogleTranslator(source=source_lang, target=target_lang).translate(source_message)
                    if target_lang == 'zh-TW':
                        translated = chinese_converter.to_traditional(translated)
                    msg += f">{flag} {translated}\n\n"
                except Exception as e:
                    print(f"Translation error ({flag}):", e)
                    msg += f">{flag} [Translation error]\n\n"

            # チャンネルタイプ判定して投稿更新 or 新規返信
            channel_type = message['data'].get('channel_type', "F")

            if channel_type == "D":
                channel_name = message['data']['channel_name']
                channel_info = mm.channels.get_channel_by_name_and_team_name(team, channel_name)
                channel_id = channel_info['id']
                mm.posts.create_post(options={
                    'channel_id': channel_id,
                    'message': msg,
                    'root_id': post_id
                })
            else:
                mm.posts.update_post(post_id, options={
                    'message': msg,
                    'id': post_id
                })

            last_id = post_id
        else:
            last_id = ""

mm.init_websocket(my_event_handler)
