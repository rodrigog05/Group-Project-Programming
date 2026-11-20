"""Run with Playwright against a locally served Pages artifact in a fresh Chromium profile."""

import argparse
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

KEY = "foundry-town.core.v1"


def exercise(page, url):
    page.add_init_script("""const f = sessionStorage.getItem('next-core-test');
        if (f) { localStorage.setItem('foundry-town.core.v1', f); sessionStorage.removeItem('next-core-test'); }""")

    def tap(key):
        page.keyboard.press(key, delay=65)
        page.wait_for_timeout(120)

    def boot():
        page.goto(url, wait_until="domcontentloaded")
        for _ in range(90):
            page.wait_for_timeout(500)
            page.mouse.click(5, 5)
            if page.locator("#infobox").evaluate("e=>e.style.display==='none'"):
                break
        else:
            raise AssertionError("Pygbag loader timed out")
        page.wait_for_timeout(600)
        tap("Escape")
        page.wait_for_function("(k)=>!!localStorage.getItem(k)", arg=KEY)

    def snapshot():
        return page.evaluate("k=>JSON.parse(localStorage.getItem(k))", KEY)

    def state():
        return snapshot()["town"]

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

    boot()
    assert state()["cash"] == 60
    # Whole bread route on foot; use the guide and interact through actual key events.
    tap("p")
    tap("4")
    tap("a")
    tap("e")
    tap("q")
    assert state()["cash"] == 44 and state()["materials"][3] == 4
    tap("Escape")
    walk(1628, "x")
    tap("e")
    tap("e")
    assert state()["orders"][3]["quantity"] == 4
    boot()
    assert state()["orders"][3]["quantity"] == 4
    page.wait_for_timeout(4300)
    tap("e")
    tap("e")
    assert state()["goods"][3] == 4
    tap("Escape")
    walk(356, "x")
    tap("e")
    tap("e")
    assert state()["cash"] == 100 and state()["goods"][3] == 0
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
