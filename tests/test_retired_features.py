"""Retired trade pop-ups must not suppress collection or other notices."""
import pytest

from browser_game import OPEN_SITES, entrance
from tycoon import Town, TRADES


@pytest.mark.parametrize("trade",range(len(TRADES)))
def test_buy_and_sell_keep_other_notices_and_collection_still_congratulates(trade):
    town=Town()
    town.notice="Keep this other notice"
    town.notice_until=42
    supplier=next(s for s in OPEN_SITES if s.role=="SUPPLIER" and s.trade==trade)
    town.x,town.y=entrance(supplier)
    town.interact()
    assert town.supplies[trade]==1
    assert (town.notice,town.notice_until)==("Keep this other notice",42)
    assert "Bought 1" in town.message

    factory=next(s for s in OPEN_SITES if s.role=="FACTORY" and s.trade==trade)
    town.x,town.y=entrance(factory)
    town.interact()
    town.advance(TRADES[trade].seconds)
    town.interact()
    assert town.goods[trade]==1
    assert "Congratulations Player, you just collected 1" in town.notice
    previous_notice=town.notice,town.notice_until

    shop=next(s for s in OPEN_SITES if s.role=="PUBLIC SHOP" and s.trade==trade)
    town.x,town.y=entrance(shop)
    town.interact()
    assert town.goods[trade]==0
    assert "Sold 1" in town.message
    assert (town.notice,town.notice_until)==previous_notice


def test_machinery_sale_keeps_the_collection_notice():
    town=Town()
    town.goods[0]=town.goods[1]=1
    workshop=next(s for s in OPEN_SITES if s.role=="TIER2")
    town.x,town.y=entrance(workshop)
    town.interact()
    town.advance(12)
    town.interact()
    previous_notice=town.notice,town.notice_until
    assert "collected 1 precision machinery" in town.notice
    town.interact()
    assert town.tier2_goods==0
    assert "Sold 1" in town.message
    assert (town.notice,town.notice_until)==previous_notice
