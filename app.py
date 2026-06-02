import os
import csv
import io
import urllib.request
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "ec13fef6789938fb2f4bfa0053e24922")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "AS9iC1Gsi0vhK2wtreKqlE0yB9twviXp+JjchPzWGZA0wXXZ06AB5n1irM5iwPZLNfIxc5sYbNuuEr5+4ATch/w2igVeMptfMJd7KAbpEbjx/aEFhOaXsjf9KmxMfbphstrybpBfAtl9L7G1tdp3iwdB04t89/1O/w1cDnyilFU=")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1WCh7nGdhECzj8Ipl6IxTuDqKsRjABg50XFyZZ2rhQUc")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


def fetch_sheet_data():
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv"
    with urllib.request.urlopen(url) as response:
        content = response.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    rows = []
    for row in reader:
        rows.append({
            "รุ่น": row.get("﻿รุ่น", row.get("รุ่น", "")).strip(),
            "ยศ": row.get("ยศ", "").strip(),
            "ชื่อ-สกุล": row.get("ชื่อ-สกุล", "").strip(),
            "ชื่อเล่น": row.get("ชื่อเล่น", "").strip(),
            "ตำแหน่ง": row.get("ตำแหน่ง", "").strip(),
            "โทร": row.get("โทร", "").strip(),
        })
    return rows


def search_alumni(keyword):
    keyword = keyword.strip().lower()
    try:
        rows = fetch_sheet_data()
    except Exception as e:
        return f"เกิดข้อผิดพลาดในการดึงข้อมูล: {e}"

    results = []
    for row in rows:
        haystack = " ".join([
            row["รุ่น"], row["ยศ"], row["ชื่อ-สกุล"], row["ชื่อเล่น"]
        ]).lower()
        if keyword in haystack:
            results.append(row)

    if not results:
        return "ไม่พบข้อมูล"

    lines = []
    for r in results:
        name_part = f"{r['ยศ']} {r['ชื่อ-สกุล']}".strip()
        if r["ชื่อเล่น"]:
            name_part += f" ({r['ชื่อเล่น']})"
        parts = [name_part]
        if r["ตำแหน่ง"]:
            parts.append(r["ตำแหน่ง"])
        if r["โทร"]:
            parts.append(r["โทร"])
        lines.append(" | ".join(parts))

    header = f"พบ {len(results)} รายการ:\n" if len(results) > 1 else ""
    return header + "\n".join(lines)


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
    text = event.message.text.strip()

    if not text.startswith("#"):
        return

    keyword = text[1:].strip()
    if not keyword:
        reply = "กรุณาระบุคำค้นหา เช่น #สมชาย หรือ #รุ่น15"
    else:
        reply = search_alumni(keyword)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
