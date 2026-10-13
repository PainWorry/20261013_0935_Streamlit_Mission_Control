import streamlit as st
import pandas as pd
from datetime import datetime
import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# กำหนดค่าหน้าจอ
st.set_page_config(
    page_title="Mission Control - ระบบติดตามและยืนยันคำสั่งงาน",
    page_icon="📋",
    layout="wide"
)

# โฟลเดอร์สำหรับเก็บข้อมูลกรณีทำงานในโหมด Offline / Local
LOCAL_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(LOCAL_DATA_DIR, exist_ok=True)
USERS_CSV = os.path.join(LOCAL_DATA_DIR, "users.csv")
ORDERS_CSV = os.path.join(LOCAL_DATA_DIR, "orders.csv")
LOGS_CSV = os.path.join(LOCAL_DATA_DIR, "order_logs.csv")

# รายชื่อผู้ใช้งานชุดแรก (11 คน พร้อมชื่อและตำแหน่ง)
DEFAULT_USERS_ROSTER = [
    {"username": "anuchat.s", "title": "Head DT"},
    {"username": "apinut.p", "title": "Junior Mgr"},
    {"username": "chayanat.k", "title": "IT sup"},
    {"username": "herren.k", "title": "Cloud En"},
    {"username": "khanin.n", "title": "IT sup"},
    {"username": "nataphon.p", "title": "CTO"},
    {"username": "niporn.n", "title": "Sen TSE"},
    {"username": "nuthapong.w", "title": "IT sup"},
    {"username": "sittisak.r", "title": "Soft sup"},
    {"username": "thatchai.w", "title": "Sen IT sup"},
    {"username": "imran.r", "title": "PM"},
]

# ----------------- ฟังก์ชันส่งการแจ้งเตือนเข้า Microsoft Teams และ Email -----------------
def send_teams_notification(order_id, title, creator, assignee, deadline, status, action_text):
    """ส่งการแจ้งเตือนแบบ Adaptive Card เข้ากลุ่มแชต Microsoft Teams ผ่าน Power Automate Webhook"""
    webhook_url = st.secrets.get("teams", {}).get("webhook_url", "")
    if not webhook_url:
        return False, "ยังไม่ได้ตั้งค่า Teams Webhook URL ใน secrets.toml"

    app_url = st.secrets.get("app_url", "")
    
    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": f"📢 แจ้งเตือนคำสั่งงาน: {action_text}",
                            "weight": "Bolder",
                            "size": "Medium",
                            "color": "Accent"
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "รหัสงาน:", "value": str(order_id)},
                                {"title": "ชื่องาน:", "value": str(title)},
                                {"title": "คนสั่ง:", "value": str(creator)},
                                {"title": "คนรับผิดชอบ:", "value": str(assignee)},
                                {"title": "กำหนดส่ง:", "value": str(deadline)},
                                {"title": "สถานะล่าสุด:", "value": str(status)}
                            ]
                        }
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "เปิดเข้าระบบ Mission Control",
                            "url": app_url if app_url else "https://streamlit.io"
                        }
                    ]
                }
            }
        ]
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.status_code in [200, 202], response.text
    except Exception as e:
        return False, str(e)


def send_email_notification(order_id, title, creator, assignee, deadline, status, action_text):
    """ส่งการแจ้งเตือนทาง Email (SMTP) สำหรับเป็นช่องทางสำรอง"""
    email_cfg = st.secrets.get("email", {})
    if not email_cfg.get("sender_email") or not email_cfg.get("sender_password"):
        return False, "ไม่ได้ตั้งค่า Email SMTP ใน secrets"

    app_url = st.secrets.get("app_url", "")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Mission Control] {action_text} - {order_id}: {title}"
    msg["From"] = email_cfg["sender_email"]
    msg["To"] = email_cfg.get("receiver_email", "")

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.5;">
        <h3 style="color: #0056b3;">แจ้งเตือนระบบ Mission Control</h3>
        <p><strong>การดำเนินการ:</strong> {action_text}</p>
        <table style="border-collapse: collapse; width: 100%; max-width: 500px;">
          <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9;"><strong>รหัสงาน</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{order_id}</td></tr>
          <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9;"><strong>ชื่องาน</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{title}</td></tr>
          <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9;"><strong>คนสั่ง</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{creator}</td></tr>
          <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9;"><strong>คนรับผิดชอบ</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{assignee}</td></tr>
          <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9;"><strong>กำหนดส่ง</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{deadline}</td></tr>
          <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9;"><strong>สถานะ</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{status}</td></tr>
        </table>
        <br/>
        <a href="{app_url}" style="background-color: #007bff; color: white; padding: 10px 16px; text-decoration: none; border-radius: 4px; display: inline-block;">เปิดดูรายการในระบบ</a>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_content, "html"))

    try:
        server = smtplib.SMTP(email_cfg.get("smtp_server", "smtp.gmail.com"), int(email_cfg.get("smtp_port", 587)))
        server.starttls()
        server.login(email_cfg["sender_email"], email_cfg["sender_password"])
        server.sendmail(email_cfg["sender_email"], [email_cfg["receiver_email"]], msg.as_string())
        server.quit()
        return True, "ส่งอีเมลสำเร็จ"
    except Exception as e:
        return False, str(e)

