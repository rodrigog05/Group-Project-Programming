import unittest

from tycoon import ROULETTE_PAYOUTS, ROULETTE_POCKETS, SITES, Town, pack_save, roulette_color, unpack_save


class RouletteWheelTest(unittest.TestCase):
    def test_wheel_has_every_number_once(self):
        self.assertEqual(sorted(ROULETTE_POCKETS), list(range(37)))

    def test_wheel_has_eighteen_red_eighteen_black_and_one_green(self):
        colors = [roulette_color(number) for number in ROULETTE_POCKETS]
        self.assertEqual((colors.count("red"), colors.count("black"), colors.count("green")), (18, 18, 1))

    def test_colors_alternate_around_the_wheel(self):
        # On a real European wheel, red and black alternate on both sides of the green 0.
        colors = [roulette_color(number) for number in ROULETTE_POCKETS[1:]]
        for previous, current in zip(colors, colors[1:]):
            self.assertNotEqual(previous, current)

    def test_house_keeps_an_edge(self):
        chances = {"red": 18 / 37, "black": 18 / 37, "green": 1 / 37}
        for choice, chance in chances.items():
            self.assertLess(chance * ROULETTE_PAYOUTS[choice], 1)


class RouletteBetTest(unittest.TestCase):
    def test_winning_red_bet_doubles_the_stake(self):
        town = Town()
        self.assertEqual(town.bet_roulette("red", 10, 32), 20)
        self.assertEqual(town.cash, 50)

    def test_losing_bet_keeps_the_stake(self):
        town = Town()
        self.assertEqual(town.bet_roulette("black", 25, 32), 0)
        self.assertEqual(town.cash, 35)

    def test_zero_loses_red_and_black_and_pays_green(self):
        town = Town()
        self.assertEqual(town.bet_roulette("red", 5, 0), 0)
        self.assertEqual(town.bet_roulette("black", 5, 0), 0)
        self.assertEqual(town.bet_roulette("green", 5, 0), 180)

    def test_cannot_bet_more_than_your_cash(self):
        town = Town()
        self.assertIsNone(town.bet_roulette("red", 100, 32))
        self.assertEqual(town.cash, 60)

    def test_unknown_bet_is_rejected(self):
        with self.assertRaises(ValueError):
            Town().bet_roulette("blue", 5, 1)

    def test_casino_is_not_a_trade_stop(self):
        town = Town()
        casino = next(site for site in SITES if site.role == "CASINO")
        town.x, town.y = casino.door[0], casino.door[1] + 10
        self.assertIs(town.nearby(), casino)
        town.interact()
        self.assertEqual((town.cash, town.supplies, town.goods), (60, [0] * 4, [0] * 4))

    def test_saves_still_round_trip(self):
        town = Town()
        town.bet_roulette("red", 10, 1)
        restored, _ = unpack_save(pack_save(town, 1000))
        self.assertEqual(restored.cash, 50)


if __name__ == "__main__":
    unittest.main()
