"""Capture the local OFFLINE DEMO only. Requires optional playwright and a browser."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", default="msedge", help="Installed browser channel, or chromium")
    args = parser.parse_args()
    output = ROOT / "docs/screenshots"
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel=args.channel)
        page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
        page.goto("http://127.0.0.1:8501/", wait_until="domcontentloaded")
        page.get_by_text("OFFLINE DEMO:", exact=False).wait_for()
        page.get_by_role("button", name="Try the Hue group scenario", exact=True).click()
        page.get_by_text("Proposed plan for 4 people", exact=False).wait_for(timeout=30000)
        expect(page.locator('[data-stale="true"]')).to_have_count(0)
        page.screenshot(path=str(output / "01-group.png"), full_page=True, animations="disabled")
        page.get_by_role("tab", name="Itinerary", exact=True).click()
        page.get_by_role("button", name="Keep only two places on Day 1").wait_for()
        page.screenshot(path=str(output / "02-itinerary.png"), full_page=True, animations="disabled")
        page.get_by_role("button", name="Keep only two places on Day 1").click()
        page.get_by_text("Other days are unchanged.", exact=False).wait_for()
        chat = page.get_by_placeholder("Describe your group, explore heritage, or refine your itinerary")
        chat.fill("Why did you choose Thien Mu Pagoda?")
        chat.press("Enter")
        page.get_by_role("tab", name="Sources", exact=True).click()
        page.get_by_text("[1] Synthetic Hue planning fixture", exact=True).wait_for()
        expect(page.locator('[data-stale="true"]')).to_have_count(0)
        page.screenshot(path=str(output / "03-sources.png"), full_page=True, animations="disabled")
        chat.fill("Book the first tour for 0900000000")
        chat.press("Enter")
        page.get_by_role("button", name="Confirm booking", exact=True).wait_for(timeout=30000)
        expect(page.locator('[data-stale="true"]')).to_have_count(0)
        page.get_by_role("button", name="Confirm booking", exact=True).scroll_into_view_if_needed()
        page.screenshot(path=str(output / "04-confirmation.png"), full_page=True, animations="disabled")
        page.set_viewport_size({"width": 390, "height": 844})
        collapse = page.get_by_role("button", name="Collapse sidebar", exact=True)
        if collapse.is_visible():
            collapse.click()
        page.get_by_role("heading", name="Different interests. One shared journey.").scroll_into_view_if_needed()
        page.screenshot(path=str(output / "05-mobile.png"), full_page=True, animations="disabled")
        page.get_by_role("button", name="Confirm booking", exact=True).click()
        page.get_by_text("DEMO simulation: Tour registration confirmed.", exact=True).wait_for()
        browser.close()
    print("Captured five screenshots from the local synthetic demo.")


if __name__ == "__main__":
    main()