# ----------------- ระบบจัดการข้อมูล (Data Layer: GSheets + Local Fallback) -----------------
EMPTY_USERS_COLS = ["username", "display_name", "pin", "must_change_pin", "updated_at"]
EMPTY_ORDERS_COLS = [
    "order_id", "created_at", "task_title", "description", 
    "creator", "assignee", "recorded_by", "deadline", 
    "creator_confirmed", "assignee_confirmed", "status"
]
EMPTY_LOGS_COLS = ["log_id", "order_id", "timestamp", "author", "step_note"]

def is_gsheets_configured():
    try:
        return "connections" in st.secrets and "gsheets" in st.secrets["connections"]
    except Exception:
        return False

def get_initial_users_df():
    rows = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    for u in DEFAULT_USERS_ROSTER:
        rows.append({
            "username": u["username"].lower(),
            "display_name": f"{u['username']} {u['title']}",
            "pin": "111111",
            "must_change_pin": "True",
            "updated_at": now_str
        })
    return pd.DataFrame(rows)

def load_data():
    conn = None
    use_gsheets = is_gsheets_configured()
    users_df = pd.DataFrame(columns=EMPTY_USERS_COLS)
    orders_df = pd.DataFrame(columns=EMPTY_ORDERS_COLS)
    logs_df = pd.DataFrame(columns=EMPTY_LOGS_COLS)

    if use_gsheets:
        try:
            from streamlit_gsheets import GSheetsConnection
            conn = st.connection("gsheets", type=GSheetsConnection)
            
            raw_users = conn.read(worksheet="users", ttl=5)
            if raw_users is not None and not raw_users.empty and "username" in raw_users.columns:
                users_df = raw_users.astype(str)
            else:
                users_df = get_initial_users_df()
                conn.update(worksheet="users", data=users_df)

            raw_orders = conn.read(worksheet="orders", ttl=5)
            if raw_orders is not None and not raw_orders.empty and "order_id" in raw_orders.columns:
                orders_df = raw_orders.astype(str)

            raw_logs = conn.read(worksheet="order_logs", ttl=5)
            if raw_logs is not None and not raw_logs.empty and "log_id" in raw_logs.columns:
                logs_df = raw_logs.astype(str)

            return conn, users_df, orders_df, logs_df, "Google Sheets (Cloud Sync)"
        except Exception:
            pass

    # โหมด Local Storage Fallback
    if os.path.exists(USERS_CSV):
        try:
            users_df = pd.read_csv(USERS_CSV, dtype=str)
        except Exception:
            users_df = get_initial_users_df()
    else:
        users_df = get_initial_users_df()
        users_df.to_csv(USERS_CSV, index=False)

    if os.path.exists(ORDERS_CSV):
        try:
            orders_df = pd.read_csv(ORDERS_CSV, dtype=str)
        except Exception:
            orders_df = pd.DataFrame(columns=EMPTY_ORDERS_COLS)

    if os.path.exists(LOGS_CSV):
        try:
            logs_df = pd.read_csv(LOGS_CSV, dtype=str)
        except Exception:
            logs_df = pd.DataFrame(columns=EMPTY_LOGS_COLS)

    return None, users_df, orders_df, logs_df, "Local Offline Storage"

def save_users_data(conn, users_df):
    if conn is not None:
        try:
            conn.update(worksheet="users", data=users_df)
            return True
        except Exception:
            pass
    users_df.to_csv(USERS_CSV, index=False)
    return True

def save_orders_data(conn, orders_df):
    if conn is not None:
        try:
            conn.update(worksheet="orders", data=orders_df)
            return True
        except Exception:
            pass
    orders_df.to_csv(ORDERS_CSV, index=False)
    return True

