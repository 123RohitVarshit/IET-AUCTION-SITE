import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.core.loader import load_candidates, load_teams


class LoaderTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def write_file(self, name: str, content: str) -> str:
        path = self.dir / name
        path.write_text(content, encoding="utf-8")
        return str(path)


class CandidateLoaderTests(LoaderTestBase):
    def test_load_valid_candidates(self):
        path = self.write_file(
            "rated.csv",
            "id,name,rating,tier,base_price,projects,experience\n"
            "1,Aarav,1900,1,1000,Smart Attendance,2 hackathons\n"
            "2,Diya,1700,2,600,Campus Market,1 hackathon\n",
        )

        candidates = load_candidates(path)

        self.assertEqual(len(candidates), 2)

        first = candidates[0]

        self.assertEqual(first["id"], 1)
        self.assertEqual(first["name"], "Aarav")
        self.assertEqual(first["rating"], 1900)
        self.assertEqual(first["tier"], 1)
        self.assertEqual(first["base_price"], 1000)
        self.assertEqual(
            first["profile"],
            {
                "projects": "Smart Attendance",
                "experience": "2 hackathons",
            },
        )

    def test_empty_file_returns_empty_list(self):
        path = self.write_file("rated.csv", "")

        self.assertEqual(load_candidates(path), [])

    def test_missing_required_columns_raise(self):
        path = self.write_file(
            "rated.csv",
            "id,name\n"
            "1,Aarav\n",
        )

        with self.assertRaises(ValueError):
            load_candidates(path)

    def test_invalid_tier_raises(self):
        path = self.write_file(
            "rated.csv",
            "id,name,rating,tier,base_price\n"
            "1,Aarav,1900,5,1000\n",
        )

        with self.assertRaises(ValueError):
            load_candidates(path)

    def test_duplicate_candidate_ids_raise(self):
        path = self.write_file(
            "rated.csv",
            "id,name,rating,tier,base_price\n"
            "1,Aarav,1900,1,1000\n"
            "1,Diya,1700,2,600\n",
        )

        with self.assertRaises(ValueError):
            load_candidates(path)


class TeamLoaderTests(LoaderTestBase):
    def test_load_valid_teams(self):
        path = self.write_file(
            "teams.csv",
            "id,name,login_code,purse\n"
            "1,Team Alpha,alpha-code,10000\n"
            "2,Team Beta,beta-code,10000\n",
        )

        teams = load_teams(path)

        self.assertEqual(len(teams), 2)

        self.assertEqual(teams[0]["id"], 1)
        self.assertEqual(teams[0]["name"], "Team Alpha")
        self.assertEqual(teams[0]["login_code"], "alpha-code")
        self.assertEqual(teams[0]["purse"], 10000)

    def test_optional_purse_can_be_missing(self):
        path = self.write_file(
            "teams.csv",
            "id,name,login_code\n"
            "1,Team Alpha,alpha-code\n",
        )

        teams = load_teams(path)

        self.assertEqual(len(teams), 1)
        self.assertNotIn("purse", teams[0])

    def test_missing_login_code_raises(self):
        path = self.write_file(
            "teams.csv",
            "id,name\n"
            "1,Team Alpha\n",
        )

        with self.assertRaises(ValueError):
            load_teams(path)

    def test_duplicate_team_ids_raise(self):
        path = self.write_file(
            "teams.csv",
            "id,name,login_code\n"
            "1,Team Alpha,alpha-code\n"
            "1,Team Beta,beta-code\n",
        )

        with self.assertRaises(ValueError):
            load_teams(path)


if __name__ == "__main__":
    unittest.main()