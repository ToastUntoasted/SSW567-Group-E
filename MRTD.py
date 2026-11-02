
"""
Group E: Passport MRZ processing using Fletcher-16.

Project convention:
The fourth check digit, at position 44 of line 2,
checks the 15-character personal-number field.
"""

from datetime import datetime

ALLOWED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<")


# REQUIREMENT 1: Scanner placeholder
def scan_mrz():
    """
    Scanner hardware interface, mocked during testing.
    """
    pass


# REQUIREMENT 3: Database placeholder
def get_passport_from_database(passport_id):
    """
    Database interface, mocked during testing.
    """
    pass


# GROUP E: FLETCHER-16
def fletcher16(value):
    """
    Calculate Fletcher-16 on ASCII bytes.
    """
    if not isinstance(value, str):
        raise TypeError("Fletcher-16 input must be text")

    try:
        data = value.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError("Fletcher-16 requires ASCII input")

    a = 0
    b = 0

    for byte in data:
        a = (a + byte) % 255
        b = (b + a) % 255

    return (b << 8) | a


def check_digit(value):
    """
    Return the Fletcher-16 checksum modulo 10.
    """
    return str(fletcher16(value) % 10)


# HELPER: Country-code format
def _country(value):
    """
    Check uppercase three-letter country-code format.
    """
    if (
        not isinstance(value, str)
        or len(value) != 3
        or any(
            c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            for c in value
        )
    ):
        raise ValueError(
            "Country/organization code must be 3 uppercase letters"
        )

    return value


# HELPER: Date validation
def _date(value):
    """
    Validate a YYMMDD date.
    """
    if (
        not isinstance(value, str)
        or len(value) != 6
        or not value.isdigit()
    ):
        raise ValueError("Date must be six digits (YYMMDD)")

    try:
        datetime(
            2000 + int(value[:2]),
            int(value[2:4]),
            int(value[4:6])
        )
    except ValueError:
        raise ValueError("Invalid YYMMDD calendar date")

    return value


# HELPER: Fixed-length fields
def _fixed_field(value, width, name, optional=False):
    if not isinstance(value, str):
        raise TypeError(name + " must be a string")

    value = value.upper()

    if (
        len(value) > width
        or (not optional and not value)
        or any(c not in ALLOWED for c in value)
    ):
        raise ValueError("Invalid " + name)

    return value.ljust(width, "<")


# HELPER: Passport names
def _name_part(value, name):
    if not isinstance(value, str):
        raise TypeError(name + " must be a string")

    text = value.strip().upper().replace(" ", "<")

    if (
        not text
        or any(
            c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ<"
            for c in text
        )
    ):
        raise ValueError("Invalid " + name)

    return text


# HELPER: Validate MRZ format
def _validate_lines(line1, line2):
    if (
        not isinstance(line1, str)
        or not isinstance(line2, str)
    ):
        raise TypeError("MRZ lines must be strings")

    if len(line1) != 44 or len(line2) != 44:
        raise ValueError(
            "Each MRZ line must contain 44 characters"
        )

    if any(c not in ALLOWED for c in line1 + line2):
        raise ValueError("MRZ contains invalid characters")

    if line1[:2] != "P<":
        raise ValueError("Unsupported passport document type")

    _country(line1[2:5])
    _country(line2[10:13])

    if "<<" not in line1[5:]:
        raise ValueError("MRZ name separator is missing")

    if not line1[5:].split("<<", 1)[0].strip("<"):
        raise ValueError("MRZ surname is missing")

    _date(line2[13:19])
    _date(line2[21:27])

    if line2[20] not in ("M", "F", "<"):
        raise ValueError("Invalid sex marker")

    for pos in (9, 19, 27, 43):
        if not line2[pos].isdigit():
            raise ValueError(
                "Check digits must be decimal digits"
            )


# REQUIREMENT 2: DECODE MRZ
def decode_mrz(line1, line2):
    """
    Extract passport fields from two 44-character MRZ lines.
    """
    _validate_lines(line1, line2)

    surname, given = line1[5:].split("<<", 1)

    return {
        "document_type": line1[0],
        "issuing_country": line1[2:5],
        "surname": surname.replace("<", " ").strip(),
        "given_names": given.replace("<", " ").strip(),
        "passport_number": line2[0:9].rstrip("<"),
        "passport_check_digit": line2[9],
        "nationality": line2[10:13],
        "birth_date": line2[13:19],
        "birth_check_digit": line2[19],
        "sex": line2[20],
        "expiration_date": line2[21:27],
        "expiration_check_digit": line2[27],
        "personal_number": line2[28:43].rstrip("<"),
        "personal_check_digit": line2[43],
    }


# REQUIREMENT 3: ENCODE MRZ
def encode_mrz(data):
    """
    Convert passport information into two MRZ strings.
    """
    if not isinstance(data, dict):
        raise TypeError(
            "Passport record must be a dictionary"
        )

    required = (
        "document_type",
        "issuing_country",
        "surname",
        "given_names",
        "passport_number",
        "nationality",
        "birth_date",
        "sex",
        "expiration_date",
        "personal_number",
    )

    for key in required:
        if key not in data:
            raise ValueError("Missing field: " + key)

    if data["document_type"] != "P":
        raise ValueError(
            "Only passport type P is supported"
        )

    issuing = _country(data["issuing_country"])
    nationality = _country(data["nationality"])

    surname = _name_part(
        data["surname"], "surname"
    )
    given_names = _name_part(
        data["given_names"], "given names"
    )

    name = _fixed_field(
        surname + "<<" + given_names,
        39,
        "name"
    )

    passport = _fixed_field(
        data["passport_number"],
        9,
        "passport number"
    )

    personal = _fixed_field(
        data["personal_number"],
        15,
        "personal number",
        optional=True
    )

    birth = _date(data["birth_date"])
    expiration = _date(data["expiration_date"])

    sex = data["sex"]

    if sex not in ("M", "F", "<"):
        raise ValueError("Sex must be M, F or <")

    line1 = "P<" + issuing + name

    line2 = (
        passport
        + check_digit(passport)
        + nationality
        + birth
        + check_digit(birth)
        + sex
        + expiration
        + check_digit(expiration)
        + personal
        + check_digit(personal)
    )

    return line1, line2


# REQUIREMENT 4: VALIDATE CHECK DIGITS
def validate_mrz(line1, line2):
    """
    Check all four digits and report any mismatches.
    """
    _validate_lines(line1, line2)

    checks = (
        ("passport_number", line2[0:9], line2[9]),
        ("birth_date", line2[13:19], line2[19]),
        ("expiration_date", line2[21:27], line2[27]),
        ("personal_number", line2[28:43], line2[43]),
    )

    mismatches = []

    for name, field, actual in checks:
        expected = check_digit(field)

        if expected != actual:
            mismatches.append({
                "field": name,
                "expected": expected,
                "actual": actual
            })

    return {
        "valid": not mismatches,
        "message": (
            "All check digits match"
            if not mismatches
            else "Check-digit mismatches found"
        ),
        "mismatches": mismatches,
    }
