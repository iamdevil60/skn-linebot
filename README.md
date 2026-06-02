# LINE Bot ค้นหาศิษย์เก่าสวนกุหลาบนนท์ (ตำรวจ)

## วิธีใช้งาน
พิมพ์ `#` ตามด้วยคำค้นหา เช่น:
- `#สมชาย` — ค้นหาด้วยชื่อ
- `#วิทัศน์` — ค้นหาด้วยชื่อเล่น
- `#ร.ต.อ.` — ค้นหาด้วยยศ
- `#รุ่น15` — ค้นหาด้วยรุ่น

---

## Deploy บน Railway

### 1. เตรียม Repository
```bash
git init
git add .
git commit -m "initial commit"
```

### 2. สร้างโปรเจกต์บน Railway
1. ไปที่ [railway.app](https://railway.app) แล้ว Login
2. กด **New Project** → **Deploy from GitHub repo**
3. เลือก repo ที่สร้างไว้

### 3. ตั้งค่า Environment Variables
ใน Railway → Settings → Variables เพิ่ม:

| Key | Value |
|-----|-------|
| `LINE_CHANNEL_SECRET` | `ec13fef6789938fb2f4bfa0053e24922` |
| `LINE_CHANNEL_ACCESS_TOKEN` | (token ของคุณ) |
| `SPREADSHEET_ID` | `1WCh7nGdhECzj8Ipl6IxTuDqKsRjABg50XFyZZ2rhQUc` |

### 4. ตั้งค่า Webhook ใน LINE Developers
1. ไปที่ [developers.line.biz](https://developers.line.biz)
2. เลือก Channel → Messaging API
3. ตั้ง **Webhook URL** เป็น:
   ```
   https://<your-railway-domain>/callback
   ```
4. เปิด **Use webhook**
5. ปิด **Auto-reply messages**

---

## โครงสร้างไฟล์
```
linebot/
├── app.py           # Flask app หลัก
├── requirements.txt # Python dependencies
├── Procfile         # คำสั่ง start สำหรับ Railway
└── README.md
```
