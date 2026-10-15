import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta
import os
import requests
import smtplib
import urllib.parse
import re
import hmac
import hashlib
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
    iframe[height="0"] { display: none !important; }
    iframe[width="0"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# โฟลเดอร์สำหรับเก็บข้อมูลกรณีทำงานในโหมด Offline / Local
LOCAL_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(LOCAL_DATA_DIR, exist_ok=True)
USERS_CSV = os.path.join(LOCAL_DATA_DIR, "users.csv")
ORDERS_CSV = os.path.join(LOCAL_DATA_DIR, "orders.csv")
LOGS_CSV = os.path.join(LOCAL_DATA_DIR, "order_logs.csv")

# รายชื่อผู้ใช้งานระบบ (สงวนเฉพาะ Herren และ CTO สำหรับการบริหารจัดการและพรีเซนต์)
# รายชื่อเดิม 11 คนได้รับการสำรองไว้อย่างปลอดภัยใน TEAM_ROSTER_ARCHIVE.md เรียบร้อยแล้ว
DEFAULT_USERS_ROSTER = [
    {"username": "herren.k", "title": "Cloud En"},
    {"username": "nataphon.p", "title": "CTO"},
]

# ----------------- ฟังก์ชันส่งการแจ้งเตือน Microsoft Teams และ Email -----------------
def get_user_email(user_display_name):
    if not user_display_name:
        return ""
    if "Guest:" in str(user_display_name):
        m = re.search(r"Guest:\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", str(user_display_name))
        if m:
            return m.group(1)
    uname = str(user_display_name).split()[0]
    domain = st.secrets.get("security", {}).get("company_domain", "onelink.co.th")
    return f"{uname}@{domain}"

def generate_teams_chat_url(recipient_display_name, message_text):
    email = get_user_email(recipient_display_name)
    encoded_msg = urllib.parse.quote(message_text)
    return f"https://teams.microsoft.com/l/chat/0/0?users={email}&message={encoded_msg}"

def send_teams_notification(order_id, title, creator, assignee, deadline, status, action_text):
    webhook_url = st.secrets.get("teams", {}).get("webhook_url", "")
    if not webhook_url:
        return False, "ยังไม่ได้ตั้งค่า Teams Webhook URL ใน secrets.toml"

    app_url = st.secrets.get("app_url", "")
    creator_email = get_user_email(creator)
    teams_direct_chat = generate_teams_chat_url(creator, f"[Mission Control] แจ้งอัปเดตงาน {order_id}: {title} (สถานะ: {status})")

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
                            "text": f"📢 แจ้งเตือนคนสั่งงาน (<at>{creator}</at>): {action_text}",
                            "weight": "Bolder",
                            "size": "Medium",
                            "color": "Accent"
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "รหัสงาน:", "value": str(order_id)},
                                {"title": "ชื่องาน:", "value": str(title)},
                                {"title": "คนสั่งงาน:", "value": f"{creator} ({creator_email})"},
                                {"title": "ผู้ปฏิบัติงาน:", "value": str(assignee)},
                                {"title": "กำหนดส่ง:", "value": str(deadline)},
                                {"title": "สถานะล่าสุด:", "value": str(status)}
                            ]
                        }
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "📋 เปิดเข้าระบบ Mission Control",
                            "url": app_url if app_url else "https://streamlit.io"
                        },
                        {
                            "type": "Action.OpenUrl",
                            "title": "💬 เปิดแชท Teams ทักคนสั่งงาน",
                            "url": teams_direct_chat
                        }
                    ],
                    "msteams": {
                        "entities": [
                            {
                                "type": "mention",
                                "text": f"<at>{creator}</at>",
                                "mentioned": {
                                    "id": creator_email,
                                    "name": creator
                                }
                            }
                        ]
                    }
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

# ----------------- จัดการ Session State & Token-Based Persistence -----------------
AUTH_SECRET = st.secrets.get("security", {}).get("session_secret", "MISSION_CONTROL_HMAC_SALT_2026")