def save_logs_data(conn, logs_df):
    if conn is not None:
        try:
            conn.update(worksheet="order_logs", data=logs_df)
            return True
        except Exception:
            pass
    logs_df.to_csv(LOGS_CSV, index=False)
    return True

# ----------------- โหลดข้อมูลระบบ -----------------
conn, users_df, orders_df, logs_df, db_status = load_data()

# รายชื่อ Display Name ทั้งหมดสำหรับ Dropdown (ชื่อ ตำแหน่ง)
ALL_DISPLAY_NAMES = list(users_df["display_name"].unique())

# ตรวจสอบ Session State ของการล็อกอิน (คงสถานะตลอดการเปิดเบราว์เซอร์)
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

if "pending_change_pin_user" not in st.session_state:
    st.session_state.pending_change_pin_user = None

if "show_forgot_password" not in st.session_state:
    st.session_state.show_forgot_password = False

# ----------------- หน้าจอบังคับเปลี่ยนรหัสผ่านครั้งแรก (First-time PIN Change) -----------------
if st.session_state.pending_change_pin_user:
    st.title("ตั้งรหัสผ่านใหม่ (กำหนดรหัส PIN 6 หลักของตนเอง)")
    p_user = st.session_state.pending_change_pin_user
    st.info(f"ยินดีต้อนรับคุณ **{p_user['display_name']}** เนื่องจากการเข้าสู่ระบบด้วยรหัสเริ่มต้น `111111` โปรดกำหนดรหัส PIN 6 หลักใหม่เพื่อความปลอดภัย")

    with st.form("set_new_pin_form"):
        new_pin = st.text_input("ตั้งรหัส PIN 6 หลักใหม่", type="password", max_chars=6, placeholder="••••••")
        confirm_pin = st.text_input("ยืนยันรหัส PIN 6 หลักอีกครั้ง", type="password", max_chars=6, placeholder="••••••")
        submit_new_pin = st.form_submit_button("บันทึกรหัสผ่านใหม่และเข้าสู่ระบบ", use_container_width=True)

        if submit_new_pin:
            if len(new_pin) != 6 or not new_pin.isdigit():
                st.error("รหัส PIN ต้องเป็นตัวเลข 6 หลักเท่านั้น")
            elif new_pin == "111111":
                st.error("ไม่สามารถใช้รหัสเริ่มต้น 111111 ได้ กรุณาตั้งรหัสอื่น")
            elif new_pin != confirm_pin:
                st.error("รหัสผ่านทั้งสองช่องไม่ตรงกัน")
            else:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                u_idx = users_df[users_df["username"] == p_user["username"]].index[0]
                users_df.loc[u_idx, "pin"] = str(new_pin)
                users_df.loc[u_idx, "must_change_pin"] = "False"
                users_df.loc[u_idx, "updated_at"] = now_str
                save_users_data(conn, users_df)

                st.session_state.auth_user = users_df.loc[u_idx].to_dict()
                st.session_state.pending_change_pin_user = None
                st.success("ตั้งรหัส PIN สำเร็จ เข้าสู่ระบบเรียบร้อย")
                st.rerun()

    if st.button("ยกเลิกและกลับหน้าเข้าสู่ระบบ"):
        st.session_state.pending_change_pin_user = None
        st.rerun()
    st.stop()

