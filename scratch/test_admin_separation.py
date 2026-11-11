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
    d.get('http://127.0.0.1:5173/')
    d.delete_all_cookies()
    d.refresh()
    time.sleep(1)
    
    email_in = WebDriverWait(d, 10).until(EC.presence_of_element_located((By.NAME, "email")))
    email_in.clear()
    email_in.send_keys('admin@eas.com')
    pass_in = d.find_element(By.NAME, "password")
    pass_in.clear()
    pass_in.send_keys('Password@123456')
    d.find_element(By.XPATH, "//button[@type='submit']").click()
    
    WebDriverWait(d, 10).until(EC.text_to_be_present_in_element((By.TAG_NAME, 'body'), 'Tài khoản quản trị'))
    print("SUCCESS! Admin separation screen detected:", d.find_element(By.TAG_NAME, 'h1').text)
    print("Screen details:", d.find_element(By.TAG_NAME, 'p').text)
finally:
    d.quit()

