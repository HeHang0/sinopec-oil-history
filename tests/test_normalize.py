import unittest

from app.normalize import normalize_row, parse_payload


class NormalizeTests(unittest.TestCase):
    def test_maps_core_products(self):
        row = normalize_row(
            {
                "queryDate": "2026-10-16",
                "GAS_92": 8.61,
                "GAS_95": 9.17,
                "GAS_98": 10.67,
                "CHECHAI_0": 8.36,
                "CHECHAI_10": 8.86,
                "CHAI_20": 9.28,
                "CHAI_35": 9.71,
            }
        )
        self.assertEqual(
            row,
            {
                "date": "2026-10-16",
                "92": 8.61,
                "95": 9.17,
                "98": 10.67,
                "0": 8.36,
                "-10": 8.86,
                "-20": 9.28,
                "-35": 9.71,
            },
        )

    def test_zero_price_is_omitted(self):
        row = normalize_row({"queryDate": "2026-10-16", "GAS_92": 8.61, "GAS_98": 0.0})
        self.assertEqual(row, {"date": "2026-10-16", "92": 8.61})

    def test_multi_zone_payload(self):
        payload = {
            "data": {
                "provinceCheck": {"PROVINCE_NAME": "云南"},
                "provinceData": [],
                "area": [
                    {
                        "areaCheck": {"AREA_NAME": "一价区"},
                        "areaData": [{"queryDate": "2026-10-16", "GAS_92": 8.6}],
                    },
                    {
                        "areaCheck": {"AREA_NAME": "二价区"},
                        "areaData": [{"queryDate": "2026-10-16", "GAS_92": 8.7}],
                    },
                ],
            }
        }
        name, rows = parse_payload(payload)
        self.assertEqual(name, "云南")
        self.assertEqual([row["zone"] for row in rows], ["一价区", "二价区"])
        self.assertEqual([row["92"] for row in rows], [8.6, 8.7])

    def test_single_zone_payload(self):
        payload = {
            "data": {
                "provinceCheck": {"PROVINCE_NAME": "上海"},
                "area": [],
                "provinceData": [{"queryDate": "2026-10-16", "GAS_92": 8.53, "GAS_95": 8.99}],
            }
        }
        name, rows = parse_payload(payload)
        self.assertEqual(name, "上海")
        self.assertEqual(rows, [{"date": "2026-10-16", "92": 8.53, "95": 8.99}])


if __name__ == "__main__":
    unittest.main()
