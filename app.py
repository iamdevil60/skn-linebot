import os
import csv
import io
import urllib.request
import anthropic
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage, FlexMessage, FlexCarousel, FlexBubble,
    FlexBox, FlexText, FlexSeparator, FlexButton, FlexImage, URIAction, PostbackAction
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, PostbackEvent

app = Flask(__name__)

CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "ec13fef6789938fb2f4bfa0053e24922")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "AS9iC1Gsi0vhK2wtreKqlE0yB9twviXp+JjchPzWGZA0wXXZ06AB5n1irM5iwPZLNfIxc5sYbNuuEr5+4ATch/w2igVeMptfMJd7KAbpEbjx/aEFhOaXsjf9KmxMfbphstrybpBfAtl9L7G1tdp3iwdB04t89/1O/w1cDnyilFU=")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1WCh7nGdhECzj8Ipl6IxTuDqKsRjABg50XFyZZ2rhQUc")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/%E0%B8%95%E0%B8%A3%E0%B8%B2%E0%B9%80%E0%B8%AA%E0%B8%A1%E0%B8%B2_%28%E0%B8%8A%E0%B8%A1%E0%B8%9E%E0%B8%B9_-_%E0%B8%9F%E0%B9%89%E0%B8%B2%29.png/250px-%E0%B8%95%E0%B8%A3%E0%B8%B2%E0%B9%80%E0%B8%AA%E0%B8%A1%E0%B8%B2_%28%E0%B8%8A%E0%B8%A1%E0%B8%9E%E0%B8%B9_-_%E0%B8%9F%E0%B9%89%E0%B8%B2%29.png"

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

LIST_THRESHOLD = 5
MAX_BUBBLES = 10
MAX_LIST_ITEMS = 10


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


def extract_keywords_with_ai(query):
    if not ANTHROPIC_API_KEY:
        return [normalize_keyword(query)]
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": (
                    "ข้อมูลมีคอลัมน์: รุ่น, ยศ, ชื่อ-สกุล, ชื่อเล่น, ตำแหน่ง, โทร\n"
                    "จากประโยคต่อไปนี้ ให้แยก keyword สำหรับค้นหาออกมา "
                    "ตอบเป็น keyword เท่านั้น คั่นด้วยจุลภาค ไม่ต้องอธิบาย\n"
                    f"ประโยค: {query}"
                )
            }]
        )
        raw = message.content[0].text.strip()
        keywords = [k.strip() for k in raw.split(",") if k.strip()]
        return keywords if keywords else [normalize_keyword(query)]
    except Exception:
        return [normalize_keyword(query)]


def normalize_keyword(keyword):
    k = keyword.strip().lower()
    for prefix in ["รุ่นที่", "รุ่น"]:
        if k.startswith(prefix):
            k = k[len(prefix):].strip()
            break
    return k


def search_alumni(keywords):
    if isinstance(keywords, str):
        keywords = [normalize_keyword(keywords)]
    else:
        keywords = [normalize_keyword(k) for k in keywords]

    try:
        rows = fetch_sheet_data()
    except Exception as e:
        return None, f"เกิดข้อผิดพลาดในการดึงข้อมูล: {e}"

    results = []
    for row in rows:
        haystack = " ".join([
            row["รุ่น"], row["ยศ"], row["ชื่อ-สกุล"], row["ชื่อเล่น"], row["ตำแหน่ง"]
        ]).lower()
        if all(k in haystack for k in keywords):
            results.append(row)

    return results, None


def find_person_by_name(fullname):
    try:
        rows = fetch_sheet_data()
    except Exception:
        return None
    for row in rows:
        if row["ชื่อ-สกุล"] == fullname:
            return row
    return None


def build_header():
    return FlexBox(
        layout="horizontal",
        background_color="#1565c0",
        padding_all="md",
        spacing="md",
        contents=[
            FlexImage(url=LOGO_URL, size="40px", aspect_mode="fit", flex=0),
            FlexText(
                text="ศิษย์เก่า สวนกุหลาบนนท์",
                color="#ffffff",
                size="sm",
                weight="bold",
                gravity="center"
            )
        ]
    )


