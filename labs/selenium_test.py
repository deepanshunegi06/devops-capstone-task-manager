"""Selenium acceptance test against the isolated localhost Orbit deployment."""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pathlib import Path
options=webdriver.ChromeOptions()
options.binary_location='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
options.add_argument('--headless=new'); options.add_argument('--window-size=1440,1000')
options.add_argument('--no-first-run');options.add_argument('--no-default-browser-check')
driver=webdriver.Chrome(options=options)
try:
 driver.get('http://127.0.0.1:18080/login')
 wait=WebDriverWait(driver,20)
 wait.until(EC.visibility_of_element_located((By.NAME,'username'))).send_keys('demo')
 driver.find_element(By.NAME,'password').send_keys('demo-pass-2026')
 driver.find_element(By.CSS_SELECTOR,'button[type=submit]').click()
 wait.until(lambda d:'/login' not in d.current_url)
 wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,'.task-row')))
 print('PASS: authenticated login and populated task list')
 driver.save_screenshot(str(Path(__file__).parents[2]/'evidence/selenium-today.png'))
 driver.get('http://127.0.0.1:18080/#/analytics')
 wait.until(lambda d: 'analytics' in d.current_url)
 wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,'canvas,svg,.chart,.stat-card,.analytics')))
 print('PASS: analytics navigation rendered')
 driver.save_screenshot(str(Path(__file__).parents[2]/'evidence/selenium-analytics.png'))
 print('Browser:',driver.capabilities.get('browserVersion'))
finally:driver.quit()
