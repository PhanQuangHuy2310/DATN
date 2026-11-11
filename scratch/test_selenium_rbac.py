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
    print("1. Logging into Web Admin...")
    driver.get("http://127.0.0.1:5174")
    time.sleep(1.5)
    driver.find_element(By.NAME, "email").send_keys("tuan.pham@eas.com")
    driver.find_element(By.NAME, "password").send_keys("Admin@123456")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "app-shell"))
    )
    time.sleep(2)

    # TEST RBAC MATRIX
    print("2. Navigating to Permissions RBAC Matrix...")
    driver.find_element(By.XPATH, "//button[contains(., 'Phân quyền')]").click()
    
    # Wait for role pill button and table row
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".role-pill-btn"))
    )
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".module-display-name"))
    )
    time.sleep(1.5)
    driver.save_screenshot(r"C:\Users\PHAN QUANG HUY\.gemini\antigravity\brain\f3a0e7bd-8e68-488f-8a6a-9f9afecd4111\phase4_admin_rbac_matrix_roles.png")
    print("Saved phase4_admin_rbac_matrix_roles.png")

    # Click MANAGER role
    print("3. Clicking Manager role pill...")
    mgr_pill = driver.find_element(By.XPATH, "//button[contains(., 'Trưởng phòng / Quản lý')]")
    mgr_pill.click()
    time.sleep(2)
    driver.save_screenshot(r"C:\Users\PHAN QUANG HUY\.gemini\antigravity\brain\f3a0e7bd-8e68-488f-8a6a-9f9afecd4111\phase4_admin_rbac_matrix_manager.png")
    print("Saved phase4_admin_rbac_matrix_manager.png")

    # Click User Override Tab
    print("4. Switching to User Override Tab...")
    driver.find_element(By.XPATH, "//button[contains(., 'Cấp quyền riêng Nhân viên')]").click()
    time.sleep(1.5)

    # Select user from dropdown
    user_select = driver.find_element(By.CSS_SELECTOR, ".user-override-header-bar select")
    options = user_select.find_elements(By.TAG_NAME, "option")
    if len(options) > 1:
        options[1].click()
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".module-display-name"))
        )
        time.sleep(1.5)
        driver.save_screenshot(r"C:\Users\PHAN QUANG HUY\.gemini\antigravity\brain\f3a0e7bd-8e68-488f-8a6a-9f9afecd4111\phase4_admin_rbac_user_matrix.png")
        print("Saved phase4_admin_rbac_user_matrix.png")

    print("RBAC TESTS COMPLETED SUCCESSFULLY!")

finally:
    driver.quit()

