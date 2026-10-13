# Mission Control: ระบบติดตามและยืนยันคำสั่งงาน

ระบบติดตามคำสั่งงาน ออกแบบตามโครงสร้าง Excel View (แบบย่อ / แบบเต็ม) พัฒนาด้วย Streamlit รองรับระบบยืนยันตัวตนรายบุคคล (11 ผู้ใช้งาน) ด้วยแป้นกดตัวเลข PIN สไตล์มือถือ (0-9) และระบบแจ้งเตือนแบบเรียลไทม์เข้ากลุ่มแชต Microsoft Teams Group Chat

---

## สารบัญ
1. [โครงสร้างโปรเจกต์](#โครงสร้างโปรเจกต์)
2. [ขั้นตอนการตั้งค่า Microsoft Teams Webhook](#ขั้นตอนการตั้งค่า-microsoft-teams-webhook)
3. [การกำหนดค่าใน Secrets](#การกำหนดค่าใน-secrets)
4. [วิธีติดตั้งและเริ่มใช้งานบนเครื่อง (Local Testing)](#วิธีติดตั้งและเริ่มใช้งานบนเครื่อง-local-testing)
5. [การ Deploy บน Streamlit Community Cloud](#การ-deploy-บน-streamlit-community-cloud)

---

## โครงสร้างโปรเจกต์
```text
20261013_0935_Streamlit_Mission_Control/
├── .streamlit/
│   ├── secrets.toml          # ไฟล์คอนฟิกจริง (ไม่ commit ขึ้น git)
│   └── secrets.toml.example  # เทมเพลตสำหรับตั้งค่า PIN, Webhook และ Google Sheets
├── app.py                    # ซอร์สโค้ดหลักระบบ Mission Control (ภาษาไทย)
├── proposal.md               # ข้อเสนอโครงการเดิม
├── 20261013_0958_plan.md     # แผนสถาปัตยกรรมระบบ Data Contract
├── requirements.txt          # รายการ Library ที่ใช้งาน
├── run.ps1                   # สคริปต์รันแอปพลิเคชันแบบ Turnkey ใน .venv
└── README.md                 # เอกสารคู่มือการใช้งาน
```

---

## ขั้นตอนการตั้งค่า Microsoft Teams Webhook

> **First you have to create workflow in Power Automate / Microsoft Teams Workflows** เพื่อสร้าง HTTP Webhook URL สำหรับรับข้อความแจ้งเตือน

### วิธีการสร้าง Webhook ผ่าน Workflows ในห้องแชต (แนะนำ):
1. **เปิดแอป Workflows ในห้องแชต**:
   - เลื่อนลงมาที่ช่องพิมพ์ข้อความในห้องแชต (Group Chat ที่มี 12 คน เช่น `OLT Digital Technology`)
   - คลิกที่เครื่องหมายบวก (`+`) หรือจุดสามจุด (`...`) ใต้ช่องพิมพ์ข้อความ แล้วเลือกแอป **Workflows**
2. **คลิกปุ่ม "Create workflows"**:
   - คลิกปุ่ม **"Create workflows"** ที่มุมขวาบนของกล่องป๊อปอัป (ปุ่มสี่เหลี่ยมสีเทาเข้มข้างคำว่า Workflows)
3. **ค้นหาเทมเพลต**:
   - เมื่อหน้าต่างเลือกเทมเพลตเปิดขึ้นมา ที่ช่องค้นหาด้านบน ให้พิมพ์คำว่า: `webhook`
   - คุณจะเห็นการ์ดเทมเพลตชื่อ:
     > **`Post message in a chat when a webhook request is received`**
     *(หรือหากไม่พบชื่อนี้ ให้เลือก `Post to a channel when a webhook request is received`)*
4. **ยืนยันการเชื่อมต่อ**:
   - คลิกที่การ์ดเทมเพลตนั้น ระบบจะแสดงการเชื่อมต่อบัญชี Microsoft Teams ของคุณ (ขึ้นเครื่องหมายถูกสีเขียว)
   - คลิกปุ่ม **Next** (ถัดไป) ด้านล่าง
5. **เลือกห้องแชตและบันทึก**:
   - ในช่อง **Chat** หรือ **Channel**: ตรวจสอบว่าถูกเลือกเป็นกลุ่มแชตปัจจุบันของคุณ (`OLT Digital Technology`)
   - คลิกปุ่ม **Create flow** (หรือ Add workflow)
6. **คัดลอก Webhook URL**:
   - ระบบจะสร้าง Flow สำเร็จ และแสดงกล่องข้อความที่มี **HTTP POST URL** ยาวๆ
   - คลิกปุ่ม **Copy** แล้วนำลิงก์นั้นไปวางใน `secrets.toml` ได้ทันที

---

### วิธีการสร้างแบบ Manual ผ่าน Power Automate Portal (ทางเลือกสำรอง):
1. เข้าไปที่ [make.powerautomate.com](https://make.powerautomate.com)
2. เมนูด้านซ้ายเลือก **Create** -> **Instant cloud flow**
3. เลือก Trigger: **"When a Teams webhook request is received"** (หรือ **"When an HTTP request is received"**)
4. เพิ่ม Action: **"Post message in a chat or channel"**
   - Post as: `Flow bot`
   - Post in: `Group chat`
   - Group chat: เลือกกลุ่มแชตของทีม
   - Message: ใส่เนื้อหา Dynamic content จาก Trigger
5. กด **Save** แล้วคัดลอก **HTTP POST URL** จากกล่อง Trigger แรก

---

## การกำหนดค่าใน Secrets

นำ Webhook URL ที่ได้ไปวางในไฟล์ `.streamlit/secrets.toml`:

```toml
# รหัสลับสำหรับขอรีเซ็ตรหัสผ่าน (Master Reset Code)
[security]
admin_reset_code = "KuromiBlackCat"
admin_contact = "Herren@Onelink.co.th"

# URL ของเว็บแอป
app_url = "http://localhost:8501"

# การเชื่อมต่อ Microsoft Teams Group Chat
[teams]
webhook_url = "https://prod-xx.southeastasia.logic.azure.com:443/workflows/xxxx/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=xxxx"

# การเชื่อมต่อ Google Sheets ผ่าน Streamlit (หากใช้งาน)
[connections.gsheets]
spreadsheet = "https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID_HERE/edit"
```

---

## วิธีติดตั้งและเริ่มใช้งานบนเครื่อง (Local Testing)

1. รันผ่านสคริปต์ Turnkey PowerShell (จะติดตั้ง dependencies ใน `.venv` อัตโนมัติ):
   ```powershell
   powershell -ExecutionPolicy Bypass -File run.ps1
   ```
2. หรือรันผ่าน Streamlit โดยตรง:
   ```powershell
   .\.venv\Scripts\streamlit.exe run app.py
   ```
3. เปิดเบราว์เซอร์ไปที่ `http://localhost:8501`
   - **Username**: เช่น `herren.k`, `nataphon.p` (แสดง placeholder เป็น `herren.k`)
   - **PIN เริ่มต้น**: `111111` (ระบบจะให้ตั้ง PIN 6 หลักใหม่ในการเข้าครั้งแรก)
   - **ลืมรหัสผ่าน**: ติดต่อ `Herren@Onelink.co.th` ใช้รหัสลับ `KuromiBlackCat`

---

## การ Deploy บน Streamlit Community Cloud

1. นำโค้ดขึ้น GitHub Repository (Private)
2. เข้าสู่ระบบที่ [share.streamlit.io](https://share.streamlit.io) แล้วกด **Create app**
3. เลือก Repository: `PainWorry/20261013_0935_Streamlit_Mission_Control` | Branch: `main` | Main file: `app.py`
4. ไปที่ **Settings** -> **Secrets** แล้ววางข้อมูลจาก `.streamlit/secrets.toml`
5. กด **Save** และเริ่มใช้งานได้ทันที
