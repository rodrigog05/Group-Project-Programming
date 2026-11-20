"""Run with Playwright against a locally served Pages artifact in a fresh Chromium profile."""

import argparse
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

KEY = "foundry-town.core.v1"


def exercise(page, url):
    page.add_init_script("""if (window === window.top && location.protocol.startsWith('http')) {
        const f = sessionStorage.getItem('next-core-test');
        if (f) { localStorage.setItem('foundry-town.core.v1', f); sessionStorage.removeItem('next-core-test'); } }""")

    def tap(key):
        page.keyboard.press(key, delay=65)
        page.wait_for_timeout(120)

    def boot(*, start=True):
        page.goto(url, wait_until="domcontentloaded")
        splash = page.locator("#core-splash")
        assert splash.get_by_role("status").text_content() == "Loading Core Edition…"
        splash.wait_for(state="hidden", timeout=45000)
        page.locator("#infobox").wait_for(state="hidden")
        if start:
            tap("c" if snapshot() is not None else "n")
            page.wait_for_function("(k)=>!!localStorage.getItem(k)", arg=KEY)

    def snapshot():
        return page.evaluate("k=>JSON.parse(localStorage.getItem(k))", KEY)

    def state():
        return snapshot()["town"]

    canvas = page.locator("#canvas")
    fullscreen = page.locator("#core-fullscreen")

    def check_canvas():
        bounds = canvas.bounding_box()
        assert bounds is not None
        assert abs(bounds["width"] / bounds["height"] - 800 / 540) < 0.005, bounds
        assert canvas.evaluate("c => c.width === 800 && c.height === 540")
        viewport = page.evaluate("() => [innerWidth, innerHeight]")
        toolbar = 44 if viewport[0] / viewport[1] <= 7 / 4 else 0
        expected = min(viewport[0], (viewport[1] - toolbar) * 800 / 540)
        assert abs(bounds["width"] - expected) < 2, (bounds, viewport)
        return bounds

    def click_game(x, y):
        bounds = check_canvas()
        page.mouse.click(
            bounds["x"] + bounds["width"] * x / 800,
            bounds["y"] + bounds["height"] * y / 540,
        )
        page.wait_for_timeout(120)

    def arrive(x, y):
        data = snapshot()
        data["town"].update(x=x, y=y)
        page.evaluate(
            "s=>sessionStorage.setItem('next-core-test',JSON.stringify(s))", data
        )
        boot()
        assert state()["x"] == x and state()["y"] == y

    def walk(target, axis):
        for _ in range(12):
            pos = state()[axis]
            if abs(target - pos) < 9:
                return
            sign = target > pos
            key = (
                ("ArrowRight" if sign else "ArrowLeft")
                if axis == "x"
                else ("ArrowDown" if sign else "ArrowUp")
            )
            page.keyboard.down(key)
            page.wait_for_timeout(max(48, min(2400, abs(target - pos) * 1000 / 232)))
            page.keyboard.up(key)
            page.wait_for_timeout(150)
        raise AssertionError((target, axis, state()))

    page.set_viewport_size({"width": 1366, "height": 768})
    boot(start=False)
    print("PASS branded splash hands off without a startup click", flush=True)
    tap("c")
    assert snapshot() is None
    click_game(500, 459)
    tap("n")
    assert snapshot() is None
    click_game(224, 491)
    page.set_viewport_size({"width": 1920, "height": 1080})
    fullscreen.click()
    page.wait_for_function("document.fullscreenElement === document.documentElement")
    expect(fullscreen).to_have_text("Exit Fullscreen")
    click_game(500, 367)
    assert state()["cash"] == 60
    fullscreen.click()
    page.wait_for_function("!document.fullscreenElement")
    expect(fullscreen).to_have_text("Fullscreen")
    page.set_viewport_size({"width": 720, "height": 500})
    click_game(145, 500)
    click_game(90, 500)
    assert state()["cash"] == 56 and state()["materials"][3] == 1
    assert check_canvas()["width"] > 600
    click_game(700, 500)
    boot(start=False)
    click_game(500, 413)
    assert state()["cash"] == 56
    page.set_viewport_size({"width": 1366, "height": 768})
    check_canvas()
    print("PASS 1366x768, 1920x1080, 720x500, fullscreen toggle, mouse and saved game", flush=True)
    # Whole bread route on foot; use the guide and interact through actual key events.
    tap("p")
    tap("4")
    tap("a")
    tap("e")
    tap("q")
    assert state()["cash"] == 40 and state()["materials"][3] == 5
    tap("Escape")
    walk(1628, "x")
    tap("e")
    tap("e")
    assert state()["orders"][3]["quantity"] == 5
    boot()
    assert state()["orders"][3]["quantity"] == 5
    page.wait_for_timeout(4300)
    tap("e")
    tap("e")
    assert state()["goods"][3] == 5
    tap("Escape")
    walk(356, "x")
    tap("e")
    tap("e")
    assert state()["cash"] == 110 and state()["goods"][3] == 0
    print(
        "PASS bread route on foot, bulk purchase, reload during production and sale",
        flush=True,
    )
    # Use only position fixtures for the other long walks; all transactions use the game UI.
    for i, src, work, market, cost, price, seconds in (
        (0, (1098, 1235), (356, 465), (596, 465), 5, 18, 5),
        (1, (1368, 280), (356, 280), (1628, 465), 7, 26, 7),
        (2, (2168, 280), (836, 465), (836, 650), 6, 22, 6),
    ):
        before = state()["cash"]
        arrive(*src)
        tap("e")
        tap("e")
        assert state()["materials"][i] == 1
        arrive(*work)
        tap("e")
        tap("e")
        page.wait_for_timeout(1000 * seconds + 400)
        tap("e")
        assert state()["goods"][i] == 1
        arrive(*market)
        tap("e")
        tap("e")
        assert state()["cash"] == before - cost + price and state()["goods"][i] == 0
        print("PASS route", i, flush=True)
    arrive(300, 700)
    walk(1100, "y")
    assert state()["y"] >= 1090
    arrive(1076, 280)
    before = state()["cash"]
    tap("e")
    tap("e")
    tap("e")
    assert state()["cash"] == before - 100 and state()["upgraded"]
    boot()
    assert state()["upgraded"] and state()["cash"] == before - 100
    print("PASS west bridge, one-time upgrade and persisted balance", flush=True)
    boot(start=False)
    original = snapshot()
    tap("n")
    assert snapshot() == original
    tap("Escape")
    tap("c")
    assert state()["upgraded"]
    boot(start=False)
    tap("n")
    assert snapshot() == original
    tap("y")
    assert state()["cash"] == 60 and not state()["upgraded"]
    print("PASS rules, disabled Continue, cancel, Continue, and confirmed replacement", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--chromium")
    args = parser.parse_args()
    if urlsplit(args.url).hostname not in ("localhost", "127.0.0.1", "::1"):
        parser.error("Use a locally served build")
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium)
        exercise(browser.new_page(), args.url)
