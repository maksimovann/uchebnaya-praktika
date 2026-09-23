import re


PARTNER_TYPES = ("ООО", "ИП", "ЗАО", "АО", "ПАО", "ТК")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class PartnerValidationError(ValueError):
    pass


def validate_partner(data: dict) -> dict:
    company_name = str(data.get("company_name", "")).strip()
    email = str(data.get("email", "")).strip()
    partner_type = str(data.get("partner_type", "")).strip()
    inn = str(data.get("inn", "")).strip()
    if not company_name:
        raise PartnerValidationError(
            "Укажите наименование партнера и повторите сохранение."
        )
    if not email:
        raise PartnerValidationError(
            "Укажите email компании и повторите сохранение."
        )
    if not EMAIL_PATTERN.fullmatch(email):
        raise PartnerValidationError(
            "Email должен иметь формат name@example.ru. Исправьте адрес и повторите сохранение."
        )
    if partner_type not in PARTNER_TYPES:
        raise PartnerValidationError(
            "Выберите тип партнера из выпадающего списка."
        )
    if not inn:
        raise PartnerValidationError(
            "Укажите ИНН партнера. Он необходим для сохранения записи в базе."
        )
    try:
        rating = int(data.get("rating", ""))
    except (TypeError, ValueError) as error:
        raise PartnerValidationError(
            "Рейтинг должен быть целым числом от 0. Удалите буквы и знаки препинания."
        ) from error
    if rating < 0:
        raise PartnerValidationError(
            "Рейтинг не может быть отрицательным. Укажите целое число от 0."
        )
    return {
        "company_name": company_name,
        "partner_type": partner_type,
        "inn": inn,
        "rating": rating,
        "address": str(data.get("address", "")).strip(),
        "director_name": str(data.get("director_name", "")).strip(),
        "phone": str(data.get("phone", "")).strip(),
        "email": email,
    }
