# Post-Approval FAANG DevOps Execution & Rollout Runbook
## Mission Control V2: Granular Step-by-Step Implementation Guide

> **Document Classification**: Lead AI & Principal DevOps Technical Runbook  
> **Associated Architecture Plan**: [MISSION_CONTROL_V2_TECHNICAL_ARCHITECTURE_PLAN.md](file:///home/herrenk/User/20261013_0935_Streamlit_Mission_Control/MISSION_CONTROL_V2_TECHNICAL_ARCHITECTURE_PLAN.md)  
> **Repository Path**: `/home/herrenk/User/20261013_0935_Streamlit_Mission_Control`  
> **Target Python Environment**: Python 3.10+ / Streamlit 1.35+

---

## 1. Operational Pre-requisites & Local Environment Setup

### 1.1 Local Workspace Verification
1. เปิด Terminal และตรวจสอบว่าโฟลเดอร์โปรเจกต์อยู่ที่:
   ```bash
   cd /home/herrenk/User/20261013_0935_Streamlit_Mission_Control
   ```
2. ตรวจสอบเวอร์ชันของ Git และ GitHub CLI:
   ```bash
   git status
   gh auth status
   ```

### 1.2 Python Virtual Environment (.venv) Initialization
สร้างและเปิดใช้งาน Virtual Environment ในเครื่อง Local:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 2. Phase 1 Implementation: Stabilization & Authentication Overhaul

### 2.1 กำจัด On-Screen Virtual Numpad (Code Refactoring in `app.py`)
1. **ลบ Session State ที่ไม่จำเป็น**:
   - นำ `st.session_state.keypad_pin` ออก
2. **แทนที่ UI Keypad ด้วย Clean Text Box**:
   - ใช้ `st.text_input("รหัส PIN 6 หลัก", type="password", max_chars=6, key="login_pin_input")`
   - รองรับการกดปุ่ม Enter หรือคลิกปุ่ม "เข้าสู่ระบบ (Login)" ได้ทันที โดยไม่มีการ Refresh หน้าจอซ้ำซ้อน

### 2.2 การปรับโครงสร้างผู้ใช้: Dual-Tab Gateway (Staff + Guest Portal)
1. **ออกแบบหน้า Login เป็น 2 Tabs**:
   - `tab_staff, tab_guest = st.tabs(["🔑 เข้าสู่ระบบ (เจ้าหน้าที่ / ทีมงาน)", "✉️ ผู้ประสานงานชั่วคราว (Guest)"])`
2. **Tab 1: บัญชีเจ้าหน้าที่ / ทีมงาน (Staff & Team Members)**:
   - ช่องกรอก `username` (Placeholder / Gray text: `name.s`)
   - ช่องกรอก `pin` แบบ `st.text_input("รหัส PIN 6 หลัก", type="password")`
   - ตรวจสอบสิทธิ์ Admin / Team Member เพื่อให้ผู้ดูแลระบบและสมาชิกสามารถกระจายงานให้รายชื่อสมาชิกในทีมได้ครบถ้วน
3. **Tab 2: Guest / Temporary User Gateway Form**:
   - ฟิลด์ที่บังคับกรอก:
     - `guest_email`: อีเมลสำหรับติดต่อและส่งแจ้งเตือนกลับ (Regex Validation: `r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"`)
     - `guest_name`: ชื่อและหน่วยงานของผู้ประสานงาน
   - บันทึกค่าลงใน Session State:
     ```python
     st.session_state.auth_user = {
         "username": f"guest_{guest_email.split('@')[0]}",
         "display_name": f"{guest_name} (Guest: {guest_email})",
         "role": "guest",
         "email": guest_email
     }
     ```
   - กำหนดสิทธิ์: สร้างงานใหม่ได้ และบันทึก Step Log ได้เฉพาะงานของตนเอง

### 2.3 การปรับแต่ง Data Contract ใน `orders.csv` / Google Sheets
1. ตรวจสอบคอลัมน์มาตรฐาน:
   - `created_at`
   - `task_title`
   - `description`
   - `deadline`
   - `status`
   - `assignee`
   - `assignee_confirmed`
   - `creator`
   - `creator_confirmed`
   - `recorded_by` (จะเก็บชื่อ Herren หรือ Guest Email ตามจริง)
   - `order_id`

---

## 3. Phase 2 Implementation: Interactive Task Navigation

### 3.1 การอัปเกรด `st.dataframe` เป็น Interactive Selection Mode & Auto Tab Routing
1. **Dynamic Tab Controller ผ่าน Session State**:
   - ใช้ `st.session_state.active_tab_index` เพื่อสลับแท็บอัตโนมัติ
2. **เปิดใช้งาน row selection ใน Tab 1 (Excel View)**:
   ```python
   selection = st.dataframe(
       render_df,
       use_container_width=True,
       hide_index=True,
       on_select="rerun",
       selection_mode="single-row"
   )
   ```
3. **ตรวจจับการคลิกแถวแล้วเด้งไป Tab 3 ทันที**:
   ```python
   selected_rows = selection.selection.rows
   if selected_rows:
       selected_idx = selected_rows[0]
       target_order_id = active_df.iloc[selected_idx]["order_id"]
       st.session_state.selected_order_for_step = target_order_id
       st.session_state.active_tab = "📝 บันทึกความคืบหน้ารายขั้นตอน"
       st.rerun()
   ```
   - เมื่อสลับไป Tab 3 ตัวฟอร์มบันทึกความคืบหน้าจะเลือกงานนั้นไว้ล่วงหน้า พร้อมให้พิมพ์ความคืบหน้าและเปลี่ยนสถานะได้ทันที

---

## 4. Quality Assurance, SRE Testing & Verification Suite

### 4.1 Test Matrix Checklist
| Test Case ID | รายละเอียดการทดสอบ | ผลลัพธ์ที่คาดหวัง | Pass / Fail |
| :--- | :--- | :--- | :---: |
| **TC-01** | ล็อกอินด้วยบัญชี Herren ผ่าน Text Input PIN | ล็อกอินสำเร็จ เข้าสู่หน้า Mission Control ใน <1 วินาที | [ ] |
| **TC-02** | ล็อกอินด้วยรหัส PIN ไม่ถูกต้อง | แสดงข้อความเตือน รหัสไม่ผ่าน ไม่เกิดบั๊กค้าง | [ ] |
| **TC-03** | เข้าใช้งานแบบ Guest โดยกรอก Email ไม่ถูกต้อง | แสดง Validation Error แจ้งให้ระบุ Email ที่ถูกต้อง | [ ] |
| **TC-04** | เข้าใช้งานแบบ Guest และบันทึกคำสั่งงานใหม่ | งานถูกสร้างในตาราง พร้อมบันทึก Email ใน recorded_by | [ ] |
| **TC-05** | ส่ง Teams Webhook แจ้งเตือน | ข้อความเด้งเข้า Teams Group Chat พร้อมรายละเอียดครบถ้วน | [ ] |
| **TC-06** | (Phase 2) คลิกแถวในตารางคำสั่งงาน | ระบบไฮไลต์งาน และเปิดฟอร์มอัปเดตสถานะงานนั้นทันที | [ ] |

---

## 5. Deployment & Git Release Automation

เมื่อทำการทดสอบในเครื่อง Local เรียบร้อย:
```bash
cd /home/herrenk/User/20261013_0935_Streamlit_Mission_Control
git add app.py README.md MISSION_CONTROL_V2_TECHNICAL_ARCHITECTURE_PLAN.md POST_APPROVAL_DEVOPS_RUNBOOK.md
git commit -m "feat: upgrade Mission Control v2 (text pin, herren-centric, guest gateway, faang proposal)"
git push origin main
```
*ระบบ Streamlit Community Cloud จะทำการตรวจจับ Commit ใหม่และ Deploy อัตโนมัติภายใน 30 วินาที*
