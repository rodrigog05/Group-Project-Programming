"""Play the built game in a fresh Chromium profile. Run against a local HTTP server."""

import argparse
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

KEY = "foundry-town.progress.v1"


class Player:
    def __init__(self, page, url):
        self.page = page
        self.url = url
        page.add_init_script("""
            let fixture = sessionStorage.getItem('foundry-test-fixture');
            if (fixture) {
                localStorage.setItem('foundry-town.progress.v1', fixture);
                sessionStorage.removeItem('foundry-test-fixture');
            }
        """)

    def boot(self):
        self.page.goto(self.url, wait_until="domcontentloaded")
        self.page.locator("#canvas").wait_for(state="attached")
        for _ in range(90):
            self.page.mouse.click(4, 4)
            if self.options()[0] == "Welcome":
                break
            self.page.wait_for_timeout(500)
        else:
            raise AssertionError("The Pygbag start menu did not appear")
        self.key("Enter")
        self.page.wait_for_function(
            "document.querySelector('#canvas').getAttribute('aria-label').startsWith('Foundry Town |')"
        )

    def key(self, key):
        self.page.keyboard.press(key, delay=70)
        self.page.wait_for_timeout(110)

    def options(self):
        return (self.page.locator("#canvas").get_attribute("aria-label") or "").split(
            " | "
        )

    def choose(self, prefix):
        for _ in range(20):
            labels = self.options()[1:]
            index = next(
                (i for i, label in enumerate(labels) if label.startswith(prefix)), None
            )
            if index is not None:
                self.key("Home")
                for _ in range(index):
                    self.key("ArrowDown")
                self.key("Enter")
                return
            if "Next" not in labels:
                break
            self.key("PageDown")
        raise AssertionError(f"{prefix} missing from {self.options()}")

    def saved(self):
        return self.page.evaluate("(key) => JSON.parse(localStorage.getItem(key))", KEY)

    def state(self):
        return self.saved()["state"]

    def fixture(self, x, y, **fields):
        snapshot = self.saved()
        snapshot["state"].update(x=x, y=y, **fields)
        self.page.evaluate(
            """save => {
            save.marketStart = Date.now()/1000 - save.state.market_elapsed;
            sessionStorage.setItem('foundry-test-fixture',JSON.stringify(save));
        }""",
            snapshot,
        )
        self.boot()

    def walk_to_x(self, target):
        for _ in range(12):
            self.key(
                "Escape"
            )  # checkpoint the player's position through the normal save path
            dx = target - self.state()["x"]
            if abs(dx) < 12:
                return
            key = "ArrowRight" if dx > 0 else "ArrowLeft"
            self.page.keyboard.down(key)
            self.page.wait_for_timeout(max(50, min(2800, abs(dx) * 1000 / 260)))
            self.page.keyboard.up(key)
        raise AssertionError("Could not walk to the next entrance")


def bread_route(p):
    p.boot()
    p.key("e")
    p.key("e")
    assert p.state()["supplies"][3] == 1 and p.state()["cash"] == 56
    p.key("Escape")
    p.walk_to_x(1628)
    p.key("e")
    p.key("e")
    assert p.state()["orders"][3]["quantity"] == 1
    p.page.wait_for_timeout(4900)
    p.key("e")
    assert p.state()["goods"][3] == 1
    p.key("Escape")
    p.walk_to_x(356)
    p.key("e")
    p.key("e")
    assert p.state()["cash"] == 70 and p.state()["goods"][3] == 0
    p.boot()
    p.key("Escape")
    assert p.state()["cash"] == 70 and abs(p.state()["x"] - 356) < 15
    print("PASS farm, bakery, market and reload", flush=True)


