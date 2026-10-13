import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta
import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# กำหนดค่าหน้าจอและซ่อน Sidebar ทางซ้าย
st.set_page_config(
    page_title="Mission Control - ระบบติดตามและยืนยันคำสั่งงาน",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ซ่อนปุ่มเปิดปิด Sidebar ทางซ้ายเพื่อให้เป็น Top Navigation 100%
st.markdown("""
<style>
    [data-testid="collapsedControl"] { display: none; }
    section[data-testid="stSidebar"] { display: none; }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        font-weight: 600;
        border-radius: 6px 6px 0px 0px;
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(255, 75, 75, 0.1);
        border-bottom: 3px solid #ff4b4b !important;
        color: #ff4b4b !important;
    }
    .pin-box {
        font-size: 26px;
        letter-spacing: 12px;
        text-align: center;
        background: #f0f2f6;
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 12px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

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

# ----------------- ฟังก์ชันส่งการแจ้งเตือน Microsoft Teams และ Email -----------------
def send_teams_notification(order_id, title, creator, assignee, deadline, status, action_text):
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

# ----------------- ระบบจัดการฐานข้อมูล (Data Layer) -----------------
EMPTY_USERS_COLS = ["username", "display_name", "pin", "must_change_pin", "updated_at"]
EMPTY_ORDERS_COLS = [
    "created_at", "task_title", "description", "deadline", 
    "status", "assignee", "assignee_confirmed", "creator", 
    "creator_confirmed", "recorded_by", "order_id"
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

conn, users_df, orders_df, logs_df, db_status = load_data()
ALL_DISPLAY_NAMES = list(users_df["display_name"].unique())

# ----------------- จัดการ Session State -----------------
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

if "keypad_pin" not in st.session_state:
    st.session_state.keypad_pin = ""

if "pending_change_pin_user" not in st.session_state:
    st.session_state.pending_change_pin_user = None

if "show_forgot_password" not in st.session_state:
    st.session_state.show_forgot_password = False

# ----------------- หน้าจอบังคับเปลี่ยนรหัสผ่านครั้งแรก -----------------
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
                st.session_state.keypad_pin = ""
                st.success("ตั้งรหัส PIN สำเร็จ เข้าสู่ระบบเรียบร้อย")
                st.rerun()

    if st.button("ยกเลิกและกลับหน้าเข้าสู่ระบบ"):
        st.session_state.pending_change_pin_user = None
        st.session_state.keypad_pin = ""
        st.rerun()
    st.stop()

# ----------------- หน้าจอเข้าสู่ระบบ: แป้นตัวเลขมือถือ (On-screen 10-Key Keypad 0-9) -----------------
if not st.session_state.auth_user:
    st.title("Mission Control : ระบบติดตามและยืนยันคำสั่งงาน")
    st.caption("ระบบเก็บประวัติการทำงานแบบรายบุคคล กรุณาเข้าสู่ระบบด้วย Username และกดรหัส PIN 6 หลักผ่านแป้นบนหน้าจอ")

    col_login, col_help = st.columns([1, 1])

    with col_login:
        entered_username = st.text_input("ชื่อผู้ใช้งาน (Username)", placeholder="herren.k", key="login_user_input")
        
        # จุดแสดงสถานะรหัสผ่านสไตล์มือถือ
        cur_pin = st.session_state.keypad_pin
        pin_dots = " ".join(["●" if i < len(cur_pin) else "○" for i in range(6)])
        st.markdown(f"<div class='pin-box'>{pin_dots}</div>", unsafe_allow_html=True)
        st.caption("กดปุ่มตัวเลข 0-9 บนหน้าจอด้านล่าง (ไม่อนุญาตให้พิมพ์ผ่านคีย์บอร์ด):")

        # แป้นตัวเลข 10 ปุ่มสไตล์มือถือ (0-9)
        k_row1 = st.columns(3)
        for i, val in enumerate(["1", "2", "3"]):
            if k_row1[i].button(val, key=f"pad_{val}", use_container_width=True):
                if len(st.session_state.keypad_pin) < 6:
                    st.session_state.keypad_pin += val
                    st.rerun()

        k_row2 = st.columns(3)
        for i, val in enumerate(["4", "5", "6"]):
            if k_row2[i].button(val, key=f"pad_{val}", use_container_width=True):
                if len(st.session_state.keypad_pin) < 6:
                    st.session_state.keypad_pin += val
                    st.rerun()

        k_row3 = st.columns(3)
        for i, val in enumerate(["7", "8", "9"]):
            if k_row3[i].button(val, key=f"pad_{val}", use_container_width=True):
                if len(st.session_state.keypad_pin) < 6:
                    st.session_state.keypad_pin += val
                    st.rerun()

        k_row4 = st.columns(3)
        if k_row4[0].button("ล้างค่า", key="pad_clear", use_container_width=True):
            st.session_state.keypad_pin = ""
            st.rerun()

        if k_row4[1].button("0", key="pad_0", use_container_width=True):
            if len(st.session_state.keypad_pin) < 6:
                st.session_state.keypad_pin += "0"
                st.rerun()

        if k_row4[2].button("⌫ ลบ", key="pad_backspace", use_container_width=True):
            if len(st.session_state.keypad_pin) > 0:
                st.session_state.keypad_pin = st.session_state.keypad_pin[:-1]
                st.rerun()

        st.write("")
        login_btn = st.button("เข้าสู่ระบบ (Login)", type="primary", use_container_width=True)
        if login_btn:
            u_clean = entered_username.strip().lower()
            matching_user = users_df[users_df["username"] == u_clean]
            
            if matching_user.empty:
                st.error("ไม่พบชื่อผู้ใช้งานนี้ในระบบ โปรดตรวจสอบตัวสะกด (เช่น herren.k, nataphon.p)")
            elif len(st.session_state.keypad_pin) != 6:
                st.error("กรุณากดรหัส PIN ให้ครบ 6 หลัก")
            else:
                user_row = matching_user.iloc[0]
                stored_pin = str(user_row["pin"])
                must_change = str(user_row["must_change_pin"]).lower() == "true"
                
                if st.session_state.keypad_pin == stored_pin:
                    if st.session_state.keypad_pin == "111111" or must_change:
                        st.session_state.pending_change_pin_user = user_row.to_dict()
                        st.rerun()
                    else:
                        st.session_state.auth_user = user_row.to_dict()
                        st.session_state.keypad_pin = ""
                        st.success(f"เข้าสู่ระบบสำเร็จ: ยินดีต้อนรับคุณ {user_row['display_name']}")
                        st.rerun()
                else:
                    st.error("รหัส PIN 6 หลักไม่ถูกต้อง")
                    st.session_state.keypad_pin = ""

        st.divider()
        if st.button("ลืมรหัสผ่าน (Forgot Password)", use_container_width=True):
            st.session_state.show_forgot_password = not st.session_state.show_forgot_password

    # หน้าต่างรีเซ็ตรหัสผ่าน KuromiBlackCat
    if st.session_state.show_forgot_password:
        with col_help:
            st.warning("ขั้นตอนขอรีเซ็ตรหัสผ่าน")
            admin_contact = st.secrets.get("security", {}).get("admin_contact", "Herren@Onelink.co.th")
            st.markdown(f"1. โปรดติดต่อ Teams: **`{admin_contact}`** เพื่อยืนยันตัวตนจริง<br>2. คุณจะได้รับรหัสยืนยันพิเศษเพื่อนำมากรอกด้านล่าง", unsafe_allow_html=True)
            
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

# ----------------- ส่วนหัวหน้าเว็บแบบ Top Navigation (ไม่มี Sidebar) -----------------
current_user = st.session_state.auth_user
my_display_name = current_user["display_name"]

# แถบ Header แสดงข้อมูลผู้ใช้และปุ่ม Logout
top_col1, top_col2, top_col3 = st.columns([3, 2, 1])
with top_col1:
    st.markdown(f"### 📋 Mission Control")
with top_col2:
    st.markdown(f"👤 ผู้ใช้งาน: **{my_display_name}** | 🟢 `{db_status}`")
with top_col3:
    if st.button("ออกจากระบบ (Logout)", use_container_width=True):
        st.session_state.auth_user = None
        st.session_state.pending_change_pin_user = None
        st.session_state.keypad_pin = ""
        st.session_state.show_forgot_password = False
        st.rerun()

st.divider()

# แถบเมนูด้านบนแบบ Tabs (Active tab จะมีเส้นใต้ไฮไลต์เข้มเด่นชัด)
tab_excel, tab_new_order, tab_step_log, tab_teams_test = st.tabs([
    "📊 ตารางคำสั่งงาน (Excel View)", 
    "➕ สร้างคำสั่งงานใหม่", 
    "📝 บันทึกความคืบหน้ารายขั้นตอน", 
    "🔔 ทดสอบการแจ้งเตือน Teams Group Chat"
])

# ----------------- TAB 1: ตารางคำสั่งงานสไตล์ Excel (ตามภาพ 1) -----------------
with tab_excel:
    st.subheader("กระดานติดตามงาน (Excel View)")
    
    # ตัวควบคุมมุมมอง: สลับ "แบบย่อ" กับ "แบบเต็ม"
    v_col1, v_col2, v_col3, v_col4 = st.columns([2, 2, 2, 2])
    with v_col1:
        view_mode = st.radio("โหมดการแสดงผล:", ["แบบย่อ", "แบบเต็ม"], horizontal=True)
    with v_col2:
        sort_order = st.selectbox("เรียงตามวันที่สร้าง:", ["ล่าสุดก่อน (ใหม่ -> เก่า)", "เก่าสุดก่อน (เก่า -> ใหม่)"])
    with v_col3:
        filter_assignee = st.selectbox("กรองตามคนรับผิดชอบ:", ["ทั้งหมด"] + ALL_DISPLAY_NAMES)
    with v_col4:
        filter_status = st.selectbox("กรองตามสถานะ:", ["ทั้งหมด (ยกเว้นที่ยกเลิก)", "งานที่ยังไม่เสร็จสิ้น", "เสร็จสิ้น", "ทั้งหมดรวมยกเลิก"])

    # กรองข้อมูล
    active_df = orders_df.copy()
    if active_df.empty:
        st.info("ยังไม่มีรายการคำสั่งงานในระบบ กดที่แท็บ 'สร้างคำสั่งงานใหม่' เพื่อเริ่มบันทึก")
    else:
        # กรองสถานะ
        if filter_status == "ทั้งหมด (ยกเว้นที่ยกเลิก)":
            active_df = active_df[active_df["status"] != "ยกเลิก"]
        elif filter_status == "งานที่ยังไม่เสร็จสิ้น":
            active_df = active_df[~active_df["status"].isin(["เสร็จสิ้น", "ยกเลิก"])]
        elif filter_status == "เสร็จสิ้น":
            active_df = active_df[active_df["status"] == "เสร็จสิ้น"]

        # กรองคนรับผิดชอบ
        if filter_assignee != "ทั้งหมด":
            active_df = active_df[active_df["assignee"] == filter_assignee]

        # จัดเรียงตามวันที่
        ascending = (sort_order == "เก่าสุดก่อน (เก่า -> ใหม่)")
        active_df = active_df.sort_values(by="created_at", ascending=ascending)

        # จัดรูปแบบคอลัมน์ตามภาพ 1
        if view_mode == "แบบย่อ":
            display_cols = ["created_at", "task_title", "description", "deadline", "assignee", "status"]
            rename_map = {
                "created_at": "สร้างเมื่อ",
                "task_title": "ชื่องาน",
                "description": "รายละเอียด",
                "deadline": "กำหนดส่ง",
                "assignee": "คนรับผิดชอบ",
                "status": "สถานะปัจจุบัน"
            }
        else:
            # แบบเต็ม ตามภาพ 1 เป๊ะ
            display_cols = [
                "created_at", "task_title", "description", "deadline", 
                "status", "assignee", "assignee_confirmed", "creator", 
                "creator_confirmed", "recorded_by"
            ]
            rename_map = {
                "created_at": "สร้างเมื่อ",
                "task_title": "ชื่องาน",
                "description": "รายละเอียด",
                "deadline": "กำหนดส่ง",
                "status": "สถานะปัจจุบัน",
                "assignee": "คนรับผิดชอบ",
                "assignee_confirmed": "คนรับผิดชอบยืนยัน",
                "creator": "คนสั่ง",
                "creator_confirmed": "คนสั่งยืนยัน",
                "recorded_by": "ผู้ลงบันทึก"
            }

        # แสดงตารางสไตล์ Excel
        render_df = active_df[display_cols].rename(columns=rename_map)
        st.dataframe(render_df, use_container_width=True, hide_index=True)

        st.divider()

        # แผงดำเนินการคำสั่งงาน (Action & Audit Panel ด้านล่างตาราง)
        st.subheader("แผงดำเนินการคำสั่งงาน (Action Panel)")
        if not active_df.empty:
            order_choices = [f"{r['order_id']} | {r['task_title']} ({r['status']})" for _, r in active_df.iterrows()]
            selected_choice = st.selectbox("เลือกคำสั่งงานเพื่อดำเนินการ / ดูประวัติขั้นตอน:", order_choices)
            selected_order_id = selected_choice.split(" | ")[0]
            selected_row = orders_df[orders_df["order_id"] == selected_order_id].iloc[0]
            row_idx = orders_df[orders_df["order_id"] == selected_order_id].index[0]

            det_col1, det_col2, det_col3 = st.columns(3)
            with det_col1:
                st.write(f"**ชื่องาน:** {selected_row['task_title']}")
                st.write(f"**คนสั่ง:** {selected_row['creator']} ({selected_row['creator_confirmed']})")
            with det_col2:
                st.write(f"**กำหนดส่ง:** {selected_row['deadline']}")
                st.write(f"**คนรับผิดชอบ:** {selected_row['assignee']} ({selected_row['assignee_confirmed']})")
            with det_col3:
                st.write(f"**สถานะ:** `{selected_row['status']}`")
                st.write(f"**ผู้ลงบันทึก:** {selected_row['recorded_by']}")

            st.info(f"**รายละเอียดงาน:** {selected_row['description']}")

            # ประวัติความคืบหน้ารายขั้นตอน
            item_logs = logs_df[logs_df["order_id"] == selected_order_id]
            if not item_logs.empty:
                st.write("**ประวัติความคืบหน้ารายขั้นตอน (Step Logs):**")
                for _, lrow in item_logs.iterrows():
                    st.caption(f"• `[{lrow['timestamp']}]` โดย **{lrow['author']}**: {lrow['step_note']}")

            # โซนปุ่มดำเนินการ
            act_col1, act_col2, act_col3, act_col4 = st.columns(4)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

            # 1. คนสั่งกดยืนยันคำสั่งงาน
            if my_display_name == selected_row['creator'] and "รอยืนยัน" in str(selected_row['creator_confirmed']):
                with act_col1:
                    if st.button("คนสั่งยืนยันความถูกต้อง", key=f"btn_cconf_{selected_order_id}", type="primary", use_container_width=True):
                        orders_df.loc[row_idx, "creator_confirmed"] = f"ยืนยันแล้ว ({now_str})"
                        if "ยืนยันแล้ว" in str(orders_df.loc[row_idx, "assignee_confirmed"]):
                            orders_df.loc[row_idx, "status"] = "กำลังดำเนินการ"
                        save_orders_data(conn, orders_df)
                        send_teams_notification(selected_order_id, selected_row['task_title'], selected_row['creator'], selected_row['assignee'], selected_row['deadline'], orders_df.loc[row_idx, "status"], f"{my_display_name} ยืนยันคำสั่งงานแล้ว")
                        st.success("ยืนยันคำสั่งงานเรียบร้อย")
                        st.rerun()

            # 2. คนรับผิดชอบตอบรับคำสั่งงาน
            if my_display_name == selected_row['assignee'] and "รอยืนยัน" in str(selected_row['assignee_confirmed']):
                with act_col2:
                    if st.button("คนรับผิดชอบตอบรับงาน", key=f"btn_aconf_{selected_order_id}", type="primary", use_container_width=True):
                        orders_df.loc[row_idx, "assignee_confirmed"] = f"ยืนยันแล้ว ({now_str})"
                        if "ยืนยันแล้ว" in str(orders_df.loc[row_idx, "creator_confirmed"]):
                            orders_df.loc[row_idx, "status"] = "กำลังดำเนินการ"
                        save_orders_data(conn, orders_df)
                        send_teams_notification(selected_order_id, selected_row['task_title'], selected_row['creator'], selected_row['assignee'], selected_row['deadline'], orders_df.loc[row_idx, "status"], f"{my_display_name} ตอบรับคำสั่งงานแล้ว")
                        st.success("ตอบรับงานเรียบร้อย")
                        st.rerun()

            # 3. คนรับผิดชอบส่งงานเพื่อขอตรวจสอบ
            if my_display_name == selected_row['assignee'] and selected_row['status'] == "กำลังดำเนินการ":
                with act_col2:
                    if st.button("ส่งงาน (ขอตรวจสอบ)", key=f"btn_sub_{selected_order_id}", use_container_width=True):
                        orders_df.loc[row_idx, "status"] = "รอตรวจสอบ"
                        save_orders_data(conn, orders_df)
                        send_teams_notification(selected_order_id, selected_row['task_title'], selected_row['creator'], selected_row['assignee'], selected_row['deadline'], "รอตรวจสอบ", f"{my_display_name} ส่งมอบงานแล้ว กรุณาตรวจสอบ")
                        st.success("ส่งมอบงานเรียบร้อย รอคนสั่งตรวจสอบ")
                        st.rerun()

            # 4. เฉพาะคนสั่งตรวจรับและปิดงาน
            if my_display_name == selected_row['creator'] and selected_row['status'] in ["รอตรวจสอบ", "กำลังดำเนินการ"]:
                with act_col3:
                    if st.button("ตรวจรับและปิดงาน (เสร็จสิ้น)", key=f"btn_close_{selected_order_id}", use_container_width=True):
                        orders_df.loc[row_idx, "status"] = "เสร็จสิ้น"
                        save_orders_data(conn, orders_df)
                        send_teams_notification(selected_order_id, selected_row['task_title'], selected_row['creator'], selected_row['assignee'], selected_row['deadline'], "เสร็จสิ้น", f"{my_display_name} ตรวจรับและปิดงานเรียบร้อยแล้ว")
                        st.success("ปิดงานเรียบร้อย")
                        st.rerun()

            # 5. เฉพาะคนสั่งมีสิทธิ์ลบ/ยกเลิกงาน (Soft Delete)
            if my_display_name == selected_row['creator'] and selected_row['status'] != "ยกเลิก":
                with act_col4:
                    if st.button("ยกเลิกคำสั่งงาน (ลบงาน)", key=f"btn_del_{selected_order_id}", use_container_width=True):
                        orders_df.loc[row_idx, "status"] = "ยกเลิก"
                        save_orders_data(conn, orders_df)
                        send_teams_notification(selected_order_id, selected_row['task_title'], selected_row['creator'], selected_row['assignee'], selected_row['deadline'], "ยกเลิก", f"{my_display_name} ได้ยกเลิกคำสั่งงานนี้แล้ว")
                        st.warning("ยกเลิกคำสั่งงานเรียบร้อยแล้ว (สถานะเปลี่ยนเป็น 'ยกเลิก' และซ่อนออกจากมุมมองปกติ)")
                        st.rerun()

# ----------------- TAB 2: สร้างคำสั่งงานใหม่ (Date Picker + Time Default 10:00) -----------------
with tab_new_order:
    st.subheader("บันทึกคำสั่งงานใหม่")
    st.caption("สามารถสร้างงานโดยตนเอง หรือจดบันทึกจากคำสั่งปากเปล่าแทนเพื่อนร่วมทีมได้ ระบบจะระบุชื่อผู้ลงบันทึกจริงเพื่อความโปร่งใส")

    with st.form("new_order_form"):
        task_title = st.text_input("ชื่องาน / สรุปประเด็นคำสั่ง", placeholder="เช่น ขอรายละเอียด server ที่ดูแลทั้งหมด, ปรับปรุง Cloud Security")
        description = st.text_area("รายละเอียดงานทั้งหมด", placeholder="เช่น ขอสิทธิ์ read only access เพื่อ maintain ระบบ")

        c1, c2 = st.columns(2)
        with c1:
            creator_default_idx = ALL_DISPLAY_NAMES.index(my_display_name) if my_display_name in ALL_DISPLAY_NAMES else 0
            selected_creator = st.selectbox("คนสั่ง (Creator)", options=ALL_DISPLAY_NAMES, index=creator_default_idx)
        with c2:
            selected_assignee = st.selectbox("คนรับผิดชอบ (Assignee)", options=ALL_DISPLAY_NAMES, index=0)

        # Date Picker + Time Default 10:00 ตามข้อกำหนด
        cd_col1, cd_col2 = st.columns(2)
        with cd_col1:
            due_date = st.date_input("กำหนดส่ง (วันที่)", value=date.today() + timedelta(days=2))
        with cd_col2:
            due_time = st.time_input("กำหนดส่ง (เวลา)", value=time(10, 0))

        formatted_deadline = f"{due_date.strftime('%Y%m%d')} {due_time.strftime('%H:%M')}"
        st.caption(f"กำหนดส่งที่จะถูกบันทึก: `{formatted_deadline}`")

        notify_channel = st.multiselect("ส่งการแจ้งเตือนทันทีไปยัง", ["Microsoft Teams (Chat Group)", "Email"], default=["Microsoft Teams (Chat Group)"])

        submitted = st.form_submit_button("บันทึกคำสั่งงาน", type="primary", use_container_width=True)
        if submitted:
            if not task_title or not description:
                st.error("กรุณาระบุชื่องานและรายละเอียดงานให้ครบถ้วน")
            else:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                # กำหนดสถานะยืนยันตามตัวตนของผู้บันทึก
                if my_display_name == selected_creator:
                    creator_conf = f"ยืนยันแล้ว ({now_str})"
                    assignee_conf = f"รอยืนยัน (รอ {selected_assignee} ตอบรับ)"
                    init_status = "รอคนรับผิดชอบตอบรับ"
                else:
                    # ผู้บันทึกพิมพ์แทนคนสั่ง (จดจากคำสั่งปากเปล่า)
                    creator_conf = f"รอยืนยัน (รอ {selected_creator} ยืนยัน)"
                    assignee_conf = f"ยืนยันแล้ว ({now_str})" if my_display_name == selected_assignee else "รอยืนยัน"
                    init_status = "รอคนสั่งยืนยัน"

                new_row = pd.DataFrame([{
                    "created_at": now_str,
                    "task_title": task_title,
                    "description": description,
                    "deadline": formatted_deadline,
                    "status": init_status,
                    "assignee": selected_assignee,
                    "assignee_confirmed": assignee_conf,
                    "creator": selected_creator,
                    "creator_confirmed": creator_conf,
                    "recorded_by": my_display_name,
                    "order_id": order_id
                }])

                updated_orders = pd.concat([orders_df, new_row], ignore_index=True)
                save_orders_data(conn, updated_orders)

                # ส่งแจ้งเตือน
                action_msg = f"มีคำสั่งงานใหม่: {selected_creator} สั่งให้ {selected_assignee} รับผิดชอบ"
                if "Microsoft Teams (Chat Group)" in notify_channel:
                    send_teams_notification(order_id, task_title, selected_creator, selected_assignee, formatted_deadline, init_status, action_msg)
                if "Email" in notify_channel:
                    send_email_notification(order_id, task_title, selected_creator, selected_assignee, formatted_deadline, init_status, action_msg)

                st.success(f"บันทึกคำสั่งงานรหัส {order_id} สำเร็จ พร้อมส่งการแจ้งเตือนเรียบร้อยแล้ว")
                st.rerun()

# ----------------- TAB 3: บันทึกความคืบหน้ารายขั้นตอน -----------------
with tab_step_log:
    st.subheader("บันทึกความคืบหน้าแต่ละขั้นตอน (Step Note)")
    st.caption("เก็บบันทึกประวัติการทำงาน (Audit Trail) รายขั้นตอน ระบุผู้บันทึกและเวลาอัตโนมัติ")

    if orders_df.empty:
        st.info("ยังไม่มีงานในระบบ")
    else:
        active_orders = orders_df[~orders_df["status"].isin(["เสร็จสิ้น", "ยกเลิก"])]
        if active_orders.empty:
            st.info("ไม่มีงานที่กำลังดำเนินการอยู่ (ทุกงานเสร็จสิ้นหรือยกเลิกแล้ว)")
        else:
            selected_order_display = st.selectbox(
                "เลือกรายการงานที่ต้องการบันทึกความคืบหน้า",
                options=active_orders["order_id"] + " : " + active_orders["task_title"]
            )
            selected_order_id = selected_order_display.split(" : ")[0]

            with st.form("step_log_form"):
                note_text = st.text_area("รายละเอียดความคืบหน้าในขั้นตอนนี้", placeholder="เช่น ดำเนินการตรวจสอบ Policy เสร็จแล้ว อยู่ระหว่างจัดทำสรุปรายงาน")
                notify_teams_on_step = st.checkbox("ส่งสรุปความคืบหน้านี้เข้า Teams Chat Group ด้วย", value=True)

                log_submitted = st.form_submit_button("บันทึกขั้นตอน", type="primary", use_container_width=True)
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

# ----------------- TAB 4: ทดสอบการแจ้งเตือน & คู่มือการขอ Webhook -----------------
with tab_teams_test:
    st.subheader("ทดสอบส่งการแจ้งเตือนเข้า Microsoft Teams Group Chat")
    
    # คำแนะนำและขั้นตอนการขอ Webhook ละเอียด
    with st.expander("📖 วิธีการสร้าง Webhook URL จาก Microsoft Teams Group Chat และนำมาใส่ใน Secrets", expanded=True):
        st.markdown("""
        ### ขั้นตอนการขอ Webhook URL ใน Microsoft Teams
        1. เปิดโปรแกรม **Microsoft Teams** บนคอมพิวเตอร์ของคุณ
        2. ไปที่กลุ่มแชต (**Group Chat**) ที่ต้องการให้แจ้งเตือนเด้งเข้า
        3. มองไปที่มุมบนขวาของหน้าต่างแชต คลิกที่ไอคอน **Workflows** (หรือคลิกจุดสามจุด `...` แล้วเลือก Workflows)
        4. เลือกแท็บ **Create** แล้วค้นหาคำว่า:
           `Post message in a chat when a webhook request is received`
        5. คลิกที่การ์ดเทมเพลต ตั้งชื่อ Flow เช่น `Mission Control Bot` แล้วกด **Next**
        6. ในช่อง **Chat** ให้เลือกเป็นกลุ่มแชตปัจจุบันของคุณ จากนั้นกด **Create Flow**
        7. ระบบจะประมวลผลและสร้างลิงก์ **HTTP POST URL** ให้ทันที ให้คลิกปุ่ม **Copy**
        
        ---
        
        ### นำลิงก์ที่ได้ไปใส่ใน Streamlit App Secrets
        - **เมื่อรันบนเครื่องคอมพิวเตอร์ (Local)**:
          เปิดไฟล์ `.streamlit/secrets.toml` ในโฟลเดอร์โปรเจกต์ แล้ววาง URL ในบรรทัด:
          ```toml
          [teams]
          webhook_url = "https://prod-xx.southeastasia.logic.azure.com:443/workflows/xxxx/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=xxxx"
          ```
        - **เมื่อ Deploy บน Streamlit Community Cloud**:
          1. ไปที่หน้าแดชบอร์ด [share.streamlit.io](https://share.streamlit.io)
          2. กดจุด 3 จุด `...` ข้างชื่อแอปของคุณ -> เลือก **Settings**
          3. เลือกแท็บ **Secrets** ทางด้านซ้าย
          4. วางบรรทัด `[teams]` และ `webhook_url = "..."` แล้วกด **Save**
        """)

    st.divider()

    webhook_current = st.secrets.get("teams", {}).get("webhook_url", "")
    if webhook_current:
        st.success(f"ตรวจพบการตั้งค่า Teams Webhook URL แล้ว: `{webhook_current[:45]}...`")
    else:
        st.warning("ยังไม่มีการตั้งค่า `webhook_url` ใน secrets.toml (สามารถวาง URL ด้านล่างเพื่อทดสอบชั่วคราวได้)")
        webhook_current = st.text_input("วาง Teams Webhook URL ชั่วคราวเพื่อทดสอบ")

    if st.button("ส่งข้อความทดสอบเข้า Teams Group Chat ตอนนี้", type="primary", use_container_width=True):
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
                                        "text": f"ส่งโดย: {my_display_name}\nระบบแจ้งเตือนเข้า Microsoft Teams Group Chat พร้อมใช้งานสำหรับคำสั่งงานจริงแล้ว",
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
