"""Browser integration against the running Compose demo (write_file model)."""

import os
import time
import uuid
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright


def main():
    output = Path(".local-data/screenshots")
    output.mkdir(parents=True, exist_ok=True)
    sid = None
    errors = []
    with sync_playwright() as playwright:
        options = {"headless": True}
        if os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE"):
            options["executable_path"] = os.environ["PLAYWRIGHT_CHROMIUM_EXECUTABLE"]
        browser = playwright.chromium.launch(**options)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            page.goto("http://127.0.0.1:8080")
            page.get_by_role("button", name="New session").click()
            page.get_by_label("Git repository URL").fill(
                "https://github.com/octocat/Hello-World.git"
            )
            page.get_by_label("Session title").fill("Browser smoke " + uuid.uuid4().hex[:6])
            page.get_by_text("Initialization commands", exact=True).click()
            page.get_by_label("Initialization commands", exact=True).fill("python3 --version")
            page.get_by_role("button", name="Create session").click()
            expect(page.get_by_role("button", name="Allow Once", exact=True)).to_be_visible(
                timeout=90000
            )
            sid = page.url.split("/sessions/")[1]
            expect(page.get_by_label("Message", exact=True)).to_be_disabled()
            page.reload()
            page.get_by_role("button", name="Allow Once", exact=True).click()
            expect(page.get_by_label("Message", exact=True)).to_be_enabled(timeout=30000)
            page.get_by_label("Message", exact=True).fill("Create a file")
            page.get_by_label("Send message").click()
            page.get_by_label("Message", exact=True).fill("Keep this draft")
            page.get_by_label("Message", exact=True).focus()
            expect(page.get_by_role("button", name="Allow Once", exact=True)).to_be_visible(
                timeout=30000
            )
            expect(page.get_by_label("Message", exact=True)).to_be_focused()
            expect(page.get_by_label("Message", exact=True)).to_have_value("Keep this draft")
            page.get_by_role("button", name="Preview proposed diff").click()
            expect(page.locator(".approval-card .diff-code")).to_contain_text("+a")
            page.screenshot(path=str(output / "web-approval.png"), full_page=True)
            page.get_by_role("button", name="Allow Once", exact=True).click()
            expect(page.get_by_text("Demo run complete.", exact=False)).to_be_visible(timeout=30000)
            page.get_by_role("tab", name="Diff", exact=True).click()
            page.get_by_label("Refresh diff").click()
            expect(page.locator(".diff-code").last).to_contain_text("a")
            page.reload()
            expect(page.get_by_text("Demo run complete.", exact=False)).to_be_visible(timeout=30000)
            expect(page.get_by_label("Message", exact=True)).to_have_value("Keep this draft")
            page.screenshot(path=str(output / "web-desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path=str(output / "web-narrow.png"))
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                "Horizontal overflow"
            )
            assert not errors, errors
            print(
                "PASS: creation, setup approval, focus, preview, edit, diff, reload, draft, narrow layout"
            )
        finally:
            browser.close()
            if sid:
                with httpx.Client(base_url="http://127.0.0.1:8000/api", timeout=30) as client:
                    current = client.get(f"/sessions/{sid}").json()["session"]
                    if current["status"] in {"running", "awaiting_approval"}:
                        client.post(f"/sessions/{sid}/stop", json={})
                        for _ in range(100):
                            if (
                                client.get(f"/sessions/{sid}").json()["session"]["status"]
                                == "stopped"
                            ):
                                break
                            time.sleep(0.1)
                    response = client.post(
                        f"/sessions/{sid}/actions",
                        json={"kind": "delete", "payload": {"confirmation": "DELETE"}},
                    )
                    assert response.is_success, response.text


if __name__ == "__main__":
    main()
