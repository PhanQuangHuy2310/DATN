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
    # Execute fetch in browser
    res = driver.execute_async_script("""
        const done = arguments[0];
        fetch('/api/v1/admin/users-management/00000002-0000-4000-8000-000000000005/requests-detail')
            .then(r => r.json().then(data => done({ status: r.status, data })))
            .catch(err => done({ ok: false, error: String(err) }));
    """)
    print('ASYNC FETCH RES:', res)
finally:
    driver.quit()

