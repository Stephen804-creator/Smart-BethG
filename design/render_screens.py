"""Rebuild the PNG screens from the HTML mockups.
Setup: pip install playwright && playwright install chromium
Run:   python design/render_screens.py   (writes design/screens/)
Needs mockups/logo.png and mockups/img/*.png next to the HTML files."""
import os
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
M = "file://" + os.path.join(HERE, "mockups") + "/"
OUT = os.path.join(HERE, "screens")

PHONE = [
 ("01-first-run", "splash", "Splash"), ("01-first-run", "onboarding-1", "Onboarding 1"),
 ("01-first-run", "onboarding-2", "Onboarding 2"), ("01-first-run", "onboarding-3", "Onboarding 3"),
 ("01-first-run", "onboarding-4", "Onboarding 4"), ("01-first-run", "sign-up", "Sign up"),
 ("02-home", "home", "Home"), ("02-home", "menu", "Menu"), ("02-home", "profile", "Profile"),
 ("02-home", "plus-menu", "Plus menu"), ("02-home", "mode-picker", "Mode picker"),
 ("02-home", "temporary-chat", "Temp chat"), ("02-home", "credit-usage", "Credits"),
 ("03-learn", "plan", "Learn plan"), ("03-learn", "stage-done", "Learn stage"),
 ("03-learn", "lesson", "Learn lesson"), ("03-learn", "quiz", "Learn quiz"),
 ("03-learn", "battle", "Learn battle"), ("03-learn", "result", "Learn result"),
 ("03-learn", "learned", "Learned"),
 ("04-settings", "settings", "Settings"), ("04-settings", "connectors", "Connectors"),
 ("04-settings", "connector-detail", "Connector detail"), ("04-settings", "tasks", "Tasks"),
 ("04-settings", "preview", "Preview"), ("04-settings", "code-split", "Code"),
 ("05-lab-phone", "lab-hub", "Lab"), ("05-lab-phone", "history", "Lab history"),
 ("05-lab-phone", "runtimes", "Runtimes"), ("05-lab-phone", "hw-tools", "Phone tools"),
 ("05-lab-phone", "hw-board", "Phone board"), ("05-lab-phone", "hw-sim", "Phone sim"),
 ("05-lab-phone", "hw-ai", "Phone AI"), ("05-lab-phone", "hw-more", "Phone more"),
 ("05-lab-phone", "sw-code", "Phone software"), ("05-lab-phone", "sw-preview", "Phone preview"),
 ("05-lab-phone", "sw-ai", "Phone software AI"), ("05-lab-phone", "both", "Lab both"),
]
DESKTOP = [("sw", "software"), ("swp", "software-preview"), ("hw", "hardware-board"),
           ("hwe", "edit-in-kicad"), ("hws", "simulation"), ("both", "both"), ("export", "export-menu")]
SITE = [("menu", "mobile-menu", 390), ("docs", "mobile-docs", 390), ("gate", "mobile-gate", 390)]


def shot(page, path, selector=None, full=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    (page.locator(selector).screenshot(path=path) if selector else page.screenshot(path=path, full_page=full))


with sync_playwright() as p:
    b = p.chromium.launch()
    ph = b.new_page(viewport={"width": 430, "height": 890}, device_scale_factor=2)
    ph.goto(M + "phone-app.html")
    for folder, name, key in PHONE:
        ph.evaluate(f"demo('{key}')"); ph.wait_for_timeout(250)
        shot(ph, f"{OUT}/{folder}/{name}.png", "#P")
    dk = b.new_page(viewport={"width": 1400, "height": 860}, device_scale_factor=1.5)
    dk.goto(M + "lab-desktop.html")
    for key, name in DESKTOP:
        dk.evaluate(f"demo('{key}')"); dk.wait_for_timeout(250)
        shot(dk, f"{OUT}/06-lab-desktop/{name}.png", "#app")
    ws = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    ws.goto(M + "website.html")
    shot(ws, f"{OUT}/08-website/mobile-top.png")
    shot(ws, f"{OUT}/08-website/mobile-full-scroll.png", full=True)
    for key, name, _ in SITE:
        ws.evaluate(f"demo('{key}')"); ws.wait_for_timeout(250)
        shot(ws, f"{OUT}/08-website/{name}.png")
    b.close()
print("done:", OUT)
