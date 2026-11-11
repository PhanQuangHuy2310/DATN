import time
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

sys.stdout.reconfigure(encoding='utf-8')

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--window-size=1600,1050')
d = webdriver.Chrome(options=opts)
try:
    d.get('http://127.0.0.1:5174/')
    d.find_element(By.NAME, 'email').send_keys('admin@eas.com')
    d.find_element(By.NAME, 'password').send_keys('Password@123456')
    d.find_element(By.XPATH, "//button[@type='submit']").click()
    
    WebDriverWait(d, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'button[title="Đăng xuất"], .app-header')))
    time.sleep(1)
    print('Logged in successfully!')
    buttons = [b.text.strip() for b in d.find_elements(By.CSS_SELECTOR, 'nav button, .sidebar button') if b.text.strip()]
    print('Nav buttons found:', buttons)
    
    # Check groups
    groups = [g.text.strip() for g in d.find_elements(By.CSS_SELECTOR, '.nav-group-title, .sidebar-group-title, .group-header, nav h3, nav h4') if g.text.strip()]
    print('Groups found:', groups)
    
    # Check header title
    header_title = d.find_element(By.CSS_SELECTOR, '.app-header h1, .header-title, .page-title, h1').text
    print('Active Header title:', header_title)
finally:
    d.quit()

