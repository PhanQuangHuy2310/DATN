import time
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

sys.stdout.reconfigure(encoding='utf-8')

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--window-size=1600,1050')
d = webdriver.Chrome(options=opts)
try:
    d.get('http://127.0.0.1:5173/')
    time.sleep(1.5)
    print('Initial page title:', d.title)
    print('Initial page text:', d.find_element(By.TAG_NAME, 'body').text[:200].replace('\n', ' -- '))
    
    email_in = d.find_element(By.NAME, 'email')
    email_in.send_keys('lan.ngo@eas.com')
    pass_in = d.find_element(By.NAME, 'password')
    pass_in.send_keys('Password@123456')
    d.find_element(By.XPATH, "//button[@type='submit']").click()
    
    time.sleep(3)
    print('After submit page text:', d.find_element(By.TAG_NAME, 'body').text[:300].replace('\n', ' -- '))
    
    # Check browser logs
    for entry in d.get_log('browser'):
        print('BROWSER LOG:', entry)
    
    d.save_screenshot(r'C:\Users\PHAN QUANG HUY\.gemini\antigravity\brain\f3a0e7bd-8e68-488f-8a6a-9f9afecd4111\debug_client_lan_ngo.png')
finally:
    d.quit()