def build_bubble(r):
    name = f"{r['ยศ']} {r['ชื่อ-สกุล']}".strip()

    body_contents = [
        FlexText(text=name, weight="bold", size="md", color="#1a237e", wrap=True),
    ]
    if r["ชื่อเล่น"]:
        body_contents.append(FlexText(text=f"ชื่อเล่น: {r['ชื่อเล่น']}", size="sm", color="#555555", margin="xs"))
    if r["รุ่น"]:
        body_contents.append(FlexText(text=f"รุ่น: {r['รุ่น']}", size="sm", color="#555555", margin="xs"))
    if r["ตำแหน่ง"]:
        body_contents.append(FlexSeparator(margin="md"))
        body_contents.append(FlexText(text=r["ตำแหน่ง"], size="sm", color="#333333", wrap=True, margin="md"))

    footer_contents = []
    if r["โทร"]:
        footer_contents.append(
            FlexButton(
                action=URIAction(label=f"📞 {r['โทร']}", uri=f"tel:{r['โทร']}"),
                style="primary", color="#1565c0", height="sm"
            )
        )

    return FlexBubble(
        header=build_header(),
        body=FlexBox(layout="vertical", contents=body_contents, padding_all="lg"),
        footer=FlexBox(layout="vertical", contents=footer_contents, padding_all="md") if footer_contents else None,
        styles={"header": {"backgroundColor": "#1565c0"}, "body": {"backgroundColor": "#ffffff"}}
    )


ITEMS_PER_BUBBLE = 10


def build_list_bubble(results, page, total):
    body_contents = []
    if page == 0:
        body_contents.append(
            FlexText(text=f"พบ {total} รายการ — เลือกดูรายละเอียด", size="sm", color="#555555", wrap=True, margin="none")
        )

    for r in results:
        label = f"{r['ยศ']} {r['ชื่อ-สกุล']}".strip()
        if r["ชื่อเล่น"]:
            label += f" ({r['ชื่อเล่น']})"
        if len(label) > 40:
            label = label[:39] + "…"

        body_contents.append(FlexSeparator(margin="sm"))
        body_contents.append(
            FlexButton(
                action=PostbackAction(
                    label=label,
                    data=f"detail:{r['ชื่อ-สกุล']}",
                    display_text=f"ดูข้อมูล {r['ยศ']} {r['ชื่อ-สกุล']}"
                ),
                style="link",
                color="#1565c0",
                height="sm",
                margin="none"
            )
        )

    return FlexBubble(
        header=build_header(),
        body=FlexBox(layout="vertical", contents=body_contents, padding_all="lg"),
        styles={"header": {"backgroundColor": "#1565c0"}, "body": {"backgroundColor": "#ffffff"}}
    )


def build_list_message(results):
    total = len(results)
    chunks = [results[i:i+ITEMS_PER_BUBBLE] for i in range(0, total, ITEMS_PER_BUBBLE)]
    bubbles = [build_list_bubble(chunk, idx, total) for idx, chunk in enumerate(chunks)]
    if len(bubbles) == 1:
        return FlexMessage(alt_text=f"พบ {total} รายการ กรุณาเลือก", contents=bubbles[0])
    return FlexMessage(alt_text=f"พบ {total} รายการ กรุณาเลือก", contents=FlexCarousel(contents=bubbles))


def build_flex_message(results):
    bubbles = [build_bubble(r) for r in results[:MAX_BUBBLES]]
    alt_text = f"พบ {len(results)} รายการ" if len(results) > 1 else f"{results[0]['ยศ']} {results[0]['ชื่อ-สกุล']}"
    if len(bubbles) == 1:
        return FlexMessage(alt_text=alt_text, contents=bubbles[0])
    return FlexMessage(alt_text=alt_text, contents=FlexCarousel(contents=bubbles))


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


@handler.add(PostbackEvent)
def handle_postback(event):
    try:
        data = event.postback.data
        if not data.startswith("detail:"):
            return

        fullname = data[len("detail:"):]
        person = find_person_by_name(fullname)

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            if not person:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"ไม่พบข้อมูลของ {fullname}")]
                    )
                )
                return
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(
                        alt_text=f"{person['ยศ']} {person['ชื่อ-สกุล']}",
                        contents=build_bubble(person)
                    )]
                )
            )
    except Exception as e:
        app.logger.error(f"handle_postback error: {e}", exc_info=True)


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    try:
        text = event.message.text.strip()

        if event.source.type != "group":
            return

        group_id = event.source.group_id

        if text == "#groupid":
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

            keywords = extract_keywords_with_ai(keyword)
            results, error = search_alumni(keywords)

            if error:
                line_bot_api.reply_message(
                    ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=error)])
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

            # เกิน 5 รายการ → แสดงรายชื่อให้เลือกก่อน
            if len(results) > LIST_THRESHOLD:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[build_list_message(results)]
                    )
                )
            else:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[build_flex_message(results)]
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
