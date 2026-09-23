import unittest

from partner_validation import PartnerValidationError, validate_partner


VALID_PARTNER = {
    "company_name": "Партнер",
    "partner_type": "ООО",
    "inn": "1234567890",
    "rating": "4",
    "address": "Москва",
    "director_name": "Иванов И.И.",
    "phone": "+7 999 100-20-30",
    "email": "partner@example.ru",
}


class PartnerValidationTests(unittest.TestCase):
    def test_valid_partner_is_normalized(self) -> None:
        result = validate_partner(VALID_PARTNER)
        self.assertEqual(result["rating"], 4)

    def test_required_fields_and_rating(self) -> None:
        for field, value in (
            ("company_name", ""),
            ("email", ""),
            ("email", "wrong"),
            ("inn", ""),
            ("partner_type", "Другое"),
            ("rating", "1.5"),
            ("rating", "-1"),
        ):
            with self.subTest(field=field, value=value):
                data = dict(VALID_PARTNER)
                data[field] = value
                with self.assertRaises(PartnerValidationError):
                    validate_partner(data)


if __name__ == "__main__":
    unittest.main()
