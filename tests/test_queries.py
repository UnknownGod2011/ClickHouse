import unittest

from takekeeper.queries import EditorialConstraints, continuity_evidence_sql, editorial_retrieval_sql


class QueryTests(unittest.TestCase):
    def test_continuity_query_is_scoped(self):
        sql = continuity_evidence_sql("glass-house", "28", "S28-T47")
        self.assertIn("o.production_id=p", sql)
        self.assertIn("o.scene_id=s", sql)
        self.assertIn("o.take_id=t", sql)
        self.assertIn("b.active=true", sql)

    def test_editorial_query_enforces_hard_constraints(self):
        sql = editorial_retrieval_sql(EditorialConstraints("glass-house", "28", 4))
        for token in [
            "t.director_rating >= 4",
            "dialogue.target_line_present",
            "performance.eyeline.after_target_line",
            "quality.boom_visible",
            "'toward_door'",
            "'false'",
        ]:
            self.assertIn(token, sql)

    def test_sql_string_escaping(self):
        self.assertIn("'prod''1'", editorial_retrieval_sql(EditorialConstraints("prod'1", "28", 4)))

    def test_queries_can_target_isolated_database(self):
        continuity = continuity_evidence_sql("glass-house", "28", "S28-T47", database="takekeeper_it_123")
        editorial = editorial_retrieval_sql(
            EditorialConstraints("glass-house", "28", 4),
            database="takekeeper_it_123",
        )
        self.assertIn("FROM takekeeper_it_123.observations", continuity)
        self.assertIn("FROM takekeeper_it_123.takes", editorial)
        self.assertIn("INNER JOIN takekeeper_it_123.observations", editorial)

    def test_rejects_unsafe_database_identifier(self):
        with self.assertRaises(ValueError):
            continuity_evidence_sql("glass-house", "28", "S28-T47", database="takekeeper; DROP DATABASE default")
        with self.assertRaises(ValueError):
            editorial_retrieval_sql(
                EditorialConstraints("glass-house", "28", 4),
                database="takekeeper-prod",
            )


if __name__ == "__main__":
    unittest.main()
