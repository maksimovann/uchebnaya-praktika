import unittest

from discount import calculate_partner_discount


class DiscountTests(unittest.TestCase):
    def test_thresholds(self) -> None:
        cases = {
            0: 0,
            9_999: 0,
            10_000: 5,
            49_999: 5,
            50_000: 10,
            299_999: 10,
            300_000: 15,
        }
        for quantity, expected in cases.items():
            with self.subTest(quantity=quantity):
                self.assertEqual(calculate_partner_discount(quantity), expected)

    def test_negative_quantity_is_invalid(self) -> None:
        with self.assertRaises(ValueError):
            calculate_partner_discount(-1)


if __name__ == "__main__":
    unittest.main()
