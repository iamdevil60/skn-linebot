import os
import csv
import io
import urllib.request
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage, FlexMessage, FlexCarousel, FlexBubble,
    FlexBox, FlexText, FlexSeparator, FlexButton, URIAction
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "ec13fef6789938fb2f4bfa0053e24922")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "AS9iC1Gsi0vhK2wtreKqlE0yB9twviXp+JjchPzWGZA0wXXZ06AB5n1irM5iwPZLNfIxc5sYbNuuEr5+4ATch/w2igVeMptfMJd7KAbpEbjx/aEFhOaXsjf9KmxMfbphstrybpBfAtl9L7G1tdp3iwdB04t89/1O/w1cDnyilFU=")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1WCh7nGdhECzj8Ipl6IxTuDqKsRjABg50XFyZZ2rhQUc")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

MAX_BUBBLES = 10


def fetch_sheet_data():
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv"
    with urllib.request.urlopen(url) as response:
        content = response.read().decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content))
    rows = []
    next(reader, None)
    for cols in reader:
        if len(cols) < 6:
            continue
        rows.append({
            "รุ่น": cols[0].strip(),
            "ยศ": cols[1].strip(),
            "ชื่อ-สกุล": cols[2].strip(),
            "ชื่อเล่น": cols[3].strip(),
            "ตำแหน่ง": cols[4].strip(),
            "โทร": cols[5].strip(),
        })
    return rows


def normalize_keyword(keyword):
    k = keyword.strip().lower()
    # "#รุ่น58" หรือ "#รุ่นที่58" → "58"
    for prefix in ["รุ่นที่", "รุ่น"]:
        if k.startswith(prefix):
            k = k[len(prefix):].strip()
            break
    return k


def search_alumni(keyword):
    keyword = normalize_keyword(keyword)
    try:
        rows = fetch_sheet_data()
    except Exception as e:
        return None, f"เกิดข้อผิดพลาดในการดึงข้อมูล: {e}"

    results = []
    for row in rows:
        haystack = " ".join([
            row["รุ่น"], row["ยศ"], row["ชื่อ-สกุล"], row["ชื่อเล่น"], row["ตำแหน่ง"]
        ]).lower()
        if keyword in haystack:
            results.append(row)

    return results, None


def build_bubble(r):
    name = f"{r['ยศ']} {r['ชื่อ-สกุล']}".strip()
    nickname = r["ชื่อเล่น"]
    position = r["ตำแหน่ง"]
    phone = r["โทร"]
    gen = r["รุ่น"]

    body_contents = [
        FlexText(
            text=name,
            weight="bold",
            size="md",
            color="#1a237e",
            wrap=True
        ),
    ]

    if nickname:
        body_contents.append(
            FlexText(
                text=f"ชื่อเล่น: {nickname}",
                size="sm",
                color="#555555",
                margin="xs"
            )
        )

    if gen:
        body_contents.append(
            FlexText(
                text=f"รุ่น: {gen}",
                size="sm",
                color="#555555",
                margin="xs"
            )
        )

    if position:
        body_contents.append(FlexSeparator(margin="md"))
        body_contents.append(
            FlexText(
                text=position,
                size="sm",
                color="#333333",
                wrap=True,
                margin="md"
            )
        )

    footer_contents = []
    if phone:
        footer_contents.append(
            FlexButton(
                action=URIAction(label=f"📞 {phone}", uri=f"tel:{phone}"),
                style="primary",
                color="#1565c0",
                height="sm"
            )
        )

    bubble = FlexBubble(
        header=FlexBox(
            layout="vertical",
            background_color="#1565c0",
            padding_all="md",
            contents=[
                FlexText(
                    text="🚔 ศิษย์เก่า สวนกุหลาบนนท์",
                    color="#ffffff",
                    size="xs",
                    weight="bold"
                )
            ]
        ),
        body=FlexBox(
            layout="vertical",
            contents=body_contents,
            padding_all="lg"
        ),
        footer=FlexBox(
            layout="vertical",
            contents=footer_contents,
            padding_all="md"
        ) if footer_contents else None,
        styles={
            "header": {"backgroundColor": "#1565c0"},
            "body": {"backgroundColor": "#ffffff"},
        }
    )
    return bubble


def build_flex_message(results, keyword):
    bubbles = [build_bubble(r) for r in results[:MAX_BUBBLES]]

    alt_text = f"พบ {len(results)} รายการ" if len(results) > 1 else f"{results[0]['ยศ']} {results[0]['ชื่อ-สกุล']}"

    if len(bubbles) == 1:
        return FlexMessage(alt_text=alt_text, contents=bubbles[0])
    else:
        return FlexMessage(
            alt_text=alt_text,
            contents=FlexCarousel(contents=bubbles)
        )


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    try:
        text = event.message.text.strip()

        if event.source.type != "group":
            return

        group_id = event.source.group_id

        if text.strip() == "#groupid":
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"Group ID: {group_id}")]
                    )
                )
            return

        allowed_groups = [g.strip() for g in os.environ.get("ALLOWED_GROUP_IDS", "").split(",") if g.strip()]
        if allowed_groups and group_id not in allowed_groups:
            return

        if not text.startswith("#"):
            return

        keyword = text[1:].strip()

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)

            if not keyword:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="กรุณาระบุคำค้นหา เช่น #สมชาย หรือ #รุ่น15")]
                    )
                )
                return

            results, error = search_alumni(keyword)

            if error:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=error)]
                    )
                )
                return

            if not results:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f'ไม่พบข้อมูลสำหรับ "{keyword}"')]
                    )
                )
                return

            messages = []
            if len(results) > MAX_BUBBLES:
                messages.append(TextMessage(
                    text=f"พบ {len(results)} รายการ (แสดง {MAX_BUBBLES} รายการแรก)"
                ))

            messages.append(build_flex_message(results, keyword))

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=messages
                )
            )

    except Exception as e:
        app.logger.error(f"handle_message error: {e}", exc_info=True)
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"เกิดข้อผิดพลาด: {e}")]
                    )
                )
        except Exception:
            pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
