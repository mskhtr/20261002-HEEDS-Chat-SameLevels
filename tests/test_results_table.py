from __future__ import annotations

import unittest

from heeds.results_table import build_levels_table


class ResultsTableTests(unittest.TestCase):
    def test_same_response_name_from_two_studies_is_not_overwritten(self):
        studies = [
            {
                "id": "stress",
                "designs": [
                    {
                        "design_id": 1,
                        "inputs": {"thickness": 2.0},
                        "responses": {"mass": 10.0},
                    }
                ],
            },
            {
                "id": "crash",
                "designs": [
                    {
                        "design_id": 7,
                        "inputs": {"thickness": 2.0},
                        "responses": {"mass": 20.0},
                    }
                ],
            },
        ]

        table = build_levels_table(
            studies,
            [{"name": "thickness"}],
            [{"thickness": 2.0}],
        )

        self.assertEqual(
            table["columns"],
            ["水準", "thickness", "stress.mass", "crash.mass"],
        )
        self.assertEqual(table["rows"][0]["stress.mass"], 10.0)
        self.assertEqual(table["rows"][0]["crash.mass"], 20.0)

    def test_response_name_that_matches_input_is_namespaced(self):
        studies = [
            {
                "id": "stress",
                "designs": [
                    {
                        "design_id": 1,
                        "inputs": {"thickness": 2.0},
                        "responses": {"thickness": 99.0},
                    }
                ],
            }
        ]

        table = build_levels_table(
            studies,
            [{"name": "thickness"}],
            [{"thickness": 2.0}],
        )

        self.assertEqual(
            table["columns"],
            ["水準", "thickness", "stress.thickness"],
        )
        self.assertEqual(table["rows"][0]["thickness"], 2.0)
        self.assertEqual(table["rows"][0]["stress.thickness"], 99.0)
        self.assertEqual(table["levels"][0]["design_ids"]["stress"], 1)

    def test_level_number_follows_the_shared_table_not_design_id(self):
        studies = [
            {
                "id": "crash",
                "designs": [
                    {
                        "design_id": 9,
                        "inputs": {"thickness": 1.0, "width": 50.0},
                        "responses": {"energy": 2.0},
                    },
                    {
                        "design_id": 3,
                        "inputs": {"thickness": 1.0, "width": 40.0},
                        "responses": {"energy": 1.0},
                    },
                    {
                        "design_id": 4,
                        "inputs": {"thickness": 9.0, "width": 40.0},
                        "responses": {"energy": 99.0},
                    },
                ],
            },
            {
                "id": "eigenvalue",
                "designs": [
                    {
                        "design_id": 1,
                        "inputs": {"thickness": 1.0, "width": 40.0},
                        "responses": {"freq": 8.0},
                    }
                ],
            },
        ]
        shared = [
            {"thickness": 1.0, "width": 40.0},
            {"thickness": 1.0, "width": 50.0},
        ]

        table = build_levels_table(
            studies,
            [{"name": "thickness"}, {"name": "width"}],
            shared,
        )

        self.assertEqual(table["rows"][0]["水準"], "水準1")
        self.assertEqual(table["rows"][0]["thickness"], 1.0)
        self.assertEqual(table["rows"][0]["width"], 40.0)
        self.assertEqual(table["rows"][0]["energy"], 1.0)
        self.assertEqual(table["rows"][0]["freq"], 8.0)
        self.assertEqual(table["levels"][0]["design_ids"]["crash"], 3)
        self.assertEqual(table["rows"][1]["水準"], "水準2")
        self.assertEqual(table["rows"][1]["width"], 50.0)
        self.assertEqual(len(table["rows"]), 2)
        self.assertEqual(table["unmatched"][0]["design_id"], 4)
        self.assertEqual(table["unmatched"][0]["study_id"], "crash")


if __name__ == "__main__":
    unittest.main()
