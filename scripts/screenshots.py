import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--record", action="store_true", help="Record a two-minute silent demo walkthrough"
    )
    args = parser.parse_args()
    output = ROOT / "docs/screenshots"
    output.mkdir(parents=True, exist_ok=True)
    checks, errors = [], []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 1440, "height": 1000},
            color_scheme="light",
            **(
                {
                    "record_video_dir": str(ROOT / "reports/video"),
                    "record_video_size": {"width": 1440, "height": 1000},
                }
                if args.record
                else {}
            ),
        )
        page = await context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        await context.request.post(args.url + "/api/simulate/reset", data={})
        if args.record:
            await page.goto(args.url + "/about")
            await page.wait_for_timeout(10000)
        response = await page.goto(args.url)
        assert response.status == 200
        await page.wait_for_selector("#start-drill")
        await page.select_option("#speed", "10")
        await page.click("#start-drill")
        await page.wait_for_selector(".match-card", timeout=15000)
        await page.wait_for_timeout(1000)
        await page.screenshot(path=str(output / "dashboard-desktop.png"), full_page=True)
        if args.record:
            await page.wait_for_timeout(18000)
        await page.locator(".match-card summary").first.click()
        await page.screenshot(path=str(output / "suggested-match.png"), full_page=True)
        if args.record:
            await page.wait_for_timeout(18000)
        await page.locator(".match-card button").filter(has_text="Approve").first.click()
        await page.wait_for_selector("#confirm-dialog[open]")
        await page.screenshot(path=str(output / "approval-review.png"), full_page=True)
        if args.record:
            await page.wait_for_timeout(12000)
        await page.click("#confirm-action")
        await page.wait_for_selector("#confirm-dialog", state="hidden")
        await page.locator(".request-card").first.click()
        await page.wait_for_selector("#drawer:not([hidden])")
        await page.screenshot(path=str(output / "card-drawer.png"), full_page=True)
        if args.record:
            await page.wait_for_timeout(12000)
        await page.keyboard.press("Escape")
        await page.get_by_role("button", name="Toggle light and dark theme").click()
        await page.screenshot(path=str(output / "dashboard-dark.png"), full_page=True)
        await page.get_by_role("button", name="Toggle light and dark theme").click()
        for width, height in [(360, 640), (390, 844), (768, 1024), (1280, 800), (1920, 1080)]:
            await page.set_viewport_size({"width": width, "height": height})
            await page.wait_for_timeout(150)
            if width < 768:
                await page.locator(".tabs button[data-tab=board]").click()
            overflow = await page.evaluate("document.documentElement.scrollWidth > innerWidth")
            checks.append(
                {"page": "/", "width": width, "height": height, "horizontal_overflow": overflow}
            )
            await page.screenshot(path=str(output / f"dashboard-{width}.png"), full_page=True)
        await page.set_viewport_size({"width": 1440, "height": 1000})
        for path in ("join", "eval", "architecture", "about", "safety"):
            await page.goto(args.url + "/" + path)
            await page.wait_for_timeout(700)
            await page.screenshot(path=str(output / (path + ".png")), full_page=True)
            if args.record and path in ("join", "eval"):
                await page.wait_for_timeout(18000)
            for width, height in [(360, 640), (390, 844), (768, 1024), (1280, 800), (1920, 1080)]:
                await page.set_viewport_size({"width": width, "height": height})
                checks.append(
                    {
                        "page": "/" + path,
                        "width": width,
                        "height": height,
                        "horizontal_overflow": await page.evaluate(
                            "document.documentElement.scrollWidth > innerWidth"
                        ),
                    }
                )
            await page.set_viewport_size({"width": 1440, "height": 1000})
        await page.goto(args.url)
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.locator(".tabs button[data-tab=board]").click()
        await page.get_by_label("Interface language").select_option("ta")
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(output / "dashboard-tamil.png"), full_page=True)
        checks.append(
            {
                "page": "/ (Tamil)",
                "width": 390,
                "height": 844,
                "horizontal_overflow": await page.evaluate(
                    "document.documentElement.scrollWidth > innerWidth"
                ),
            }
        )
        await page.get_by_label("Interface language").select_option("en")
        video = page.video
        await context.close()
        if video:
            await video.save_as(str(ROOT / "reports/demo-walkthrough.webm"))
        await browser.close()
    result = {"viewports": checks, "javascript_errors": errors}
    (ROOT / "reports/browser_checks.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    assert not errors, errors
    assert not any(c["horizontal_overflow"] for c in checks), "Horizontal overflow detected"


if __name__ == "__main__":
    asyncio.run(main())
