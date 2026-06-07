import time
import requests
from playwright.sync_api import sync_playwright

# Wait for services
print("Waiting for services to be ready...")
for i in range(30):
    try:
        requests.get("http://localhost:5173", timeout=2)
        requests.get("http://localhost:8000/health", timeout=2)
        print("Services are ready!")
        break
    except:
        time.sleep(1)
else:
    print("Services not ready, proceeding anyway...")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    
    # Screenshot 1: Initial UI
    print("Capturing initial UI...")
    page.goto("http://localhost:5173")
    time.sleep(3)
    page.screenshot(path="screenshots/01_initial_ui.png", full_page=True)
    
    # Screenshot 2: Chat interaction - Create a shaft
    print("Creating a shaft...")
    page.fill("textarea", "Create a shaft 100mm long and 20mm diameter")
    page.press("textarea", "Enter")
    time.sleep(5)
    page.screenshot(path="screenshots/02_shaft_created.png", full_page=True)
    
    # Screenshot 3: 3D viewer with model
    print("Capturing 3D model view...")
    time.sleep(2)
    page.screenshot(path="screenshots/03_3d_viewer.png", full_page=True)
    
    # Screenshot 4: Wireframe toggle
    print("Toggling wireframe...")
    page.click("input[type='checkbox']:near(:text('Wireframe'))")
    time.sleep(1)
    page.screenshot(path="screenshots/04_wireframe_mode.png", full_page=True)
    
    # Screenshot 5: Inspector panel
    print("Selecting component in inspector...")
    page.click("select")
    page.select_option("select", index=0)
    time.sleep(1)
    page.screenshot(path="screenshots/05_inspector_panel.png", full_page=True)
    
    # Screenshot 6: Create a gear
    print("Creating a gear...")
    page.fill("textarea", "Create a gear with 20 teeth")
    page.press("textarea", "Enter")
    time.sleep(3)
    page.screenshot(path="screenshots/06_gear_prompt.png", full_page=True)
    
    # Answer module parameter
    time.sleep(2)
    page.fill("textarea", "2.5")
    page.press("textarea", "Enter")
    time.sleep(5)
    page.screenshot(path="screenshots/07_gear_created.png", full_page=True)
    
    # Screenshot 7: Explode view
    print("Testing explode view...")
    page.fill("input[type='range']", "50")
    time.sleep(1)
    page.screenshot(path="screenshots/08_explode_view.png", full_page=True)
    
    # Screenshot 8: Multiple components
    print("Final view with multiple components...")
    page.fill("input[type='range']", "0")
    time.sleep(1)
    page.screenshot(path="screenshots/09_final_assembly.png", full_page=True)
    
    print("Screenshots captured successfully!")
    browser.close()
