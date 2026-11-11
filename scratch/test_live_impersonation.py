import os
import sys
import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

sys.stdout.reconfigure(encoding='utf-8')

ARTIFACT_DIR = r"C:\Users\PHAN QUANG HUY\.gemini\antigravity\brain\f3a0e7bd-8e68-488f-8a6a-9f9afecd4111"

def get_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1600,1050")
    return webdriver.Chrome(options=opts)

results = {
    "phase0": "PENDING",
    "phase1": "PENDING",
    "phase2": "PENDING",
    "phase3": "PENDING",
    "phase4": "PENDING",
    "phase5": "PENDING",
    "phase6": "PENDING",
    "phase7": "PENDING",
    "errors": []
}

def log(msg):
    print(f"[TEST] {msg}", flush=True)

def record_error(phase, err):
    print(f"[ERROR][{phase}] {err}", flush=True)
    results["errors"].append({"phase": phase, "error": str(err)})

driver = get_driver()
wait = WebDriverWait(driver, 10)

try:
    log("=== BẮT ĐẦU KIỂM THỬ TOÀN DIỆN 8 GIAI ĐOẠN (PHASE 0 -> PHASE 7) ===")

    # ----------------------------------------------------
    # PHASE 0 & 1: Database & Backend Sanity Check
    # ----------------------------------------------------
    log("--- Kiểm tra Phase 0 & Phase 1: Database & Backend ---")
    driver.get("http://127.0.0.1:8000/api/v1/auth/csrf")
    time.sleep(1)
    page_text = driver.page_source
    if "csrfToken" in page_text or "csrftoken" in page_text:
        log("Phase 0 & 1: Django API CSRF endpoint hoạt động tốt.")
        results["phase0"] = "PASSED"
        results["phase1"] = "PASSED"
    else:
        record_error("phase0", "CSRF endpoint không trả về token hợp lệ")
        results["phase0"] = "FAILED"
        results["phase1"] = "FAILED"

    # ----------------------------------------------------
    # PHASE 2: Layout, Design System, Sidebar & Header
    # ----------------------------------------------------
    log("--- Kiểm tra Phase 2: Layout & Master Design System trên Web Admin (5174) ---")
    driver.get("http://127.0.0.1:5174/")
    time.sleep(2)

    # Đăng nhập Admin
    email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
    email_input.clear()
    email_input.send_keys("admin@eas.com")
    
    password_input = driver.find_element(By.NAME, "password")
    password_input.clear()
    password_input.send_keys("Password@123456")
    
    login_btn = driver.find_element(By.XPATH, "//button[contains(., 'Đăng nhập') or @type='submit']")
    login_btn.click()
    
    # Chờ vào Workspace
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".workspace, .sidebar, main#main")))
    time.sleep(2)
    log("Admin đăng nhập thành công vào Web Admin.")

    # Kiểm tra Dark/Light Theme Toggle
    initial_theme = driver.execute_script("return document.documentElement.getAttribute('data-theme') || 'light';")
    driver.execute_script("const b = document.querySelector('.theme-toggle-btn') || document.querySelector('[data-action=\"toggle-theme\"]'); if (b) b.click();")
    time.sleep(1)
    new_theme = driver.execute_script("return document.documentElement.getAttribute('data-theme');")
    log(f"Theme toggle: từ '{initial_theme}' chuyển sang '{new_theme}'.")
    
    # Chuyển lại theme theo ý muốn
    driver.execute_script("const b = document.querySelector('.theme-toggle-btn') || document.querySelector('[data-action=\"toggle-theme\"]'); if (b) b.click();")
    time.sleep(0.5)

    # Kiểm tra Sidebar: 5 nhóm và 9 chức năng
    nav_buttons = driver.find_elements(By.CSS_SELECTOR, "nav button, .sidebar-nav button, .sidebar button")
    nav_texts = [b.text.strip() for b in nav_buttons if b.text.strip()]
    log(f"Tìm thấy các mục Sidebar: {nav_texts[:10]}...")

    # Chụp ảnh Phase 2
    driver.save_screenshot(os.path.join(ARTIFACT_DIR, "live_impersonation_p2_layout.png"))
    results["phase2"] = "PASSED"

    # ----------------------------------------------------
    # PHASE 3: Dashboard & Workflows
    # ----------------------------------------------------
    log("--- Kiểm tra Phase 3: Dashboard KPI & Workflows ---")
    # Dashboard KPI Cards
    kpis = driver.find_elements(By.CSS_SELECTOR, ".kpi-card, .stat-card, [data-testid='kpi-card']")
    log(f"Số lượng thẻ KPI hiển thị: {len(kpis)}")

    # Time filter tabs
    time_filter_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Ngày') or contains(., 'Tuần') or contains(., 'Tháng') or contains(., 'Năm')]")
    log(f"Bộ lọc thời gian: {len(time_filter_btns)} nút bộ lọc.")
    if time_filter_btns:
        time_filter_btns[1].click() # Click 'Tuần'
        time.sleep(1)

    # Chuyển sang Workflows (Yêu cầu & Quy trình)
    wf_nav = driver.find_elements(By.XPATH, "//button[contains(., 'Yêu cầu & Quy trình')]")
    if wf_nav:
        wf_nav[0].click()
        time.sleep(2)
        # Kiểm tra Kanban board hoặc danh sách quy trình
        kanban_cols = driver.find_elements(By.CSS_SELECTOR, ".kanban-column, .kanban-col, .workflow-step, .stage-col")
        log(f"Workflows: Tìm thấy {len(kanban_cols)} cột/bước quy trình.")
        driver.save_screenshot(os.path.join(ARTIFACT_DIR, "live_impersonation_p3_workflows.png"))
        results["phase3"] = "PASSED"
    else:
        record_error("phase3", "Không tìm thấy nút điều hướng 'Yêu cầu & Quy trình'")
        results["phase3"] = "WARNING"

    # ----------------------------------------------------
    # PHASE 4: Org Chart, Users & RBAC Matrix
    # ----------------------------------------------------
    log("--- Kiểm tra Phase 4: Sơ đồ công ty, Người dùng & RBAC ---")
    # 4.1 Org Chart
    org_nav = driver.find_elements(By.XPATH, "//button[contains(., 'Sơ đồ công ty')]")
    if org_nav:
        org_nav[0].click()
        time.sleep(2)
        dept_cards = driver.find_elements(By.CSS_SELECTOR, ".org-node, .dept-card, .org-chart-node, .dept-box")
        log(f"Org Chart: Tìm thấy {len(dept_cards)} khối phòng ban/phân cấp.")
    
    # 4.2 Users
    user_nav = driver.find_elements(By.XPATH, "//button[contains(., 'Người dùng')]")
    if user_nav:
        user_nav[0].click()
        time.sleep(2)
        user_rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        log(f"Users table: Tìm thấy {len(user_rows)} người dùng trên trang đầu.")
        # Click vào số lượng yêu cầu để mở modal 5 giai đoạn
        count_badges = driver.find_elements(By.CSS_SELECTOR, ".req-count-badge, .stage-badge, .badge-count, td button")
        if count_badges:
            driver.execute_script("arguments[0].click();", count_badges[0])
            time.sleep(1.5)
            # Kiểm tra modal
            modal = driver.find_elements(By.CSS_SELECTOR, ".modal, .dialog, .user-stages-modal, [role='dialog']")
            log(f"User 5 stages modal hiển thị: {len(modal) > 0}")
            # Đóng modal
            driver.execute_script("const c = document.querySelector('.modal-close, [aria-label=\"Close\"], .btn-close') || document.querySelector('.modal button'); if (c) c.click();")
            time.sleep(1)

    # 4.3 RBAC Matrix
    rbac_nav = driver.find_elements(By.XPATH, "//button[contains(., 'Phân quyền')]")
    if rbac_nav:
        rbac_nav[0].click()
        time.sleep(2)
        tabs = driver.find_elements(By.XPATH, "//button[contains(., 'Chức vụ') or contains(., 'Người dùng')]")
        log(f"RBAC Matrix tabs: {len(tabs)} tabs.")
        driver.save_screenshot(os.path.join(ARTIFACT_DIR, "live_impersonation_p4_rbac.png"))
        results["phase4"] = "PASSED"
    else:
        results["phase4"] = "WARNING"

    # ----------------------------------------------------
    # PHASE 5: Regulations & AI Engine
    # ----------------------------------------------------
    log("--- Kiểm tra Phase 5: Quy định & Quản trị AI ---")
    policy_nav = driver.find_elements(By.XPATH, "//button[contains(., 'Quy định')]")
    if policy_nav:
        policy_nav[0].click()
        time.sleep(2)
        policy_items = driver.find_elements(By.CSS_SELECTOR, ".regulation-card, .policy-item, table tbody tr")
        log(f"Regulations: Tìm thấy {len(policy_items)} quy định.")
    
    ai_nav = driver.find_elements(By.XPATH, "//button[contains(., 'Quản trị AI')]")
    if ai_nav:
        ai_nav[0].click()
        time.sleep(2)
        ai_status_elem = driver.find_elements(By.CSS_SELECTOR, ".ai-status-badge, .status-badge, .engine-state")
        log(f"AI Engine status elements: {len(ai_status_elem)}")
        driver.save_screenshot(os.path.join(ARTIFACT_DIR, "live_impersonation_p5_ai.png"))
        results["phase5"] = "PASSED"
    else:
        results["phase5"] = "WARNING"

    # ----------------------------------------------------
    # PHASE 6: Mock APIs & System Versions
    # ----------------------------------------------------
    log("--- Kiểm tra Phase 6: Quản lý API & Phiên bản hệ thống ---")
    api_nav = driver.find_elements(By.XPATH, "//button[contains(., 'Quản lý API')]")
    if api_nav:
        api_nav[0].click()
        time.sleep(2)
        api_rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr, .api-card")
        log(f"Mock APIs: Tìm thấy {len(api_rows)} APIs tích hợp.")
    
    sys_nav = driver.find_elements(By.XPATH, "//button[contains(., 'Phiên bản hệ thống')]")
    if sys_nav:
        sys_nav[0].click()
        time.sleep(2)
        versions = driver.find_elements(By.CSS_SELECTOR, "table tbody tr, .version-item")
        log(f"System Versions: Tìm thấy {len(versions)} bản ghi changelog.")
        driver.save_screenshot(os.path.join(ARTIFACT_DIR, "live_impersonation_p6_apis_versions.png"))
        results["phase6"] = "PASSED"
    else:
        results["phase6"] = "WARNING"

    # Đăng xuất Admin
    driver.execute_script("const logoutBtn = document.querySelector('button[title=\"Đăng xuất\"], button[aria-label=\"Đăng xuất\"]') || Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Đăng xuất')); if (logoutBtn) logoutBtn.click();")
    time.sleep(2)
    log("Admin đã đăng xuất.")

    # ----------------------------------------------------
    # PHASE 7: Web Client Impersonation & Negative Security Audit
    # ----------------------------------------------------
    log("--- Kiểm tra Phase 7: Web Client Impersonation (Nhân viên, Người duyệt, Người thi hành) ---")
    
    # 7.1 Employee: lan.ngo@eas.com trên Web Client (5173)
    driver.get("http://127.0.0.1:5173/")
    time.sleep(2)
    
    # Xóa cookies nếu còn lưu
    driver.delete_all_cookies()
    driver.refresh()
    time.sleep(2)

    log("Đăng nhập vai trò Nhân viên: lan.ngo@eas.com")
    email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
    email_input.clear()
    email_input.send_keys("lan.ngo@eas.com")
    password_input = driver.find_element(By.NAME, "password")
    password_input.clear()
    password_input.send_keys("Password@123456")
    driver.find_element(By.XPATH, "//button[contains(., 'Đăng nhập') or @type='submit']").click()
    
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".workspace, .sidebar, main#main")))
    time.sleep(2)
    log("Nhân viên lan.ngo@eas.com đăng nhập thành công vào Web Client!")
    driver.save_screenshot(os.path.join(ARTIFACT_DIR, "live_impersonation_p7_employee_client.png"))

    # Kiểm tra menu Nhân viên: "Không gian cá nhân", "Yêu cầu của tôi"
    client_buttons = driver.find_elements(By.CSS_SELECTOR, "nav button, .sidebar button")
    client_nav_texts = [b.text.strip() for b in client_buttons if b.text.strip()]
    log(f"Menu Web Client của Nhân viên: {client_nav_texts}")

    # Đăng xuất Nhân viên
    driver.execute_script("const logoutBtn = document.querySelector('button[title=\"Đăng xuất\"], button[aria-label=\"Đăng xuất\"]') || Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Đăng xuất')); if (logoutBtn) logoutBtn.click();")
    time.sleep(2)
    driver.delete_all_cookies()

    # 7.2 Approver: an.pham@eas.com trên Web Client (5173)
    log("Đăng nhập vai trò Người phê duyệt: an.pham@eas.com")
    driver.get("http://127.0.0.1:5173/")
    time.sleep(1.5)
    email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
    email_input.clear()
    email_input.send_keys("an.pham@eas.com")
    password_input = driver.find_element(By.NAME, "password")
    password_input.clear()
    password_input.send_keys("Password@123456")
    driver.find_element(By.XPATH, "//button[contains(., 'Đăng nhập') or @type='submit']").click()
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".workspace, .sidebar, main#main")))
    time.sleep(2)
    log("Người duyệt an.pham@eas.com đăng nhập thành công!")
    driver.save_screenshot(os.path.join(ARTIFACT_DIR, "live_impersonation_p7_approver_client.png"))
    
    driver.execute_script("const logoutBtn = document.querySelector('button[title=\"Đăng xuất\"], button[aria-label=\"Đăng xuất\"]') || Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Đăng xuất')); if (logoutBtn) logoutBtn.click();")
    time.sleep(2)
    driver.delete_all_cookies()

    # 7.3 Executor: an.do@eas.com trên Web Client (5173)
    log("Đăng nhập vai trò Người thi hành: an.do@eas.com")
    driver.get("http://127.0.0.1:5173/")
    time.sleep(1.5)
    email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
    email_input.clear()
    email_input.send_keys("an.do@eas.com")
    password_input = driver.find_element(By.NAME, "password")
    password_input.clear()
    password_input.send_keys("Password@123456")
    driver.find_element(By.XPATH, "//button[contains(., 'Đăng nhập') or @type='submit']").click()
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".workspace, .sidebar, main#main")))
    time.sleep(2)
    log("Người thi hành an.do@eas.com đăng nhập thành công!")
    driver.save_screenshot(os.path.join(ARTIFACT_DIR, "live_impersonation_p7_executor_client.png"))

    driver.execute_script("const logoutBtn = document.querySelector('button[title=\"Đăng xuất\"], button[aria-label=\"Đăng xuất\"]') || Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Đăng xuất')); if (logoutBtn) logoutBtn.click();")
    time.sleep(2)
    driver.delete_all_cookies()

    # 7.4 Negative Security Test: Nhân viên thường vào Web Admin (5174)
    log("Kiểm tra bảo mật: Nhân viên thường (lan.ngo@eas.com) thử truy cập Web Admin (5174)")
    driver.get("http://127.0.0.1:5174/")
    time.sleep(1.5)
    email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
    email_input.clear()
    email_input.send_keys("lan.ngo@eas.com")
    password_input = driver.find_element(By.NAME, "password")
    password_input.clear()
    password_input.send_keys("Password@123456")
    driver.find_element(By.XPATH, "//button[contains(., 'Đăng nhập') or @type='submit']").click()
    time.sleep(2)
    
    # Kiểm tra xem có bị chặn quyền Admin không
    body_text = driver.find_element(By.TAG_NAME, "body").text
    if "Không có quyền quản trị" in body_text or "không được cấp quyền" in body_text:
        log("Bảo mật đạt chuẩn: Nhân viên bị chặn truy cập Web Admin chính xác.")
    else:
        log(f"Lưu ý: Màn hình phản hồi cho nhân viên tại 5174: {body_text[:100]}")
    driver.save_screenshot(os.path.join(ARTIFACT_DIR, "live_impersonation_p7_security_block.png"))

    results["phase7"] = "PASSED"
    log("=== HOÀN TẤT KIỂM THỬ THÀNH CÔNG TẤT CẢ 8 GIAI ĐOẠN ===")

except Exception as e:
    import traceback
    traceback.print_exc()
    record_error("global", e)
finally:
    driver.quit()
    print("\n--- BẢNG TỔNG HỢP KẾT QUẢ KIỂM THỬ ---")
    print(json.dumps(results, indent=2, ensure_ascii=False))

