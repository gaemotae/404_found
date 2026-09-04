from django.test import SimpleTestCase

from .services import uvi_level


class UviLevelTests(SimpleTestCase):
    def test_uvi_boundaries(self):
        cases = {
            None: "Unknown",
            2: "Low",
            3: "Moderate",
            6: "High",
            8: "Very High",
            11: "Extreme",
        }

        for uvi, expected in cases.items():
            with self.subTest(uvi=uvi):
                self.assertEqual(uvi_level(uvi), expected)
