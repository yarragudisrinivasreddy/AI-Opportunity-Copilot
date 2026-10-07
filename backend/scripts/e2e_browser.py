"""Browser smoke test (needs: pip install playwright && playwright install chromium).
Start the backend (uvicorn app.main:app_factory --factory --port 8080) and `npm run dev` in frontend first.
Run from backend/:  python scripts/e2e_browser.py
"""
from playwright.sync_api import sync_playwright
import io, random
from PIL import Image

img = Image.new("RGB", (400, 300), (200, 200, 200)); buf = io.BytesIO(); img.save(buf, "JPEG"); open("/tmp/t.jpg", "wb").write(buf.getvalue())

with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto("http://localhost:5173")
    page.get_by_role("button", name="Try the sample case").click()
    page.wait_for_selector("text=Sample case: read-only")
    assert page.get_by_role("heading", name="Manual product quality inspection").is_visible()
    page.get_by_role("button", name="Find AI opportunities").click()
    page.wait_for_selector("text=Where AI could help")
    assert page.locator("article.card").count() == 3
    page.get_by_role("button", name="Select this opportunity").first.click()
    page.get_by_role("button", name="Generate build brief").click()
    page.wait_for_selector("text=Build brief")
    page.get_by_role("button", name="Continue to proposals").click()
    page.wait_for_selector("text=Proposal evaluation")
    assert page.locator("text=Injection attempt flagged").count() >= 1
    print("SAMPLE FLOW OK")

    # live flow
    page.get_by_role("button", name="AI Opportunity Copilot").click()
    page.get_by_role("button", name="Show us your process").click()
    page.set_input_files("#file", "/tmp/t.jpg")
    page.fill("#desc", "Operators check parts by eye and write the result by hand.")
    page.get_by_role("button", name="Analyse my process").click()
    page.wait_for_selector("text=Check this carefully")
    page.get_by_role("button", name="Yes, this is right: continue").click()
    for ans in ["About 1,500 a day", "2 minutes", "Supervisor checks", "Some saved photos"]:
        page.wait_for_selector("#ans")
        page.fill("#ans", ans)
        page.get_by_role("button", name="Answer", exact=True).click()
        page.wait_for_timeout(300)
    page.get_by_role("button", name="Find AI opportunities").click()
    page.wait_for_selector("text=Where AI could help")
    page.get_by_role("button", name="Select this opportunity").first.click()
    page.fill("#w", "12"); page.fill("#bl", "800000"); page.fill("#bh", "1200000")
    page.get_by_role("button", name="Generate build brief").click()
    page.wait_for_selector("text=Build brief")
    assert "hours/day" in page.content()
    page.get_by_role("button", name="Continue to proposals").click()
    page.get_by_role("button", name="Request simulated proposals").click()
    page.get_by_role("button", name="Evaluate proposals").wait_for()
    page.get_by_role("button", name="Evaluate proposals").click()
    page.wait_for_selector("text=Proposal evaluation")
    assert page.locator("text=Injection attempt flagged").count() >= 1
    page.get_by_role("button", name="Delete this case and its data").click()
    page.wait_for_selector("text=What could AI improve in your work?")
    print("LIVE FLOW OK")
    print("console/page errors:", errors)
    page.screenshot(path="/tmp/home.png")
    b.close()