def services(p):
    p.fixture(1076, 649, cash=5000, won=True, milestone_acknowledged=True)
    p.key("e")
    p.key("2")
    p.key("Escape")
    assert p.state()["vehicle"] == "car" and p.state()["cash"] == 4760
    p.key("b")
    p.choose("Ironworks")
    p.choose("Buy Ironworks")
    p.choose("Upgrade equipment")
    assert p.state()["businesses"]["owned"]["Ironworks"]["equipment_level"] == 1
    p.key("Escape")
    p.key("Escape")
    p.key("l")
    p.choose("Purchase Delivery van")
    p.choose("Goldenfield Farm")
    p.choose("Sunrise Bakery")
    assert p.state()["logistics"]["routes"][0]["destination"] == "Sunrise Bakery"
    p.key("Escape")
    p.key("c")
    p.choose("Accept")
    assert len(p.state()["contracts"]["active"]) == 1
    p.key("Escape")
    p.key("j")
    p.choose("Markets")
    assert any("Bread" in x for x in p.options())
    print("PASS car, ownership, upgrade, fleet, contract and journal", flush=True)
    p.fixture(596, 278)
    p.key("e")
    p.choose(p.options()[1])
    p.choose("Buy 1")
    assert sum(p.state()["exchange"]["holdings"].values()) == 1
    p.choose("Sell 1")
    assert sum(p.state()["exchange"]["holdings"].values()) == 0
    p.fixture(116, 648)
    p.key("e")
    p.choose("Research Advanced Metallurgy")
    assert p.state()["innovation"]["project"]["branch"] == "metallurgy"
    p.fixture(1092, 460)
    p.key("e")
    p.key("r")
    p.page.wait_for_timeout(5100)
    p.key("Escape")
    assert "Roulette:" in p.state()["message"]
    p.fixture(660, 702, vehicle=None)
    p.key("e")
    p.choose("Cross to")
    p.page.wait_for_timeout(5000)
    p.key("Escape")
    assert p.state()["y"] > 1050
    print("PASS exchange, research, roulette and ferry", flush=True)
    p.key("F1")
    assert any(s.startswith("Music") and s.endswith("on") for s in p.options())
    p.choose("Music")
    assert any(s.startswith("Music") and s.endswith("off") for s in p.options())
    p.choose("Character and appearance")
    p.choose("Costume")
    p.choose("Play as")
    assert p.state()["profile"]["costume"] != "Builder"
    print("PASS soundtrack control and character save", flush=True)


def late_game(p):
    # Use a paid research project just before completion, then play fabrication in real time.
    tech = p.state()["innovation"]
    if not tech["levels"]["metallurgy"]:
        tech["project"].update(remaining=0.3)
    p.fixture(116, 648, innovation=tech, supplies=[2, 0, 0, 0], goods=[1, 0, 0, 0])
    p.page.wait_for_timeout(600)
    p.key("e")
    p.choose("Craft Alloy Components")
    assert p.state()["innovation"]["orders"]["alloy_components"]["quantity"] == 1
    p.page.wait_for_timeout(14700)
    p.choose("Collect Alloy Components")
    assert p.state()["innovation"]["goods"]["alloy_components"] == 1
    p.choose("Sell Alloy Components")
    assert p.state()["innovation"]["total_sold"]["alloy_components"] == 1
    # A project with all but one pastry already delivered (multi-trip desktop contract).
    projects = p.state()["contracts"]
    order = projects["active"][0]
    assert order["key"] == "festival_project"
    order["delivered"] = order["required"] - 1
    goods = p.state()["industry_goods"]
    goods["PASTELARIA"] = 1
    p.fixture(596, 650, contracts=projects, industry_goods=goods)
    p.key("c")
    p.choose("Deliver Pastéis")
    assert "festival_project" in p.state()["contracts"]["completed_projects"]
    print("PASS advanced manufacturing, sale and permanent contract reward", flush=True)
    p.fixture(1076, 278)
    p.key("e")
    p.choose("Add 12 slots")
    assert p.state()["warehouse_level"] == 1
    p.fixture(
        356, 649, cash=495, goods=[0, 0, 0, 1], won=False, milestone_acknowledged=False
    )
    p.key("e")
    p.key("e")
    assert p.options()[0] == "Cash milestone"
    p.choose("You reached")
    assert p.state()["milestone_acknowledged"]
    print("PASS warehouse and victory continuation", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--chromium", help="Path to an installed Chromium executable")
    args = parser.parse_args()
    if urlsplit(args.url).hostname not in ("127.0.0.1", "localhost", "::1"):
        parser.error("Serve the test build on localhost")
    with sync_playwright() as engine:
        browser = engine.chromium.launch(executable_path=args.chromium)
        p = Player(browser.new_page(), args.url)
        bread_route(p)
        services(p)
        late_game(p)


if __name__ == "__main__":
    main()
