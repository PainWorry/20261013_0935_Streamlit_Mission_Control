# Mission Control: ระบบติดตามและยืนยันคำสั่งงาน

ระบบติดตามคำสั่งงาน พัฒนาด้วย Streamlit เชื่อมต่อ Google Sheets และแจ้งเตือนผ่าน Microsoft Teams / Email ออกแบบตามสถาปัตยกรรม Dual-Confirmation Protocol

## โครงสร้างโปรเจกต์
```text
20261013_Streamlit_Mission_Control_0935/
├── .streamlit/
│   └── secrets.toml.example  # เทมเพลตสำหรับตั้งค่า PIN, Webhook และ Google Sheets
├── app.py                    # โค้ดหลักระบบ Mission Control (ภาษาไทย)
├── plan.md                   # แผนสถาปัตยกรรมระบบและ Data Contract
├── requirements.txt          # รายการ Library ที่ใช้งาน
└── README.md                 # เอกสารคู่มือการใช้งาน
```

## วิธีติดตั้งและเริ่มใช้งานในเครื่อง (Local Testing)
1. ติดตั้ง Dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
2. คัดลอกและตั้งค่า Secrets:
   ```powershell
   Copy-Item .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
   จากนั้นแก้ไขค่า Webhook, Spreadsheet URL และ PIN ในไฟล์ `.streamlit/secrets.toml`
3. รันแอปพลิเคชัน:
   ```powershell
   streamlit run app.py
   ```
