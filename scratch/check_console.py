import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument('--headless=new')
options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
driver = webdriver.Chrome(options=options)

try:
    driver.get('http://127.0.0.1:5174')
    time.sleep(1)
    driver.find_element(By.NAME, 'email').send_keys('tuan.pham@eas.com')
    driver.find_element(By.NAME, 'password').send_keys('Admin@123456')
    driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
    time.sleep(2)
    driver.find_element(By.XPATH, "//span[contains(., 'Người dùng')]").click()
    time.sleep(2)
    btn = driver.find_element(By.CSS_SELECTOR, '.drilldown-badge-btn')
    btn.click()
    time.sleep(3)
    for entry in driver.get_log('browser'):
        print(entry)
finally:
    driver.quit()
