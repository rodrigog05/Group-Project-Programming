"""Level ordering, cash thresholds, and saved notification progress."""
import unittest

from tycoon import SITES, Town, pack_save, unpack_save


class LevelTest(unittest.TestCase):
    def sell_first_product(self, town):
        site = next(site for site in SITES if site.role == 'PUBLIC SHOP' and site.trade == 0)
        town.x, town.y = site.door[0], site.door[1] + 10
        town.goods[0] = 1
        town.interact()

    def test_three_levels_and_reload_do_not_repeat_acknowledged_messages(self):
        town = Town()
        self.assertIsNone(town.pending_level)
        self.assertEqual(town.level_progress()[1], 0)
        self.sell_first_product(town)
        self.assertEqual(town.pending_level, 1)
        town.acknowledge_level()
        town.add_cash(499 - town.cash)
        self.assertIsNone(town.pending_level)
        town.add_cash(1)
        self.assertEqual(town.pending_level, 2)
        town.acknowledge_level()
        self.assertTrue(town.milestone_acknowledged)
        self.assertEqual(town.level_progress()[1], .25)
        town.add_cash(1499)
        self.assertIsNone(town.pending_level)
        town.add_cash(1)
        self.assertEqual(town.pending_level, 3)
        town.cash = 100
        restored, _ = unpack_save(pack_save(town, 1000))
        self.assertEqual(restored.pending_level, 3)
        restored.acknowledge_level()
        restored, _ = unpack_save(pack_save(restored, 1000))
        self.assertIsNone(restored.pending_level)
        self.assertEqual(restored.level_progress(), ('ALL 3 LEVELS COMPLETE', 1))

    def test_large_cash_award_keeps_notifications_in_order(self):
        town = Town()
        town.add_cash(2000)
        self.assertIsNone(town.pending_level)
        self.sell_first_product(town)
        for level in (1, 2, 3):
            self.assertEqual(town.pending_level, level)
            town.acknowledge_level()
        self.assertIsNone(town.pending_level)

    def test_legacy_save_keeps_acknowledged_cash_milestone(self):
        town = Town()
        town.add_cash(500)
        town.continue_after_milestone()
        saved = pack_save(town, 1000)
        for field in ('level_notices', 'final_goal_reached'):
            saved['state'].pop(field)
        restored, _ = unpack_save(saved)
        self.assertEqual(restored.level_notices, 2)
        self.assertIsNone(restored.pending_level)


def test_browser_level_dialogs_and_progress():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file('../streamlit_app.py', default_timeout=15).run()
    app.session_state.show_menu = False
    app.session_state.show_tutorial = False
    app.session_state.town.total_sold[0] = 1
    app.run()
    for level, label in ((1, 'Continue to Level 2'), (2, 'Continue to Level 3'), (3, 'Keep playing')):
        if level > 1:
            app.session_state.town.add_cash((500 if level == 2 else 2000) - app.session_state.town.cash)
            app.run()
        assert not app.exception
        assert any(item.value == f'Level {level} complete!' for item in app.subheader)
        if level == 2:  # Dollar amounts are escaped, not shown as a maths formula
            assert any(r'reached \$500 cash' in item.value and r'\$2,000' in item.value for item in app.markdown)
        if level == 3:
            assert any(item.value == 'You successfully completed the game! Good job!' for item in app.markdown)
        next(button for button in app.button if button.label == label).click().run()
        assert not app.exception
        assert app.session_state.town.level_notices == level
    assert app.session_state.town.level_progress() == ('ALL 3 LEVELS COMPLETE', 1)