def create_auth_token(username, role="staff"):
    raw = f"{str(username).lower()}:{role}"
    sig = hmac.new(AUTH_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{raw}:{sig}"

def verify_auth_token(token_str):
    if not token_str or ":" not in str(token_str):
        return None, None
    parts = str(token_str).split(":")
    if len(parts) != 3:
        return None, None
    username, role, sig = parts[0], parts[1], parts[2]
    raw = f"{username}:{role}"
    expected_sig = hmac.new(AUTH_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()[:16]
    if hmac.compare_digest(sig, expected_sig):
        return username, role
    return None, None

def set_persistent_cookie(token_str):
    """บันทึก Secure Session Token ลงใน Browser Cookies (อายุ 30 วัน) เพื่อให้เปิดแท็บใหม่ หรือปิดเปิดเบราว์เซอร์ใหม่ก็ยังจำสถานะผู้ใช้ไว้แบบ Google & Facebook"""
    import streamlit.components.v1 as components
    js_code = f"""
    <script>
    try {{
        var cookieVal = encodeURIComponent("{token_str}");
        var expireDays = 30;
        var d = new Date();
        d.setTime(d.getTime() + (expireDays * 24 * 60 * 60 * 1000));
        var cookieStr = "mc_auth=" + cookieVal + "; expires=" + d.toUTCString() + "; path=/; SameSite=Lax";
        window.parent.document.cookie = cookieStr;
        document.cookie = cookieStr;
    }} catch(e) {{
        console.warn("Could not set persistent cookie:", e);
    }}
    </script>
    """
    components.html(js_code, height=0, width=0)

def clear_persistent_cookie():
    """ลบ Secure Session Cookie และล้าง URL Address Bar เมื่อผู้ใช้กดออกจากระบบ (Logout)"""
    import streamlit.components.v1 as components
    js_code = """
    <script>
    try {
        var clearStr = "mc_auth=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; SameSite=Lax";
        window.parent.document.cookie = clearStr;
        document.cookie = clearStr;
        if (window.parent.history && window.parent.history.replaceState) {
            window.parent.history.replaceState({}, document.title, window.parent.location.pathname);
        }
    } catch(e) {
        console.warn("Could not clear persistent cookie:", e);
    }
    </script>
    """
    components.html(js_code, height=0, width=0)

def clear_subpage_params():
    if "view" in st.query_params:
        del st.query_params["view"]
    if "order_id" in st.query_params:
        del st.query_params["order_id"]

if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

if "is_logged_out" not in st.session_state:
    st.session_state.is_logged_out = False

# กู้คืนเซสชันอัตโนมัติ (Session Persistence แบบ Google & Facebook)
# ลำดับที่ 1: ตรวจสอบจาก URL Query Param ก่อน (รองรับการเปิด 2 แท็บทดสอบคนละ User เช่น herren.k กับ nataphon.p)
# ลำดับที่ 2: หากเปิดแท็บใหม่ว่างๆ (ไม่มี ?auth=...) ให้ดึงจาก Browser Cookie อัตโนมัติ (ล็อกอินค้างไว้แบบ Google/Facebook)
# ป้องกันการเด้งล็อกอินกลับ: หากผู้ใช้เพิ่งกดออกจากระบบ (is_logged_out == True) จะไม่กู้คืนเซสชันจนกว่าจะล็อกอินใหม่
if not st.session_state.auth_user and not st.session_state.is_logged_out:
    saved_token = st.query_params.get("auth", None)
    if not saved_token:
        try:
            raw_cookie = st.context.cookies.get("mc_auth", None)
            if raw_cookie:
                saved_token = urllib.parse.unquote(str(raw_cookie))
        except Exception:
            saved_token = None

    if saved_token:
        v_user, v_role = verify_auth_token(saved_token)
        if v_user:
            if v_role == "staff":
                matching = users_df[users_df["username"] == v_user]
                if not matching.empty:
                    u_dict = matching.iloc[0].to_dict()
                    u_dict["role"] = "staff"
                    st.session_state.auth_user = u_dict
                    st.query_params["auth"] = saved_token
            elif v_role == "guest":
                guest_disp = st.query_params.get("guest_name", f"Guest ({v_user})")
                st.session_state.auth_user = {
                    "username": f"guest_{v_user.split('@')[0]}",
                    "display_name": guest_disp,
                    "role": "guest",
                    "email": v_user
                }
                st.query_params["auth"] = saved_token

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
                st.query_params["auth"] = create_auth_token(p_user["username"], role="staff")
                st.session_state.pending_change_pin_user = None
                st.session_state.keypad_pin = ""
                st.success("ตั้งรหัส PIN สำเร็จ เข้าสู่ระบบเรียบร้อย")
                st.rerun()

    if st.button("ยกเลิกและกลับหน้าเข้าสู่ระบบ"):
        st.session_state.pending_change_pin_user = None
        st.session_state.keypad_pin = ""
        st.rerun()
    st.stop()

# ----------------- หน้าจอเข้าสู่ระบบ: Dual-Tab Gateway (เจ้าหน้าที่ / ผู้ประสานงาน) -----------------
if not st.session_state.auth_user:
    clear_persistent_cookie()
    st.session_state.should_clear_cookie = False

    st.title("Mission Control : ระบบติดตามและยืนยันคำสั่งงาน")
    st.caption("ระบบเก็บประวัติการทำงานแบบรายบุคคล กรุณาเข้าสู่ระบบเพื่อดำเนินการ")

    tab_staff, tab_guest = st.tabs(["🔑 เข้าสู่ระบบ (เจ้าหน้าที่ / ทีมงาน)", "✉️ ผู้ประสานงานชั่วคราว (Guest)"])

    with tab_staff:
        col_login, col_help = st.columns([1, 1])

        with col_login:
            with st.form("staff_login_form"):
                entered_username = st.text_input("ชื่อผู้ใช้งาน (Username)", placeholder="name.s", key="login_user_input")
                entered_pin = st.text_input("รหัส PIN 6 หลัก", type="password", max_chars=6, placeholder="••••••", key="login_pin_input")
                login_btn = st.form_submit_button("เข้าสู่ระบบ (Login)", type="primary", use_container_width=True)

                if login_btn:
                    u_clean = entered_username.strip().lower()
                    if not u_clean:
                        st.error("กรุณาระบุชื่อผู้ใช้งาน")
                    elif not entered_pin:
                        st.error("กรุณาระบุรหัส PIN 6 หลัก")
                    else:
                        matching_user = users_df[users_df["username"] == u_clean]
                        if matching_user.empty:
                            st.error("ไม่พบชื่อผู้ใช้งานนี้ในระบบ โปรดตรวจสอบตัวสะกด (เช่น name.s)")
                        elif len(entered_pin) != 6 or not entered_pin.isdigit():
                            st.error("รหัส PIN ต้องเป็นตัวเลข 6 หลักเท่านั้น")
                        else:
                            user_row = matching_user.iloc[0]
                            stored_pin = str(user_row["pin"])
                            must_change = str(user_row["must_change_pin"]).lower() == "true"

                            if entered_pin == stored_pin:
                                if entered_pin == "111111" or must_change:
                                    st.session_state.pending_change_pin_user = user_row.to_dict()
                                    st.rerun()
                                else:
                                    user_dict = user_row.to_dict()
                                    user_dict["role"] = "staff"
                                    st.session_state.auth_user = user_dict
                                    st.session_state.is_logged_out = False
                                    st.session_state.cookie_saved = False
                                    st.query_params["auth"] = create_auth_token(user_row["username"], role="staff")
                                    st.success(f"เข้าสู่ระบบสำเร็จ: ยินดีต้อนรับคุณ {user_row['display_name']}")
                                    st.rerun()
                            else:
                                st.error("รหัส PIN 6 หลักไม่ถูกต้อง")

            st.divider()
            if st.button("ลืมรหัสผ่าน (Forgot Password)", use_container_width=True):
                st.session_state.show_forgot_password = not st.session_state.show_forgot_password

        # หน้าต่างรีเซ็ตรหัสผ่าน KuromiBlackCat
        if st.session_state.show_forgot_password:
            with col_help:
                st.warning("ขั้นตอนขอรีเซ็ตรหัสผ่าน")
                admin_contact = st.secrets.get("security", {}).get("admin_contact", "admin@Onelink.co.th")
                st.markdown(f"1. โปรดติดต่อผู้ดูแลระบบ (Teams: **`{admin_contact}`**) เพื่อยืนยันตัวตนจริง<br>2. คุณจะได้รับรหัสยืนยันพิเศษเพื่อนำมากรอกด้านล่าง", unsafe_allow_html=True)
                
                with st.form("forgot_pw_form"):
                    reset_user_choice = st.selectbox("เลือกบัญชีของคุณ", options=ALL_DISPLAY_NAMES)
                    secret_input = st.text_input("กรอกรหัสยืนยันจากผู้ดูแลระบบ (Secret Code)", type="password", placeholder="กรอกรหัสที่ได้รับ")
                    new_reset_pin = st.text_input("ตั้งรหัส PIN 6 หลักใหม่", type="password", max_chars=6, placeholder="••••••")
                    confirm_reset_pin = st.text_input("ยืนยันรหัส PIN 6 หลักใหม่อีกครั้ง", type="password", max_chars=6, placeholder="••••••")
                    
                    reset_submit = st.form_submit_button("ยืนยันการตั้งรหัสผ่านใหม่", use_container_width=True)
                    if reset_submit:
                        expected_secret = st.secrets.get("security", {}).get("admin_reset_code", "KuromiBlackCat")
                        if secret_input.strip() != expected_secret:
                            st.error("รหัสยืนยันไม่ถูกต้อง โปรดตรวจสอบรหัสลับจากผู้ดูแลระบบ")
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

    with tab_guest:
        st.subheader("เข้าใช้งานสำหรับผู้ประสานงานชั่วคราว (Guest Collaborator)")
        st.caption("สำหรับผู้ประสานงานที่ไม่มีบัญชีประจำ สามารถระบุชื่อและอีเมลเพื่อเปิดคำสั่งงานหรือบันทึกความคืบหน้าได้ทันที")

        col_g1, col_g2 = st.columns([1, 1])
        with col_g1:
            with st.form("guest_login_form"):
                guest_name = st.text_input("ชื่อ-นามสกุล หรือ หน่วยงานผู้ประสานงาน", placeholder="สมชาย ประสานงานไอที", key="guest_name_input")
                guest_email = st.text_input("อีเมลสำหรับติดต่อ (Email)", placeholder="name.s@example.com", key="guest_email_input")
                guest_submit = st.form_submit_button("เข้าใช้งานในฐานะผู้ประสานงาน (Enter as Guest)", type="primary", use_container_width=True)

                if guest_submit:
                    g_name_clean = guest_name.strip()
                    g_email_clean = guest_email.strip().lower()
                    import re
                    email_pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

                    if not g_name_clean:
                        st.error("กรุณาระบุชื่อหรือหน่วยงานผู้ประสานงาน")
                    elif not g_email_clean or not re.match(email_pattern, g_email_clean):
                        st.error("กรุณาระบุรูปแบบอีเมลที่ถูกต้อง (ตัวอย่าง: name.s@example.com)")
                    else:
                        st.session_state.auth_user = {
                            "username": f"guest_{g_email_clean.split('@')[0]}",
                            "display_name": f"{g_name_clean} (Guest: {g_email_clean})",
                            "role": "guest",
                            "email": g_email_clean
                        }
                        st.query_params["auth"] = create_auth_token(g_email_clean, role="guest")
                        st.query_params["guest_name"] = f"{g_name_clean} (Guest: {g_email_clean})"
                        st.success(f"เข้าสู่ระบบชั่วคราวสำเร็จ: ยินดีต้อนรับคุณ {g_name_clean}")
                        st.rerun()

        with col_g2:
            st.info("""
            **สิทธิ์การใช้งานสำหรับผู้ประสานงานชั่วคราว (Guest):**
            - สามารถสร้างคำสั่งงานประสานงานใหม่ได้ (ระบุ Email ตนเองอัตโนมัติ)
            - สามารถบันทึกความคืบหน้ารายขั้นตอน (Step Note) ในงานที่ตนเองเปิดได้
            - ระบบจะบันทึก Email ลง Audit Trail และแจ้งเตือนเข้า Teams โดยอัตโนมัติ
            - *สิทธิ์ในการตรวจรับปิดงานหรือยกเลิกงานสงวนเฉพาะเจ้าหน้าที่ผู้ดูแลระบบเท่านั้น*
            """)
    st.stop()

# ----------------- ส่วนหัวหน้าเว็บแบบ Top Navigation (ไม่มี Sidebar) -----------------
current_user = st.session_state.auth_user
if not current_user:
    st.stop()
my_display_name = current_user.get("display_name", "User") if current_user else "User"

# บันทึก Cookie แบบ Google/Facebook (เปิดแท็บใหม่ หรือปิดเปิดเบราว์เซอร์ใหม่ก็ยังจำสถานะผู้ใช้นี้ไว้ 30 วัน)
if not st.session_state.get("cookie_saved", False):
    user_token = create_auth_token(current_user["username"], role=current_user.get("role", "staff"))
    set_persistent_cookie(user_token)
    st.session_state.cookie_saved = True

# แถบ Header แสดงข้อมูลผู้ใช้, ปุ่ม Sync ข้อมูล และปุ่ม Logout
top_col1, top_col2, top_col3, top_col4 = st.columns([3, 2, 1.2, 1])
with top_col1:
    st.markdown(f"### 📋 Mission Control")
with top_col2:
    st.markdown(f"👤 ผู้ใช้งาน: **{my_display_name}** | 🟢 `{db_status}`")
with top_col3:
    if st.button("🔄 ซิงค์ข้อมูลล่าสุด", help="กดเพื่อดึงสถานะงานที่ผู้ใช้อื่นอัปเดตทันที", use_container_width=True):
        st.rerun()
with top_col4:
    if st.button("ออกจากระบบ (Logout)", use_container_width=True):
        st.session_state.auth_user = None
        st.session_state.pending_change_pin_user = None
        st.session_state.keypad_pin = ""
        st.session_state.show_forgot_password = False
        st.session_state.is_logged_out = True
        st.session_state.cookie_saved = False
        st.query_params.clear()
        clear_persistent_cookie()
        st.rerun()

st.divider()

# ----------------- Two-Phase Confirmation Dialogs (ตามข้อเสนอแนะความปลอดภัย) -----------------
@st.dialog("ยืนยันการตรวจรับและปิดงาน")
def confirm_close_dialog(dlg_order_id, dlg_row_idx):
    st.write(f"คุณต้องการยืนยันการตรวจรับและเปลี่ยนสถานะคำสั่งงาน `{dlg_order_id}` เป็น **'เสร็จสิ้น'** หรือไม่?")
    st.warning("⚠️ การดำเนินการนี้ถือว่างานได้รับการส่งมอบและตรวจสอบครบถ้วนสมบูรณ์แล้ว")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("ยืนยันปิดงาน", type="primary", use_container_width=True, key=f"dlg_close_yes_{dlg_order_id}"):
            orders_df.loc[dlg_row_idx, "status"] = "เสร็จสิ้น"
            save_orders_data(conn, orders_df)
            send_teams_notification(dlg_order_id, orders_df.loc[dlg_row_idx, 'task_title'], orders_df.loc[dlg_row_idx, 'creator'], orders_df.loc[dlg_row_idx, 'assignee'], orders_df.loc[dlg_row_idx, 'deadline'], "เสร็จสิ้น", f"{my_display_name} ตรวจรับและปิดงานเรียบร้อยแล้ว")
            st.toast(f"ปิดงาน {dlg_order_id} เรียบร้อยแล้ว", icon="✅")
            st.rerun()
    with c2:
        if st.button("ยกเลิก", use_container_width=True, key=f"dlg_close_no_{dlg_order_id}"):
            st.rerun()

@st.dialog("ยืนยันการยกเลิกคำสั่งงาน")
def confirm_cancel_dialog(dlg_order_id, dlg_row_idx):
    st.write(f"คุณต้องการยกเลิกคำสั่งงาน `{dlg_order_id}` หรือไม่?")
    st.error("🚨 คำสั่งงานนี้จะถูกเปลี่ยนสถานะเป็น 'ยกเลิก' (Soft Delete) และซ่อนจากมุมมองปกติ")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("ยืนยันยกเลิกคำสั่งงาน", type="primary", use_container_width=True, key=f"dlg_cancel_yes_{dlg_order_id}"):
            orders_df.loc[dlg_row_idx, "status"] = "ยกเลิก"
            save_orders_data(conn, orders_df)
            send_teams_notification(dlg_order_id, orders_df.loc[dlg_row_idx, 'task_title'], orders_df.loc[dlg_row_idx, 'creator'], orders_df.loc[dlg_row_idx, 'assignee'], orders_df.loc[dlg_row_idx, 'deadline'], "ยกเลิก", f"{my_display_name} ได้ยกเลิกคำสั่งงานนี้แล้ว")
            st.toast(f"ยกเลิกคำสั่งงาน {dlg_order_id} เรียบร้อยแล้ว", icon="🗑️")
            st.rerun()
    with c2:
        if st.button("ย้อนกลับ", use_container_width=True, key=f"dlg_cancel_no_{dlg_order_id}"):
            st.rerun()

@st.dialog("ยืนยันการส่งกลับแก้ไข")
def confirm_reject_dialog(dlg_order_id, dlg_row_idx):
    st.write(f"คุณต้องการส่งคำสั่งงาน `{dlg_order_id}` กลับไปให้ผู้รับผิดชอบปรับปรุงแก้ไขหรือไม่?")
    reason = st.text_input("ระบุสิ่งที่ต้องการให้แก้ไขเพิ่มเติม:", placeholder="เช่น ขอให้เพิ่มเอกสารสรุปผลและตรวจสอบการตั้งค่าอีกครั้ง")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("ยืนยันส่งกลับแก้ไข", type="primary", use_container_width=True, key=f"dlg_reject_yes_{dlg_order_id}"):
            orders_df.loc[dlg_row_idx, "status"] = "กำลังดำเนินการ"
            save_orders_data(conn, orders_df)
            note_msg = f"{my_display_name} ส่งกลับแก้ไข: {reason}" if reason else f"{my_display_name} ขอให้ปรับปรุงแก้ไขงานเพิ่มเติม"
            send_teams_notification(dlg_order_id, orders_df.loc[dlg_row_idx, 'task_title'], orders_df.loc[dlg_row_idx, 'creator'], orders_df.loc[dlg_row_idx, 'assignee'], orders_df.loc[dlg_row_idx, 'deadline'], "กำลังดำเนินการ", note_msg)
            st.toast(f"ส่งกลับงาน {dlg_order_id} ให้แก้ไขเรียบร้อย", icon="↩️")
            st.rerun()
    with c2:
        if st.button("ย้อนกลับ", use_container_width=True, key=f"dlg_reject_no_{dlg_order_id}"):
            st.rerun()

# ----------------- ตรวจสอบ URL Query Parameter Sub-page Router -----------------
view_mode_url = st.query_params.get("view", None)
selected_order_id = st.query_params.get("order_id", None)

# --- Sub-page 1: รายละเอียดคำสั่งงานและแผงดำเนินการ (Action Panel) ---
if view_mode_url == "detail" and selected_order_id:
    b_col1, b_col2 = st.columns([2.5, 7.5])
    with b_col1:
        if st.button("⬅️ กลับหน้ากระดานหลัก", type="secondary", use_container_width=True):
            clear_subpage_params()
            st.rerun()
    with b_col2:
        st.markdown(f"#### 🔍 รายละเอียดและแผงดำเนินการ: `{selected_order_id}`")

    target_rows = orders_df[orders_df["order_id"] == selected_order_id]
    if target_rows.empty:
        st.error(f"ไม่พบข้อมูลคำสั่งงานรหัส '{selected_order_id}' ในระบบ")
        if st.button("กลับสู่หน้าหลัก"):
            clear_subpage_params()
            st.rerun()
        st.stop()

    selected_row = target_rows.iloc[0]
    row_idx = target_rows.index[0]

    st_text = selected_row['status']
    if "เสร็จ" in st_text:
        badge_style = "background:#d1fae5; color:#065f46; border:1px solid #a7f3d0;"
    elif "ยกเลิก" in st_text:
        badge_style = "background:#fee2e2; color:#991b1b; border:1px solid #fecaca;"
    elif "ดำเนิน" in st_text:
        badge_style = "background:#dbeafe; color:#1e40af; border:1px solid #bfdbfe;"
    else:
        badge_style = "background:#fef3c7; color:#92400e; border:1px solid #fde68a;"

    st.markdown(f"""
    <div style='background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:18px 22px; margin-bottom:16px;'>
        <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;'>
            <span style='font-size:20px; font-weight:700; color:#1e293b;'>{selected_row['task_title']}</span>
            <span style='{badge_style} padding:4px 12px; border-radius:12px; font-weight:700; font-size:14px;'>{st_text}</span>
        </div>
        <div style='display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:12px; font-size:14px; color:#475569;'>
            <div><strong>รหัสคำสั่งงาน:</strong> <code>{selected_row['order_id']}</code></div>
            <div><strong>กำหนดส่ง:</strong> <code>{selected_row['deadline']}</code></div>
            <div><strong>ผู้ลงบันทึก:</strong> {selected_row['recorded_by']}</div>
            <div><strong>สร้างเมื่อ:</strong> {selected_row['created_at']}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    det_col1, det_col2 = st.columns(2)
    with det_col1:
        st.markdown(f"**👑 คนสั่ง (Creator):** {selected_row['creator']}")
        st.caption(f"สถานะยืนยันคนสั่ง: `{selected_row['creator_confirmed']}`")
    with det_col2:
        st.markdown(f"**👤 คนรับผิดชอบ (Assignee):** {selected_row['assignee']}")
        st.caption(f"สถานะยืนยันคนรับผิดชอบ: `{selected_row['assignee_confirmed']}`")

    st.info(f"**📝 รายละเอียดคำสั่งงานทั้งหมด:**\n\n{selected_row['description']}")

    teams_chat_creator_url = generate_teams_chat_url(
        selected_row['creator'],
        f"สวัสดีครับ ขอแจ้งอัปเดตงาน {selected_row['order_id']}: {selected_row['task_title']} (สถานะ: {selected_row['status']})"
    )
    st.link_button(f"💬 เปิดแชท Teams ทักหาคนสั่งงาน ({selected_row['creator']})", url=teams_chat_creator_url, use_container_width=True)

    st.subheader("⚡ แผงดำเนินการคำสั่งงาน (Action Panel)")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    is_creator = (my_display_name == selected_row['creator'])
    is_assignee = (my_display_name == selected_row['assignee'])
    is_admin = ("cto" in my_display_name.lower()) or (current_user.get("role") == "admin") or ("herren" in my_display_name.lower())

    # สิทธิ์การตรวจรับและปิดงาน: คนสั่งงาน หรือ CTO/Admin เท่านั้น (ผู้รับผิดชอบตรวจรับงานตัวเองไม่ได้)
    can_close = (is_creator or is_admin) and (not is_assignee or is_admin)
    # สิทธิ์ยกเลิกงาน: คนสั่งงาน หรือ CTO/Admin เท่านั้น
    can_cancel = (is_creator or is_admin)

    act_col1, act_col2, act_col3, act_col4 = st.columns(4)

    # 1. ขั้นตอนยืนยันคำสั่งงาน (Dual Confirmation)
    if selected_row['status'] == "รอยืนยัน":
        if is_creator and "รอยืนยัน" in str(selected_row['creator_confirmed']):
            with act_col1:
                if st.button("👑 คนสั่งยืนยันความถูกต้อง", key=f"sp_cconf_{selected_order_id}", type="primary", use_container_width=True):
                    orders_df.loc[row_idx, "creator_confirmed"] = f"ยืนยันแล้ว ({now_str})"
                    if "ยืนยันแล้ว" in str(orders_df.loc[row_idx, "assignee_confirmed"]):
                        orders_df.loc[row_idx, "status"] = "กำลังดำเนินการ"
                    save_orders_data(conn, orders_df)
                    send_teams_notification(selected_order_id, selected_row['task_title'], selected_row['creator'], selected_row['assignee'], selected_row['deadline'], orders_df.loc[row_idx, "status"], f"{my_display_name} ยืนยันคำสั่งงานแล้ว")
                    st.toast("ยืนยันคำสั่งงานเรียบร้อย", icon="✅")
                    st.rerun()

        if is_assignee and "รอยืนยัน" in str(selected_row['assignee_confirmed']):
            with act_col2:
                if st.button("👤 คนรับผิดชอบตอบรับงาน", key=f"sp_aconf_{selected_order_id}", type="primary", use_container_width=True):
                    orders_df.loc[row_idx, "assignee_confirmed"] = f"ยืนยันแล้ว ({now_str})"
                    if "ยืนยันแล้ว" in str(orders_df.loc[row_idx, "creator_confirmed"]):
                        orders_df.loc[row_idx, "status"] = "กำลังดำเนินการ"
                    save_orders_data(conn, orders_df)
                    send_teams_notification(selected_order_id, selected_row['task_title'], selected_row['creator'], selected_row['assignee'], selected_row['deadline'], orders_df.loc[row_idx, "status"], f"{my_display_name} ตอบรับคำสั่งงานแล้ว")
                    st.toast("ตอบรับงานเรียบร้อย", icon="✅")
                    st.rerun()

    # 2. ขั้นตอนกำลังดำเนินการ (In Progress) -> ผู้รับผิดชอบส่งงานได้เท่านั้น / คนสั่งงานรอตรวจรับ
    elif selected_row['status'] == "กำลังดำเนินการ":
        if is_assignee:
            with act_col2:
                if st.button("🚀 ส่งงาน (ขอตรวจสอบ)", key=f"sp_sub_{selected_order_id}", type="primary", use_container_width=True):
                    orders_df.loc[row_idx, "status"] = "รอตรวจสอบ"
                    save_orders_data(conn, orders_df)
                    send_teams_notification(selected_order_id, selected_row['task_title'], selected_row['creator'], selected_row['assignee'], selected_row['deadline'], "รอตรวจสอบ", f"{my_display_name} ส่งมอบงานแล้ว กรุณาตรวจสอบ")
                    st.toast("ส่งมอบงานเรียบร้อย รอคนสั่งตรวจสอบ", icon="🚀")
                    st.rerun()
        else:
            with act_col2:
                st.info(f"⏳ **{selected_row['assignee']}** กำลังดำเนินงาน (รอส่งมอบงาน)")

    # 3. ขั้นตอนรอตรวจสอบ (Pending Review / Acceptance) -> แสดงปุ่มตรวจรับและปิดงานเฉพาะเมื่อสถานะเป็น 'รอตรวจสอบ' เท่านั้น!
    elif selected_row['status'] == "รอตรวจสอบ":
        if can_close:
            with act_col2:
                if st.button("↩️ ส่งกลับแก้ไข", key=f"sp_reject_{selected_order_id}", use_container_width=True):
                    confirm_reject_dialog(selected_order_id, row_idx)
            with act_col3:
                if st.button("✅ ตรวจรับและปิดงาน", key=f"sp_close_{selected_order_id}", type="primary", use_container_width=True):
                    confirm_close_dialog(selected_order_id, row_idx)
        else:
            with act_col2:
                st.info(f"⏳ ส่งมอบงานแล้ว — อยู่ระหว่างรอ **{selected_row['creator']}** ตรวจรับและปิดงาน")

    # 4. สถานะเสร็จสิ้น
    elif selected_row['status'] == "เสร็จสิ้น":
        with act_col2:
            st.success("🎉 คำสั่งงานนี้ได้รับการตรวจรับและปิดงานเสร็จสมบูรณ์แล้ว")

    # 5. ปุ่มยกเลิกคำสั่งงาน (เฉพาะ Creator หรือ Admin/CTO และต้องยังไม่เสร็จสิ้น/ไม่ถูกยกเลิก)
    if can_cancel and selected_row['status'] not in ["ยกเลิก", "เสร็จสิ้น"]:
        with act_col4:
            if st.button("🗑️ ยกเลิกคำสั่งงาน (ลบงาน)", key=f"sp_del_{selected_order_id}", use_container_width=True):
                confirm_cancel_dialog(selected_order_id, row_idx)

    st.divider()

    st.subheader("📜 ประวัติความคืบหน้ารายขั้นตอนและ Audit Trail")
    item_logs = logs_df[logs_df["order_id"] == selected_order_id]
    if item_logs.empty:
        st.info("ยังไม่มีประวัติความคืบหน้าสำหรับคำสั่งงานนี้ สามารถบันทึกขั้นตอนแรกได้ที่ฟอร์มด้านล่าง")
    else:
        for _, lrow in item_logs.iterrows():
            st.markdown(f"""
            <div style='background:#ffffff; border-left:4px solid #3b82f6; border-radius:4px; padding:10px 14px; margin-bottom:8px; box-shadow:0 1px 3px rgba(0,0,0,0.05);'>
                <div style='font-size:12px; color:#64748b;'>⏰ <code>{lrow['timestamp']}</code> | 👤 บันทึกโดย <strong>{lrow['author']}</strong></div>
                <div style='margin-top:4px; font-size:14px; color:#1e293b;'>{lrow['step_note']}</div>
            </div>
            """, unsafe_allow_html=True)

    with st.expander("➕ เพิ่มบันทึกความคืบหน้ารายขั้นตอนสำหรับงานนี้ทันที", expanded=True):
        with st.form(f"quick_step_form_{selected_order_id}", clear_on_submit=True):
            q_note = st.text_area("รายละเอียดความคืบหน้า", placeholder="เช่น ดำเนินการตรวจสอบ Policy เสร็จแล้ว อยู่ระหว่างจัดทำสรุปรายงาน")
            q_teams = st.checkbox("ส่งสรุปความคืบหน้านี้เข้า Teams Chat Group ด้วย", value=True, key=f"q_teams_{selected_order_id}")
            q_submit = st.form_submit_button("บันทึกขั้นตอน", type="primary", use_container_width=True)

            if q_submit:
                if not q_note:
                    st.error("กรุณาระบุรายละเอียดความคืบหน้า")
                else:
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                    new_log = pd.DataFrame([{
                        "log_id": f"LOG-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "order_id": selected_order_id,
                        "timestamp": now_str,
                        "author": my_display_name,
                        "step_note": q_note
                    }])
                    updated_logs = pd.concat([logs_df, new_log], ignore_index=True)
                    save_logs_data(conn, updated_logs)

                    if q_teams:
                        send_teams_notification(
                            selected_order_id, 
                            selected_row["task_title"], 
                            selected_row["creator"], 
                            selected_row["assignee"], 
                            selected_row["deadline"], 
                            selected_row["status"], 
                            f"อัปเดตความคืบหน้าโดย {my_display_name}: {q_note}"
                        )
                    st.toast("บันทึกความคืบหน้าเรียบร้อยแล้ว", icon="✅")
                    st.rerun()

    st.stop()

# --- Sub-page 2: บันทึกความคืบหน้าแต่ละขั้นตอน (Step Note) ---
if view_mode_url == "step_log" and selected_order_id:
    b_col1, b_col2 = st.columns([2.5, 7.5])
    with b_col1:
        if st.button("⬅️ กลับหน้ากระดานหลัก", type="secondary", use_container_width=True):
            clear_subpage_params()
            st.rerun()
    with b_col2:
        st.markdown(f"#### 📝 บันทึกความคืบหน้ารายขั้นตอน: `{selected_order_id}`")

    target_rows = orders_df[orders_df["order_id"] == selected_order_id]
    if target_rows.empty:
        st.error(f"ไม่พบข้อมูลคำสั่งงานรหัส '{selected_order_id}' ในระบบ")
        if st.button("กลับสู่หน้าหลัก"):
            clear_subpage_params()
            st.rerun()
        st.stop()

    selected_row = target_rows.iloc[0]

    st.markdown(f"""
    <div style='background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:14px 18px; margin-bottom:16px;'>
        <div style='font-size:16px; font-weight:700; color:#1e293b; margin-bottom:6px;'>📋 {selected_row['task_title']}</div>
        <div style='display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:8px; font-size:13px; color:#475569;'>
            <div><strong>คนสั่ง:</strong> {selected_row['creator']}</div>
            <div><strong>คนรับผิดชอบ:</strong> {selected_row['assignee']}</div>
            <div><strong>กำหนดส่ง:</strong> <code>{selected_row['deadline']}</code></div>
            <div><strong>สถานะ:</strong> <code>{selected_row['status']}</code></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    teams_chat_creator_url = generate_teams_chat_url(
        selected_row['creator'],
        f"สวัสดีครับ ขอแจ้งอัปเดตงาน {selected_row['order_id']}: {selected_row['task_title']} (สถานะ: {selected_row['status']})"
    )
    st.link_button(f"💬 เปิดแชท Teams ทักหาคนสั่งงาน ({selected_row['creator']})", url=teams_chat_creator_url, use_container_width=True)

    with st.form("subpage_step_log_form", clear_on_submit=True):
        note_text = st.text_area("รายละเอียดความคืบหน้าในขั้นตอนนี้ (Step Note)", placeholder="ระบุสิ่งที่ดำเนินการ เช่น 'ติดตั้ง Configuration สำเร็จ อยู่ระหว่างทดสอบระบบ Network'")
        notify_teams = st.checkbox("ส่งสรุปความคืบหน้านี้เข้า Teams Chat Group ด้วย", value=True)
        log_submitted = st.form_submit_button("บันทึกขั้นตอน (Save Step Note)", type="primary", use_container_width=True)

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

                if notify_teams:
                    send_teams_notification(
                        selected_order_id, 
                        selected_row["task_title"], 
                        selected_row["creator"], 
                        selected_row["assignee"], 
                        selected_row["deadline"], 
                        selected_row["status"], 
                        f"อัปเดตความคืบหน้าโดย {my_display_name}: {note_text}"
                    )

                st.toast("บันทึกความคืบหน้าเรียบร้อยแล้ว", icon="✅")
                st.rerun()

    st.divider()
    st.subheader("📜 ประวัติขั้นตอนทั้งหมดของงานนี้")
    item_logs = logs_df[logs_df["order_id"] == selected_order_id]
    if item_logs.empty:
        st.info("ยังไม่มีบันทึกขั้นตอนสำหรับงานนี้")
    else:
        for _, lrow in item_logs.iterrows():
            st.markdown(f"""
            <div style='background:#ffffff; border-left:4px solid #10b981; border-radius:4px; padding:10px 14px; margin-bottom:8px; box-shadow:0 1px 3px rgba(0,0,0,0.05);'>
                <div style='font-size:12px; color:#64748b;'>⏰ <code>{lrow['timestamp']}</code> | 👤 <strong>{lrow['author']}</strong></div>
                <div style='margin-top:4px; font-size:14px; color:#1e293b;'>{lrow['step_note']}</div>
            </div>
            """, unsafe_allow_html=True)

    st.stop()

# ----------------- หน้าหลัก (Main View Tabs) -----------------
# แถบเมนูด้านบนแบบ Tabs (Active tab จะมีเส้นใต้ไฮไลต์เข้มเด่นชัด)
tab_excel, tab_new_order, tab_step_log = st.tabs([
    "📊 ตารางคำสั่งงาน (Excel View)", 
    "➕ สร้างคำสั่งงานใหม่", 
    "📝 บันทึกความคืบหน้ารายขั้นตอน"
])

# ----------------- TAB 1: ตารางคำสั่งงานสไตล์ Excel พร้อมปุ่มดำเนินการในแต่ละแถว -----------------
with tab_excel:
    top_col_left, top_col_right = st.columns([6, 4])
    with top_col_left:
        st.subheader("กระดานติดตามงาน (Excel View)")
    with top_col_right:
        view_mode = st.radio(
            "โหมดการแสดงผล:", 
            ["แบบย่อ", "แบบเต็ม"], 
            horizontal=True, 
            index=0,
            key="table_view_mode"
        )
    
    # ตัวควบคุมการกรองข้อมูล (เต็มความกว้าง)
    f_col1, f_col2, f_col3 = st.columns([1, 1, 1])
    with f_col1:
        sort_order = st.selectbox("เรียงตามวันที่สร้าง:", ["ล่าสุดก่อน (ใหม่ -> เก่า)", "เก่าสุดก่อน (เก่า -> ใหม่)"])
    with f_col2:
        filter_assignee = st.selectbox("กรองตามคนรับผิดชอบ:", ["ทั้งหมด"] + ALL_DISPLAY_NAMES)
    with f_col3:
        filter_status = st.selectbox("กรองตามสถานะ:", ["ทั้งหมด (ยกเว้นที่ยกเลิก)", "งานที่ยังไม่เสร็จสิ้น", "เสร็จสิ้น", "ทั้งหมดรวมยกเลิก"])

    # แสดงผลตารางแบบ Live Auto-Sync ผ่าน st.fragment ทุก 4 วินาที
    @st.fragment(run_every="4s")
    def render_live_task_grid(f_status, f_assignee, s_order, v_mode):
        _, _, latest_orders_df, _, _ = load_data()
        active_df = latest_orders_df.copy()

        if active_df.empty:
            st.info("ยังไม่มีรายการคำสั่งงานในระบบ กดที่แท็บ 'สร้างคำสั่งงานใหม่' เพื่อเริ่มบันทึก")
            return

        # กรองสถานะ
        if f_status == "ทั้งหมด (ยกเว้นที่ยกเลิก)":
            active_df = active_df[active_df["status"] != "ยกเลิก"]
        elif f_status == "งานที่ยังไม่เสร็จสิ้น":
            active_df = active_df[~active_df["status"].isin(["เสร็จสิ้น", "ยกเลิก"])]
        elif f_status == "เสร็จสิ้น":
            active_df = active_df[active_df["status"] == "เสร็จสิ้น"]

        # กรองคนรับผิดชอบ
        if f_assignee != "ทั้งหมด":
            active_df = active_df[active_df["assignee"] == f_assignee]

        # จัดเรียงตามวันที่
        ascending = (s_order == "เก่าสุดก่อน (เก่า -> ใหม่)")
        active_df = active_df.sort_values(by="created_at", ascending=ascending)

        if active_df.empty:
            st.warning("ไม่พบรายการคำสั่งงานที่ตรงกับเงื่อนไขการกรอง")
            return

        st.caption("🟢 เชื่อมต่อซิงค์สถานะสดแบบเรียลไทม์ (Auto-Sync ทุก 4 วิ)")

        if v_mode == "แบบย่อ":
            h_col1, h_col2, h_col3, h_col4, h_col5, h_col6, h_col7 = st.columns([1.5, 3.2, 1.6, 1.8, 1.6, 1.2, 1.2])
            h_col1.markdown("**📅 สร้างเมื่อ**")
            h_col2.markdown("**📋 ชื่องาน**")
            h_col3.markdown("**⏰ กำหนดส่ง**")
            h_col4.markdown("**👤 คนรับผิดชอบ**")
            h_col5.markdown("**🚦 สถานะ**")
            h_col6.markdown("**🔍 จัดการ**")
            h_col7.markdown("**📝 บันทึก**")
            st.markdown("<hr style='margin: 4px 0 10px 0;'>", unsafe_allow_html=True)

            for idx, r in active_df.iterrows():
                oid = r["order_id"]
                c1, c2, c3, c4, c5, c6, c7 = st.columns([1.5, 3.2, 1.6, 1.8, 1.6, 1.2, 1.2])
                c1.write(f"`{r['created_at']}`")
                c2.write(f"**{r['task_title']}**")
                c3.write(f"`{r['deadline']}`")
                c4.write(r['assignee'])

                st_text = r['status']
                if "เสร็จ" in st_text:
                    badge_style = "background:#d1fae5; color:#065f46; border:1px solid #a7f3d0;"
                elif "ยกเลิก" in st_text:
                    badge_style = "background:#fee2e2; color:#991b1b; border:1px solid #fecaca;"
                elif "ดำเนิน" in st_text:
                    badge_style = "background:#dbeafe; color:#1e40af; border:1px solid #bfdbfe;"
                else:
                    badge_style = "background:#fef3c7; color:#92400e; border:1px solid #fde68a;"

                c5.markdown(f"<span style='{badge_style} padding: 3px 8px; border-radius: 6px; font-size: 13px; font-weight: 600;'>{st_text}</span>", unsafe_allow_html=True)

                if c6.button("🔍 รายละเอียด", key=f"tbl_btn_det_{oid}_{idx}", use_container_width=True):
                    st.query_params["view"] = "detail"
                    st.query_params["order_id"] = oid
                    st.rerun()

                if c7.button("📝 บันทึกเพิ่ม", key=f"tbl_btn_log_{oid}_{idx}", use_container_width=True):
                    st.query_params["view"] = "step_log"
                    st.query_params["order_id"] = oid
                    st.rerun()
                st.markdown("<hr style='margin: 4px 0;'>", unsafe_allow_html=True)
        else:
            # แบบเต็ม (Full Detailed Columns)
            h1, h2, h3, h4, h5, h6, h7, h8, h9 = st.columns([1.3, 2.2, 1.3, 1.5, 1.5, 1.3, 1.4, 1.2, 1.2])
            h1.markdown("**📅 สร้างเมื่อ**")
            h2.markdown("**📋 ชื่องาน**")
            h3.markdown("**⏰ กำหนดส่ง**")
            h4.markdown("**👑 คนสั่ง (ยืนยัน)**")
            h5.markdown("**👤 คนรับผิดชอบ (ยืนยัน)**")
            h6.markdown("**✍️ บันทึกโดย**")
            h7.markdown("**🚦 สถานะ**")
            h8.markdown("**🔍 จัดการ**")
            h9.markdown("**📝 บันทึก**")
            st.markdown("<hr style='margin: 4px 0 10px 0;'>", unsafe_allow_html=True)

            for idx, r in active_df.iterrows():
                oid = r["order_id"]
                c1, c2, c3, c4, c5, c6, c7, c8, c9 = st.columns([1.3, 2.2, 1.3, 1.5, 1.5, 1.3, 1.4, 1.2, 1.2])
                c1.write(f"`{r['created_at']}`")
                c2.write(f"**{r['task_title']}**")
                c3.write(f"`{r['deadline']}`")
                c4.caption(f"{r['creator']}<br>`{r['creator_confirmed']}`", unsafe_allow_html=True)
                c5.caption(f"{r['assignee']}<br>`{r['assignee_confirmed']}`", unsafe_allow_html=True)
                c6.write(r['recorded_by'])

                st_text = r['status']
                if "เสร็จ" in st_text:
                    badge_style = "background:#d1fae5; color:#065f46; border:1px solid #a7f3d0;"
                elif "ยกเลิก" in st_text:
                    badge_style = "background:#fee2e2; color:#991b1b; border:1px solid #fecaca;"
                elif "ดำเนิน" in st_text:
                    badge_style = "background:#dbeafe; color:#1e40af; border:1px solid #bfdbfe;"
                else:
                    badge_style = "background:#fef3c7; color:#92400e; border:1px solid #fde68a;"

                c7.markdown(f"<span style='{badge_style} padding: 3px 6px; border-radius: 6px; font-size: 12px; font-weight: 600;'>{st_text}</span>", unsafe_allow_html=True)

                if c8.button("🔍 รายละเอียด", key=f"tbl_btn_det_{oid}_{idx}", use_container_width=True):
                    st.query_params["view"] = "detail"
                    st.query_params["order_id"] = oid
                    st.rerun()

                if c9.button("📝 บันทึกเพิ่ม", key=f"tbl_btn_log_{oid}_{idx}", use_container_width=True):
                    st.query_params["view"] = "step_log"
                    st.query_params["order_id"] = oid
                    st.rerun()
                st.markdown("<hr style='margin: 4px 0;'>", unsafe_allow_html=True)

        st.write("")
        with st.expander("📥 ดูตารางดิบสไตล์ Excel Sheet (Raw Dataframe View)", expanded=False):
            if v_mode == "แบบย่อ":
                d_cols = ["created_at", "task_title", "description", "deadline", "assignee", "status"]
                r_map = {
                    "created_at": "สร้างเมื่อ",
                    "task_title": "ชื่องาน",
                    "description": "รายละเอียด",
                    "deadline": "กำหนดส่ง",
                    "assignee": "คนรับผิดชอบ",
                    "status": "สถานะปัจจุบัน"
                }
            else:
                d_cols = [
                    "created_at", "task_title", "description", "deadline", 
                    "status", "assignee", "assignee_confirmed", "creator", 
                    "creator_confirmed", "recorded_by"
                ]
                r_map = {
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
            render_df = active_df[d_cols].rename(columns=r_map)
            st.dataframe(render_df, use_container_width=True, hide_index=True)

    render_live_task_grid(filter_status, filter_assignee, sort_order, view_mode)

# ----------------- TAB 2: สร้างคำสั่งงานใหม่ (Date Picker + Time Default 10:00) -----------------
with tab_new_order:
    st.subheader("บันทึกคำสั่งงานใหม่")
    st.caption("สามารถสร้างงานโดยตนเอง หรือจดบันทึกจากคำสั่งปากเปล่าแทนเพื่อนร่วมทีมได้ ระบบจะระบุชื่อผู้ลงบันทึกจริงเพื่อความโปร่งใส")

    if "order_form_key" not in st.session_state:
        st.session_state.order_form_key = 0

    if st.session_state.get("ticket_alert_msg"):
        st.success(st.session_state.ticket_alert_msg)
        st.session_state.ticket_alert_msg = None

    with st.form(f"new_order_form_{st.session_state.order_form_key}"):
        task_title = st.text_input("ชื่องาน / สรุปประเด็นคำสั่ง", placeholder="เช่น ขอรายละเอียด server ที่ดูแลทั้งหมด, ปรับปรุง Cloud Security", key=f"task_title_{st.session_state.order_form_key}")
        description = st.text_area("รายละเอียดงานทั้งหมด", placeholder="เช่น ขอสิทธิ์ read only access เพื่อ maintain ระบบ", key=f"desc_{st.session_state.order_form_key}")

        c1, c2 = st.columns(2)
        with c1:
            if current_user.get("role") == "guest":
                selected_creator = my_display_name
                st.text_input("คนสั่ง (Creator)", value=my_display_name, disabled=True)
            else:
                creator_default_idx = ALL_DISPLAY_NAMES.index(my_display_name) if my_display_name in ALL_DISPLAY_NAMES else 0
                selected_creator = st.selectbox("คนสั่ง (Creator)", options=ALL_DISPLAY_NAMES, index=creator_default_idx, key=f"creator_{st.session_state.order_form_key}")
        with c2:
            selected_assignee = st.selectbox("คนรับผิดชอบ (Assignee)", options=ALL_DISPLAY_NAMES, index=0, key=f"assignee_{st.session_state.order_form_key}")

        # Date Picker + Time Default 10:00 ตามข้อกำหนด
        cd_col1, cd_col2 = st.columns(2)
        with cd_col1:
            due_date = st.date_input("กำหนดส่ง (วันที่)", value=date.today() + timedelta(days=2), key=f"date_{st.session_state.order_form_key}")
        with cd_col2:
            due_time = st.time_input("กำหนดส่ง (เวลา)", value=time(10, 0), key=f"time_{st.session_state.order_form_key}")

        formatted_deadline = f"{due_date.strftime('%Y%m%d')} {due_time.strftime('%H:%M')}"
        st.caption(f"กำหนดส่งที่จะถูกบันทึก: `{formatted_deadline}`")

        notify_channel = st.multiselect("ส่งการแจ้งเตือนทันทีไปยัง", ["Microsoft Teams (Chat Group)", "Email"], default=["Microsoft Teams (Chat Group)"], key=f"notify_{st.session_state.order_form_key}")

        submitted = st.form_submit_button("บันทึกคำสั่งงาน (เปิด Ticket)", type="primary", use_container_width=True)
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

                # แสดงสถานะเปิด Ticket สำเร็จและล้างค่าในฟิลด์อัตโนมัติ
                st.session_state.order_form_key += 1
                st.session_state.ticket_alert_msg = f"🎉 เปิด Ticket สำเร็จเรียบร้อยแล้ว! รหัสคำสั่งงาน: {order_id}"
                st.toast(f"🎉 เปิด Ticket {order_id} สำเร็จเรียบร้อยแล้ว!", icon="✅")
                st.rerun()

# ----------------- TAB 3: บันทึกความคืบหน้ารายขั้นตอน -----------------
with tab_step_log:
    st.subheader("บันทึกความคืบหน้าแต่ละขั้นตอน (Step Note)")
    st.caption("เก็บบันทึกประวัติการทำงาน (Audit Trail) รายขั้นตอน ระบุผู้บันทึกและเวลาอัตโนมัติ")

    if orders_df.empty:
        st.info("ยังไม่มีงานในระบบ")
    else:
        active_orders = orders_df[~orders_df["status"].isin(["เสร็จสิ้น", "ยกเลิก"])]
        if current_user.get("role") == "guest":
            active_orders = active_orders[
                (active_orders["creator"] == my_display_name) | 
                (active_orders["recorded_by"] == my_display_name)
            ]

        if active_orders.empty:
            st.info("ไม่มีงานที่กำลังดำเนินการอยู่ (ทุกงานเสร็จสิ้นหรือยกเลิกแล้ว)")
        else:
            selected_order_display = st.selectbox(
                "เลือกรายการงานที่ต้องการบันทึกความคืบหน้า",
                options=active_orders["order_id"] + " : " + active_orders["task_title"]
            )
            selected_order_id = selected_order_display.split(" : ")[0]

            with st.form("step_log_form", clear_on_submit=True):
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



