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

    # Go to User Management
    print("2. Navigating to User Management...")
    driver.find_element(By.XPATH, "//button[contains(., 'Người dùng')]").click()
    time.sleep(2)

    # Wait for rows
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".user-management-table tbody tr"))
    )
    time.sleep(1)
    driver.save_screenshot(r"C:\Users\PHAN QUANG HUY\.gemini\antigravity\brain\f3a0e7bd-8e68-488f-8a6a-9f9afecd4111\phase4_admin_users_management.png")
    print("Saved phase4_admin_users_management.png")

    # 1. Test Drilldown button
    print("3. Testing drilldown drawer...")
    btn = driver.find_element(By.CSS_SELECTOR, ".drilldown-badge-btn")
    btn.click()
    
    # Wait for stage cards
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".stage-cards-grid"))
    )
    time.sleep(1)
    driver.save_screenshot(r"C:\Users\PHAN QUANG HUY\.gemini\antigravity\brain\f3a0e7bd-8e68-488f-8a6a-9f9afecd4111\phase4_admin_user_5stage_drawer.png")
    print("Saved phase4_admin_user_5stage_drawer.png")

    # Close drawer
    driver.find_element(By.CSS_SELECTOR, ".drawer-close-btn").click()
    time.sleep(1)

    # 2. Test Quick Leave / Trip Modal
    print("4. Testing leave modal...")
    leave_btn = driver.find_element(By.CSS_SELECTOR, "button[title*='Cập nhật đơn nghỉ']")
    leave_btn.click()
    
    # Wait for modal card
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".modal-card"))
    )
    time.sleep(1)
    driver.save_screenshot(r"C:\Users\PHAN QUANG HUY\.gemini\antigravity\brain\f3a0e7bd-8e68-488f-8a6a-9f9afecd4111\phase4_admin_user_leave_modal.png")
    print("Saved phase4_admin_user_leave_modal.png")

    # Click Áp dụng ngay
    print("5. Submitting leave / trip...")
    driver.find_element(By.XPATH, "//button[contains(., 'Áp dụng ngay')]").click()
    time.sleep(2)
    driver.save_screenshot(r"C:\Users\PHAN QUANG HUY\.gemini\antigravity\brain\f3a0e7bd-8e68-488f-8a6a-9f9afecd4111\phase4_admin_user_status_changed.png")
    print("Saved phase4_admin_user_status_changed.png")

    print("ALL TESTS AND SCREENSHOTS COMPLETED SUCCESSFULLY!")

finally:
    driver.quit()
