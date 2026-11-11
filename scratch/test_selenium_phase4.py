import time
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

sys.stdout.reconfigure(encoding="utf-8")

options = Options()
options.add_argument("--headless=new")
options.add_argument("--window-size=1600,1050")

driver = webdriver.Chrome(options=options)

try:
    print("1. Opening Web Admin login page...")
    driver.get("http://127.0.0.1:5174")
    time.sleep(1.5)

    # Login as tuan.pham@eas.com
    driver.find_element(By.NAME, "email").send_keys("tuan.pham@eas.com")
    driver.find_element(By.NAME, "password").send_keys("Admin@123456")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

    # Wait for dashboard
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "app-shell"))
    )
    print("Logged in successfully to Web Admin!")
    time.sleep(2)

    # TEST 1: Navigate to Org Chart
    print("2. Navigating to Org Chart...")
    driver.find_element(By.XPATH, "//button[contains(., 'Sơ đồ công ty')]").click()
    
    # Wait for tree to load
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".org-level-top"))
    )
    time.sleep(1)
    driver.save_screenshot(r"C:\Users\PHAN QUANG HUY\.gemini\antigravity\brain\f3a0e7bd-8e68-488f-8a6a-9f9afecd4111\phase4_admin_org_chart.png")
    print("Captured phase4_admin_org_chart.png")

    # Click on child department card to open roster modal
    dept_cards = driver.find_elements(By.CSS_SELECTOR, "button.org-dept-header-card")
    if dept_cards:
        dept_cards[0].click()
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".org-modal-card"))
        )
        time.sleep(1)
        driver.save_screenshot(r"C:\Users\PHAN QUANG HUY\.gemini\antigravity\brain\f3a0e7bd-8e68-488f-8a6a-9f9afecd4111\phase4_admin_org_chart_roster.png")
        print("Captured phase4_admin_org_chart_roster.png")
        driver.find_element(By.CSS_SELECTOR, ".org-modal-close").click()
        time.sleep(1)

    # TEST 2: Navigate to Permissions RBAC Matrix
    print("3. Navigating to Permissions RBAC Matrix...")
    driver.find_element(By.XPATH, "//button[contains(., 'Phân quyền')]").click()
    
    # Wait for matrix table
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".rbac-matrix-table"))
    )
    time.sleep(1)
    driver.save_screenshot(r"C:\Users\PHAN QUANG HUY\.gemini\antigravity\brain\f3a0e7bd-8e68-488f-8a6a-9f9afecd4111\phase4_admin_rbac_matrix_roles.png")
    print("Captured phase4_admin_rbac_matrix_roles.png")

    # Click on Manager role pill
    role_pills = driver.find_elements(By.CSS_SELECTOR, ".role-pill-btn")
    if len(role_pills) > 1:
        # Click MANAGER (last or 5th)
        role_pills[-1].click()
        time.sleep(1.5)
        driver.save_screenshot(r"C:\Users\PHAN QUANG HUY\.gemini\antigravity\brain\f3a0e7bd-8e68-488f-8a6a-9f9afecd4111\phase4_admin_rbac_matrix_manager.png")
        print("Captured phase4_admin_rbac_matrix_manager.png")

    # Switch to User Override Tab
    print("4. Testing User Override Tab...")
    driver.find_element(By.XPATH, "//button[contains(., 'Cấp quyền riêng Nhân viên')]").click()
    time.sleep(1)
    driver.save_screenshot(r"C:\Users\PHAN QUANG HUY\.gemini\antigravity\brain\f3a0e7bd-8e68-488f-8a6a-9f9afecd4111\phase4_admin_rbac_user_empty.png")
    print("Captured phase4_admin_rbac_user_empty.png")

    # Select user from dropdown
    user_select = driver.find_element(By.CSS_SELECTOR, ".user-override-header-bar select")
    options = user_select.find_elements(By.TAG_NAME, "option")
    if len(options) > 1:
        options[1].click()
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".rbac-matrix-table"))
        )
        time.sleep(1)
        driver.save_screenshot(r"C:\Users\PHAN QUANG HUY\.gemini\antigravity\brain\f3a0e7bd-8e68-488f-8a6a-9f9afecd4111\phase4_admin_rbac_user_matrix.png")
        print("Captured phase4_admin_rbac_user_matrix.png")

    print("ALL TESTS AND SCREENSHOTS COMPLETED SUCCESSFULLY!")

finally:
    driver.quit()
