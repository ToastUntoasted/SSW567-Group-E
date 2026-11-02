import unittest
from unittest.mock import patch
import MRTD


# Sample passport information
SAMPLE = {
    "document_type": "P",
    "issuing_country": "USA",
    "surname": "SMITH",
    "given_names": "ANNA MARIA",
    "passport_number": "A12345678",
    "nationality": "CAN",
    "birth_date": "990101",
    "sex": "F",
    "expiration_date": "301231",
    "personal_number": "123456789",
}


class TestMRTD(unittest.TestCase):

    def setUp(self):
        self.line1, self.line2 = MRTD.encode_mrz(SAMPLE)

    # scan_mrz
    @patch("MRTD.scan_mrz")
    def test_scan_mrz_pass(self, mock_scan):
        mock_scan.return_value = (self.line1, self.line2)
        self.assertEqual(MRTD.scan_mrz(), (self.line1, self.line2))

    @patch("MRTD.scan_mrz")
    def test_scan_mrz_fail(self, mock_scan):
        mock_scan.side_effect = OSError("Scanner not connected")
        with self.assertRaises(OSError):
            MRTD.scan_mrz()

    # get_passport_from_database
    @patch("MRTD.get_passport_from_database")
    def test_database_pass(self, mock_db):
        mock_db.return_value = SAMPLE
        self.assertEqual(MRTD.get_passport_from_database("A12345678"), SAMPLE)

    @patch("MRTD.get_passport_from_database")
    def test_database_fail(self, mock_db):
        mock_db.return_value = None
        self.assertIsNone(MRTD.get_passport_from_database("UNKNOWN"))

    # fletcher16
    def test_fletcher16_pass(self):
        self.assertEqual(MRTD.fletcher16("abc"), 0x4C27)

    def test_fletcher16_fail(self):
        with self.assertRaises(TypeError):
            MRTD.fletcher16(123)

    # check_digit
    def test_check_digit_pass(self):
        self.assertEqual(MRTD.check_digit("abc"), "5")

    def test_check_digit_fail(self):
        with self.assertRaises(ValueError):
            MRTD.check_digit("é")

    # encode_mrz
    def test_encode_mrz_pass(self):
        self.assertEqual((len(self.line1), len(self.line2)), (44, 44))
        self.assertTrue(self.line1.startswith("P<USASMITH<<ANNA<MARIA"))

    def test_encode_mrz_fail(self):
        with self.assertRaises(ValueError):
            MRTD.encode_mrz(dict(SAMPLE, sex="X"))

    # decode_mrz
    def test_decode_mrz_pass(self):
        data = MRTD.decode_mrz(self.line1, self.line2)
        self.assertEqual(data["surname"], "SMITH")
        self.assertEqual(data["given_names"], "ANNA MARIA")
        self.assertEqual(data["passport_number"], "A12345678")

    def test_decode_mrz_fail(self):
        with self.assertRaises(ValueError):
            MRTD.decode_mrz("SHORT", self.line2)

    # validate_mrz
    def test_validate_mrz_pass(self):
        result = MRTD.validate_mrz(self.line1, self.line2)
        self.assertTrue(result["valid"])
        self.assertEqual(result["mismatches"], [])

    def test_validate_mrz_fail(self):
        chars = list(self.line2)
        chars[9] = "0" if chars[9] != "0" else "1"
        result = MRTD.validate_mrz(self.line1, "".join(chars))
        self.assertFalse(result["valid"])
        self.assertEqual(result["mismatches"][0]["field"], "passport_number")


    # ADDITIONAL TEST 1:
    def test_additional_fletcher_empty(self):
        self.assertEqual(MRTD.fletcher16(""), 0)
        self.assertEqual(MRTD.check_digit(""), "0")

    # ADDITIONAL TEST 2:
    def test_additional_invalid_calendar_dates(self):
        for date in ("010229", "991332", "301300", "300000"):
            with self.assertRaises(ValueError):
                MRTD.encode_mrz(
                    dict(SAMPLE, expiration_date=date)
                )

    # ADDITIONAL TEST 3:
    def test_additional_valid_leap_day(self):
        first, second = MRTD.encode_mrz(
            dict(SAMPLE, birth_date="000229")
        )

        result = MRTD.decode_mrz(first, second)
        self.assertEqual(result["birth_date"], "000229")

    # ADDITIONAL TEST 4:
    def test_additional_country_format(self):
        for code in ("US", "US1", "usa", "USAA", None):
            with self.assertRaises(ValueError):
                MRTD.encode_mrz(
                    dict(SAMPLE, nationality=code)
                )

    # ADDITIONAL TEST 5:
    def test_additional_invalid_names(self):
        for surname in ("", " ", "SM1TH", "A" * 40, None):
            with self.assertRaises((ValueError, TypeError)):
                MRTD.encode_mrz(
                    dict(SAMPLE, surname=surname)
                )

    # ADDITIONAL TEST 6:
    def test_additional_personal_number_boundaries(self):
        for value in ("", "A" * 15):
            first, second = MRTD.encode_mrz(
                dict(SAMPLE, personal_number=value)
            )

            decoded = MRTD.decode_mrz(first, second)

            self.assertEqual(
                decoded["personal_number"], value
            )
            self.assertTrue(
                MRTD.validate_mrz(first, second)["valid"]
            )

        with self.assertRaises(ValueError):
            MRTD.encode_mrz(
                dict(SAMPLE, personal_number="A" * 16)
            )

    # ADDITIONAL TEST 7:
    def test_additional_encoded_positions(self):
        self.assertEqual(self.line2[:9], "A12345678")
        self.assertEqual(self.line2[10:13], "CAN")
        self.assertEqual(self.line2[13:19], "990101")
        self.assertEqual(self.line2[20], "F")
        self.assertEqual(self.line2[21:27], "301231")
        self.assertEqual(
            self.line2[28:43], "123456789<<<<<<"
        )

        checks = (
            (self.line2[:9], 9),
            ("990101", 19),
            ("301231", 27),
            (self.line2[28:43], 43)
        )

        for content, position in checks:
            self.assertEqual(
                self.line2[position],
                MRTD.check_digit(content)
            )

    # ADDITIONAL TEST 8:
    def test_additional_every_mismatch_detail(self):
        positions = (
            (9, "passport_number"),
            (19, "birth_date"),
            (27, "expiration_date"),
            (43, "personal_number")
        )

        for pos, name in positions:
            changed = list(self.line2)

            changed[pos] = (
                "0" if changed[pos] != "0" else "1"
            )

            result = MRTD.validate_mrz(
                self.line1, "".join(changed)
            )

            self.assertEqual(
                result["message"],
                "Check-digit mismatches found"
            )

            self.assertEqual(
                result["mismatches"],
                [{
                    "field": name,
                    "expected": self.line2[pos],
                    "actual": changed[pos]
                }]
            )

    # ADDITIONAL TEST 9:
    def test_additional_multiple_mismatches(self):
        changed = list(self.line2)

        for pos in (19, 43):
            changed[pos] = (
                "0" if changed[pos] != "0" else "1"
            )

        result = MRTD.validate_mrz(
            self.line1, "".join(changed)
        )

        self.assertFalse(result["valid"])

        self.assertEqual(
            [x["field"] for x in result["mismatches"]],
            ["birth_date", "personal_number"]
        )

    # ADDITIONAL TEST 10:
    def test_additional_valid_message(self):
        result = MRTD.validate_mrz(
            self.line1, self.line2
        )

        self.assertIs(result["valid"], True)

        self.assertEqual(
            result["message"],
            "All check digits match"
        )

    # ADDITIONAL TEST 11:
    def test_additional_invalid_decoded_lines(self):
        cases = [
            (
                self.line1,
                self.line2[:9] + "<" + self.line2[10:]
            ),
            (
                self.line1,
                self.line2[:20] + "X" + self.line2[21:]
            ),
            (
                self.line1.replace("P<", "V<", 1),
                self.line2
            ),
            (
                self.line1,
                self.line2 + "<"
            )
        ]

        for first, second in cases:
            with self.assertRaises(ValueError):
                MRTD.decode_mrz(first, second)

    # ADDITIONAL TEST 12:
    def test_additional_invalid_input_types(self):
        with self.assertRaises(TypeError):
            MRTD.encode_mrz(None)

        with self.assertRaises(TypeError):
            MRTD.decode_mrz(None, self.line2)

        with self.assertRaises(ValueError):
            MRTD.encode_mrz(
                dict(SAMPLE, document_type="V")
            )

        with self.assertRaises(ValueError):
            MRTD.encode_mrz(
                dict(SAMPLE, passport_number="1234567890")
            )

if __name__ == "__main__":
    unittest.main()
