import unittest

from recommend.recommendation import normalize_location
from upload.image import normalize_ai_result, parse_colors


class ImageHelperTests(unittest.TestCase):
    def test_parse_colors_accepts_json_and_comma_separated_values(self):
        self.assertEqual(parse_colors('["black", "white"]'), ["black", "white"])
        self.assertEqual(parse_colors("black, white"), ["black", "white"])

    def test_normalize_ai_result_maps_legacy_field_names(self):
        result = normalize_ai_result(
            {
                "clothing_big_type": "상의",
                "clothing_type": "셔츠",
                "colors": ["blue"],
                "material": "면",
            }
        )

        self.assertEqual(result["type"], "상의")
        self.assertEqual(result["category"], "셔츠")
        self.assertEqual(result["colors"], ["blue"])


class RecommendationHelperTests(unittest.TestCase):
    def test_normalize_location_trims_input(self):
        self.assertEqual(
            normalize_location("  서울특별시 종로구  "), "서울특별시 종로구"
        )
        self.assertEqual(normalize_location(""), "알 수 없는 위치")


if __name__ == "__main__":
    unittest.main()