# ----------------- หน้าจอเข้าสู่ระบบ (Login Screen) -----------------
if not st.session_state.auth_user:
    st.title("Mission Control : ระบบติดตามและยืนยันคำสั่งงาน")
    st.subheader("เข้าสู่ระบบ (Login)")
    st.caption("ระบบเก็บประวัติการทำงานแบบรายบุคคล กรุณาเข้าสู่ระบบด้วย Username และรหัส PIN 6 หลัก")

    col1, col2 = st.columns([1, 1])
    with col1:
        entered_username = st.text_input("ชื่อผู้ใช้งาน (Username)", placeholder="herren.k")
        entered_pin = st.text_input("รหัส PIN 6 หลัก", type="password", max_chars=6, placeholder="••••••")
        
        login_btn = st.button("เข้าสู่ระบบ", use_container_width=True)
        if login_btn:
            u_clean = entered_username.strip().lower()
            matching_user = users_df[users_df["username"] == u_clean]
            
            if matching_user.empty:
                st.error("ไม่พบชื่อผู้ใช้งานนี้ในระบบ โปรดตรวจสอบตัวสะกด (เช่น herren.k, nataphon.p)")
            else:
                user_row = matching_user.iloc[0]
                stored_pin = str(user_row["pin"])
                must_change = str(user_row["must_change_pin"]).lower() == "true"
                
                if entered_pin == stored_pin:
                    if entered_pin == "111111" or must_change:
                        st.session_state.pending_change_pin_user = user_row.to_dict()
                        st.rerun()
                    else:
                        st.session_state.auth_user = user_row.to_dict()
                        st.success(f"เข้าสู่ระบบสำเร็จ: ยินดีต้อนรับคุณ {user_row['display_name']}")
                        st.rerun()
                else:
                    st.error("รหัส PIN 6 หลักไม่ถูกต้อง")

        st.divider()
        if st.button("ลืมรหัสผ่าน (Forgot Password)"):
            st.session_state.show_forgot_password = not st.session_state.show_forgot_password

    # หน้าต่างรีเซ็ตรหัสผ่าน (Secret Reset Workflow)
    if st.session_state.show_forgot_password:
        with col2:
            st.warning("⚠️ ขั้นตอนขอรีเซ็ตรหัสผ่าน")
            admin_contact = st.secrets.get("security", {}).get("admin_contact", "Herren@Onelink.co.th")
            st.markdown(f"1. โปรดติดต่อ Teams: **`{admin_contact}`** เพื่อยืนยันตัวตนจริง<br>2. เจ้าหน้าที่จะให้รหัสยืนยันพิเศษเพื่อนำมากรอกในช่องด้านล่าง", unsafe_allow_html=True)
            
            with st.form("forgot_pw_form"):
                reset_user_choice = st.selectbox("เลือกบัญชีของคุณ", options=ALL_DISPLAY_NAMES)
                secret_input = st.text_input("กรอกรหัสยืนยันจาก Herren (Secret Code)", type="password", placeholder="กรอกรหัสที่ได้รับ")
                new_reset_pin = st.text_input("ตั้งรหัส PIN 6 หลักใหม่", type="password", max_chars=6, placeholder="••••••")
                confirm_reset_pin = st.text_input("ยืนยันรหัส PIN 6 หลักใหม่อีกครั้ง", type="password", max_chars=6, placeholder="••••••")
                
                reset_submit = st.form_submit_button("ยืนยันการตั้งรหัสผ่านใหม่", use_container_width=True)
                if reset_submit:
                    expected_secret = st.secrets.get("security", {}).get("admin_reset_code", "KuromiBlackCat")
                    if secret_input.strip() != expected_secret:
                        st.error("รหัสยืนยันไม่ถูกต้อง โปรดตรวจสอบรหัสลับจาก Herren")
                    elif len(new_reset_pin) != 6 or not new_reset_pin.isdigit():
                        st.error("รหัส PIN ต้องเป็นตัวเลข 6 หลักเท่านั้น")
                    elif new_reset_pin != confirm_reset_pin:
                        st.error("รหัสผ่านใหม่ทั้งสองช่องไม่ตรงกัน")
                    else:
                        match_u = users_df[users_df["display_name"] == reset_user_choice]
                        if not match_u.empty:
                            u_idx = match_u.index[0]
                            users_df.loc[u_idx, "pin"] = str(new_reset_pin)
                            users_df.loc[u_idx, "must_change_pin"] = "False"
                            users_df.loc[u_idx, "updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                            save_users_data(conn, users_df)
                            st.success(f"รีเซ็ตรหัสผ่านสำหรับ {reset_user_choice} เรียบร้อยแล้ว! สามารถเข้าสู่ระบบด้วยรหัสใหม่ได้ทันที")
                            st.session_state.show_forgot_password = False
    st.stop()

# ----------------- แถบเมนูด้านข้าง (Sidebar) -----------------
current_user = st.session_state.auth_user
my_display_name = current_user["display_name"]

with st.sidebar:
    st.title("Mission Control")
    st.write(f"ผู้ใช้งาน: **{my_display_name}**")
    st.caption(f"สถานะฐานข้อมูล: `{db_status}`")
    
    if st.button("ออกจากระบบ (Logout)", use_container_width=True):
        st.session_state.auth_user = None
        st.session_state.pending_change_pin_user = None
        st.session_state.show_forgot_password = False
        st.rerun()
    
    st.divider()
    menu = st.radio("เมนูหลัก", [
        "กระดานติดตามงาน (Mission Control)",
        "สร้างคำสั่งงานใหม่",
        "บันทึกความคืบหน้ารายขั้นตอน",
        "ทดสอบการแจ้งเตือน (Teams Group Chat)"
    ])

# ----------------- เมนู 1: กระดานติดตามงาน (Mission Control Dashboard) -----------------
if menu == "กระดานติดตามงาน (Mission Control)":
    st.title("กระดานติดตามงาน (Mission Control Dashboard)")
    st.caption(f"ยินดีต้อนรับคุณ **{my_display_name}** | ติดตามสถานะงานและดำเนินการยืนยันแบบสองทาง (Dual-Confirmation)")

    # ตัวกรองงาน 4 มุมมอง (Personalized 4-View Filters)
    filter_tab = st.radio(
        "มุมมองรายการงาน:",
        ["งานทั้งหมด", "งานที่ฉันต้องทำ (Assignee)", "งานที่ฉันสั่ง (Creator)", "งานที่รอฉันยืนยัน (Pending Approval)"],
        horizontal=True
    )

    if orders_df.empty:
        st.info("ยังไม่มีรายการคำสั่งงานในระบบ กดที่เมนู 'สร้างคำสั่งงานใหม่' เพื่อเริ่มบันทึก")
    else:
        # กรองข้อมูลตามแถบมุมมอง
        if filter_tab == "งานที่ฉันต้องทำ (Assignee)":
            filtered_df = orders_df[orders_df["assignee"] == my_display_name]
        elif filter_tab == "งานที่ฉันสั่ง (Creator)":
            filtered_df = orders_df[orders_df["creator"] == my_display_name]
        elif filter_tab == "งานที่รอฉันยืนยัน (Pending Approval)":
            # งานที่รอฉันยืนยัน: ฉันเป็น creator และ creator_confirmed ยังรอยืนยัน หรือ ฉันเป็น assignee และ assignee_confirmed ยังรอยืนยัน หรือ งานรอตรวจสอบที่ฉันเป็น creator
            is_creator_pending = (orders_df["creator"] == my_display_name) & (orders_df["creator_confirmed"].str.contains("รอยืนยัน", na=False))
            is_assignee_pending = (orders_df["assignee"] == my_display_name) & (orders_df["assignee_confirmed"].str.contains("รอยืนยัน", na=False))
            is_creator_review_pending = (orders_df["creator"] == my_display_name) & (orders_df["status"] == "รอตรวจสอบ")
            filtered_df = orders_df[is_creator_pending | is_assignee_pending | is_creator_review_pending]
        else:
            filtered_df = orders_df

        st.caption(f"แสดงรายการงานจำนวน {len(filtered_df)} รายการ")

        if filtered_df.empty:
            st.info(f"ไม่พบรายการงานในหมวด '{filter_tab}'")
        else:
            for idx, row in filtered_df.iloc[::-1].iterrows():
                badge_status = str(row['status'])
                header_title = f"[{badge_status}] {row['order_id']} : {row['task_title']} | กำหนดส่ง: {row['deadline']}"
                
                with st.expander(header_title, expanded=(badge_status != "เสร็จสิ้น")):
                    col_info1, col_info2, col_info3 = st.columns(3)
                    with col_info1:
                        st.write(f"**คนสั่ง:** {row['creator']}")
                        st.write(f"**การยืนยันคนสั่ง:** {row['creator_confirmed']}")
                    with col_info2:
                        st.write(f"**คนรับผิดชอบ:** {row['assignee']}")
                        st.write(f"**การยืนยันคนรับผิดชอบ:** {row['assignee_confirmed']}")
                    with col_info3:
                        st.write(f"**สถานะปัจจุบัน:** {row['status']}")
                        recorded_by_val = row.get('recorded_by', row['creator'])
                        st.write(f"**ผู้ลงบันทึก:** {recorded_by_val}")
                        st.write(f"**สร้างเมื่อ:** {row['created_at']}")
                    
                    st.write("**รายละเอียดงานและเงื่อนไข:**")
                    st.info(str(row['description']))
                    
                    # ประวัติความคืบหน้ารายขั้นตอน (Step Logs)
                    item_logs = logs_df[logs_df["order_id"] == str(row["order_id"])]
                    if not item_logs.empty:
                        st.write("**ประวัติความคืบหน้า (Step Logs):**")
                        for _, lrow in item_logs.iterrows():
                            st.caption(f"• `[{lrow['timestamp']}]` โดย **{lrow['author']}**: {lrow['step_note']}")
                    
                    st.divider()
                    
                    # โซนปุ่มดำเนินการยืนยันงาน (Personalized Dual-Confirmation Actions)
                    btn_col1, btn_col2, btn_col3 = st.columns(3)
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    # 1. คนสั่งกดยืนยันคำสั่งงาน (กรณีเป็นคนสั่งจริงที่ล็อกอินอยู่)
                    if my_display_name == row['creator'] and "รอยืนยัน" in str(row['creator_confirmed']):
                        with btn_col1:
                            if st.button("คนสั่งยืนยันความถูกต้องคำสั่งงาน", key=f"creator_conf_{row['order_id']}", use_container_width=True):
                                orders_df.loc[idx, "creator_confirmed"] = f"ยืนยันแล้ว ({now_str})"
                                if "ยืนยันแล้ว" in str(orders_df.loc[idx, "assignee_confirmed"]):
                                    orders_df.loc[idx, "status"] = "กำลังดำเนินการ"
                                save_orders_data(conn, orders_df)
                                send_teams_notification(row['order_id'], row['task_title'], row['creator'], row['assignee'], row['deadline'], orders_df.loc[idx, "status"], f"{my_display_name} ยืนยันคำสั่งงานแล้ว")
                                st.success("บันทึกการยืนยันของคนสั่งสำเร็จ")
                                st.rerun()

                    # 2. คนรับผิดชอบตอบรับคำสั่งงาน (กรณีเป็นคนรับผิดชอบจริงที่ล็อกอินอยู่)
                    if my_display_name == row['assignee'] and "รอยืนยัน" in str(row['assignee_confirmed']):
                        with btn_col2:
                            if st.button("คนรับผิดชอบตอบรับคำสั่งงานนี้", key=f"assignee_conf_{row['order_id']}", use_container_width=True):
                                orders_df.loc[idx, "assignee_confirmed"] = f"ยืนยันแล้ว ({now_str})"
                                if "ยืนยันแล้ว" in str(orders_df.loc[idx, "creator_confirmed"]):
                                    orders_df.loc[idx, "status"] = "กำลังดำเนินการ"
                                save_orders_data(conn, orders_df)
                                send_teams_notification(row['order_id'], row['task_title'], row['creator'], row['assignee'], row['deadline'], orders_df.loc[idx, "status"], f"{my_display_name} ตอบรับคำสั่งงานแล้ว")
                                st.success("บันทึกการตอบรับงานสำเร็จ")
                                st.rerun()

                    # 3. คนรับผิดชอบส่งงานเพื่อขอตรวจสอบ (Assignee submits task)
                    if my_display_name == row['assignee'] and row['status'] == "กำลังดำเนินการ":
                        with btn_col2:
                            if st.button("ส่งงาน (ขอตรวจสอบความเรียบร้อย)", key=f"submit_task_{row['order_id']}", use_container_width=True):
                                orders_df.loc[idx, "status"] = "รอตรวจสอบ"
                                save_orders_data(conn, orders_df)
                                send_teams_notification(row['order_id'], row['task_title'], row['creator'], row['assignee'], row['deadline'], "รอตรวจสอบ", f"{my_display_name} ส่งมอบงานแล้ว กรุณาตรวจสอบ")
                                st.success("ส่งมอบงานเรียบร้อย รอคนสั่งตรวจสอบ")
                                st.rerun()

                    # 4. เฉพาะคนสั่งเท่านั้นที่มีสิทธิ์ตรวจรับและปิดงาน (Creator closes order)
                    if my_display_name == row['creator'] and row['status'] in ["รอตรวจสอบ", "กำลังดำเนินการ"]:
                        with btn_col3:
                            if st.button("ตรวจรับและปิดงาน (เสร็จสิ้น)", key=f"close_order_{row['order_id']}", use_container_width=True):
                                orders_df.loc[idx, "status"] = "เสร็จสิ้น"
                                save_orders_data(conn, orders_df)
                                send_teams_notification(row['order_id'], row['task_title'], row['creator'], row['assignee'], row['deadline'], "เสร็จสิ้น", f"{my_display_name} ตรวจรับและปิดงานเรียบร้อยแล้ว")
                                st.success("ปิดงานเรียบร้อย")
                                st.rerun()

# ----------------- เมนู 2: สร้างคำสั่งงานใหม่ -----------------
elif menu == "สร้างคำสั่งงานใหม่":
    st.title("บันทึกคำสั่งงานใหม่")
    st.caption("สามารถสร้างงานโดยตนเอง หรือจดบันทึกจากคำสั่งปากเปล่าแทนเพื่อนร่วมทีมได้ ระบบจะระบุชื่อผู้ลงบันทึกจริงเพื่อความโปร่งใส")

    with st.form("new_order_form"):
        task_title = st.text_input("ชื่องาน / สรุปประเด็นคำสั่ง", placeholder="เช่น ปรับปรุง Cloud Security, ตรวจสอบ Network Switches")
        description = st.text_area("รายละเอียดงานทั้งหมด", placeholder="ระบุขอบเขตงาน รายละเอียดสำคัญ เงื่อนไข หรือข้อตกลงที่ระบุไว้")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            creator_default_idx = ALL_DISPLAY_NAMES.index(my_display_name) if my_display_name in ALL_DISPLAY_NAMES else 0
            selected_creator = st.selectbox("คนสั่ง (Creator)", options=ALL_DISPLAY_NAMES, index=creator_default_idx)
        with c2:
            selected_assignee = st.selectbox("คนรับผิดชอบ (Assignee)", options=ALL_DISPLAY_NAMES, index=0)
        with c3:
            deadline = st.text_input("กำหนดส่ง (Deadline)", placeholder="เช่น 2026-10-16 17:00")
            
        notify_channel = st.multiselect("ส่งการแจ้งเตือนทันทีไปยัง", ["Microsoft Teams (Chat Group)", "Email"], default=["Microsoft Teams (Chat Group)"])
        
        submitted = st.form_submit_button("บันทึกคำสั่งงาน", use_container_width=True)
        if submitted:
            if not task_title or not description:
                st.error("กรุณาระบุชื่องานและรายละเอียดงานให้ครบถ้วน")
            else:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # กำหนดสถานะยืนยันตามตัวตนของผู้บันทึก
                if my_display_name == selected_creator:
                    creator_conf = f"ยืนยันแล้ว ({now_str})"
                    assignee_conf = "รอยืนยัน (รอคนรับผิดชอบตอบรับ)"
                    init_status = "รอคนรับผิดชอบตอบรับ"
                else:
                    # ผู้บันทึกพิมพ์แทนคนสั่ง (เช่น จดจากคำสั่งปากเปล่า)
                    creator_conf = f"รอยืนยัน (รอ {selected_creator} ตรวจสอบ)"
                    assignee_conf = f"ยืนยันแล้ว ({now_str})" if my_display_name == selected_assignee else "รอยืนยัน"
                    init_status = "รอคนสั่งยืนยัน"
                
                new_row = pd.DataFrame([{
                    "order_id": order_id,
                    "created_at": now_str,
                    "task_title": task_title,
                    "description": description,
                    "creator": selected_creator,
                    "assignee": selected_assignee,
                    "recorded_by": my_display_name,
                    "deadline": deadline,
                    "creator_confirmed": creator_conf,
                    "assignee_confirmed": assignee_conf,
                    "status": init_status
                }])
                
                updated_orders = pd.concat([orders_df, new_row], ignore_index=True)
                save_orders_data(conn, updated_orders)
                
                # ส่งการแจ้งเตือน
                action_msg = f"มีคำสั่งงานใหม่: {selected_creator} สั่งให้ {selected_assignee} รับผิดชอบ"
                if "Microsoft Teams (Chat Group)" in notify_channel:
                    send_teams_notification(order_id, task_title, selected_creator, selected_assignee, deadline, init_status, action_msg)
                if "Email" in notify_channel:
                    send_email_notification(order_id, task_title, selected_creator, selected_assignee, deadline, init_status, action_msg)
                
                st.success(f"บันทึกคำสั่งงานรหัส {order_id} สำเร็จ พร้อมส่งการแจ้งเตือนเรียบร้อยแล้ว")

# ----------------- เมนู 3: บันทึกความคืบหน้ารายขั้นตอน -----------------
elif menu == "บันทึกความคืบหน้ารายขั้นตอน":
    st.title("บันทึกความคืบหน้าแต่ละขั้นตอน (Step Note)")
    st.caption("เก็บบันทึกประวัติการทำงาน (Audit Trail) รายขั้นตอน ระบุผู้บันทึกและเวลาอัตโนมัติ")

    if orders_df.empty:
        st.info("ยังไม่มีงานในระบบ")
    else:
        active_orders = orders_df[orders_df["status"] != "เสร็จสิ้น"]
        if active_orders.empty:
            st.info("ไม่มีงานที่กำลังดำเนินการอยู่ (ทุกงานปิดเสร็จสิ้นแล้ว)")
        else:
            selected_order_display = st.selectbox(
                "เลือกรายการงานที่ต้องการบันทึกความคืบหน้า",
                options=active_orders["order_id"] + " : " + active_orders["task_title"]
            )
            selected_order_id = selected_order_display.split(" : ")[0]
            
            with st.form("step_log_form"):
                note_text = st.text_area("รายละเอียดความคืบหน้าในขั้นตอนนี้", placeholder="เช่น ดำเนินการตรวจสอบ Policy เสร็จแล้ว อยู่ระหว่างจัดทำสรุปรายงาน")
                notify_teams_on_step = st.checkbox("ส่งสรุปความคืบหน้านี้เข้า Teams Chat Group ด้วย", value=True)
                
                log_submitted = st.form_submit_button("บันทึกขั้นตอน", use_container_width=True)
                if log_submitted:
                    if not note_text:
                        st.error("กรุณาระบุรายละเอียดความคืบหน้า")
                    else:
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                        new_log = pd.DataFrame([{
                            "log_id": f"LOG-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                            "order_id": selected_order_id,
                            "timestamp": now_str,
                            "author": my_display_name,
                            "step_note": note_text
                        }])
                        
                        updated_logs = pd.concat([logs_df, new_log], ignore_index=True)
                        save_logs_data(conn, updated_logs)
                        
                        if notify_teams_on_step:
                            order_row = orders_df[orders_df["order_id"] == selected_order_id].iloc[0]
                            send_teams_notification(
                                selected_order_id, 
                                order_row["task_title"], 
                                order_row["creator"], 
                                order_row["assignee"], 
                                order_row["deadline"], 
                                order_row["status"], 
                                f"อัปเดตความคืบหน้าโดย {my_display_name}: {note_text}"
                            )
                        
                        st.success("บันทึกความคืบหน้าเรียบร้อยแล้ว")
                        st.rerun()

# ----------------- เมนู 4: ทดสอบการแจ้งเตือน (Teams Group Chat) -----------------
elif menu == "ทดสอบการแจ้งเตือน (Teams Group Chat)":
    st.title("ทดสอบส่งการแจ้งเตือนเข้า Microsoft Teams Group Chat")
    st.caption("ตรวจสอบว่า Webhook URL จาก Power Automate รับส่งข้อมูลเข้ากลุ่มแชตถูกต้องหรือไม่")

    webhook_current = st.secrets.get("teams", {}).get("webhook_url", "")
    if webhook_current:
        st.success(f"ตรวจพบการตั้งค่า Teams Webhook URL แล้ว: `{webhook_current[:45]}...`")
    else:
        st.warning("ยังไม่มีการตั้งค่า `webhook_url` ใน secrets.toml (สามารถวาง URL ด้านล่างเพื่อทดสอบชั่วคราวได้)")
        webhook_current = st.text_input("วาง Teams Webhook URL ชั่วคราวเพื่อทดสอบ")

    if st.button("ส่งข้อความทดสอบเข้า Teams Group Chat", use_container_width=True):
        if not webhook_current:
            st.error("กรุณาระบุ Teams Webhook URL ก่อนกดทดสอบ")
        else:
            with st.spinner("กำลังส่งข้อความทดสอบ..."):
                test_payload = {
                    "type": "message",
                    "attachments": [
                        {
                            "contentType": "application/vnd.microsoft.card.adaptive",
                            "content": {
                                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                                "type": "AdaptiveCard",
                                "version": "1.4",
                                "body": [
                                    {
                                        "type": "TextBlock",
                                        "text": "✅ ทดสอบการเชื่อมต่อระบบ Mission Control สำเร็จ!",
                                        "weight": "Bolder",
                                        "size": "Medium",
                                        "color": "Good"
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": f"ส่งโดยผู้ใช้งาน: {my_display_name}\nระบบแจ้งเตือนเข้า Microsoft Teams Chat Group ทำงานสมบูรณ์แบบแล้ว",
                                        "wrap": True
                                    }
                                ]
                            }
                        }
                    ]
                }
                try:
                    res = requests.post(webhook_current, json=test_payload, timeout=10)
                    if res.status_code in [200, 202]:
                        st.success("ส่งข้อความทดสอบเข้า Teams Group Chat เรียบร้อยแล้ว! ตรวจสอบในกลุ่มแชต Teams ได้ทันที")
                    else:
                        st.error(f"Teams ตอบกลับด้วยรหัส {res.status_code}: {res.text}")
                except Exception as e:
                    st.error(f"ไม่สามารถเชื่อมต่อได้: {str(e)}")
