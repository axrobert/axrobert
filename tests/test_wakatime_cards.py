import datetime as dt
import importlib.util
import sys
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
spec = importlib.util.spec_from_file_location(
    "wakatime_cards", Path(__file__).resolve().parents[1] /
    "scripts/generate_wakatime_cards.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class WakaTimeCardTests(unittest.TestCase):
    def setUp(self):
        self.today = dt.date(2026, 11, 10)
        self.month = {"data": {"languages": [
            {"name": "TypeScript", "total_seconds": 54000},
            {"name": "Python", "total_seconds": 14400},
        ], "total_seconds": 70000}}
        self.week = {"data": {"total_seconds": 10000, "daily_average": 1400}}
        self.summaries = {"data": [
            {"range": {"date": "2026-11-10"}, "grand_total": {"total_seconds": 3600}},
            {"range": {"date": "2026-11-09"}, "grand_total": {"total_seconds": 7200}}
        ]}

    def test_four_svg_cards_are_well_formed(self):
        cards = module.generate_cards(self.month, self.week, self.summaries,
                                      None, self.today)
        self.assertEqual(set(cards), {"all_projs_bar_vertical.svg", "spedometer.svg",
                                       "weekly_ranking.svg", "heatmap.svg"})
        for content in cards.values():
            self.assertEqual(ET.fromstring(content).tag,
                             "{http://www.w3.org/2000/svg}svg")
            self.assertNotIn("Card Error", content)
            self.assertNotIn("Heatmap Error", content)
        self.assertIn("TypeScript", cards["all_projs_bar_vertical.svg"])
        self.assertIn("Sem posição pública confirmada", cards["weekly_ranking.svg"])

    def test_zero_activity_does_not_invent_stats(self):
        cards = module.generate_cards(
            {"data": {"languages": []}},
            {"data": {"total_seconds": 0, "daily_average": 0}},
            {"data": []}, None, self.today)
        self.assertIn("Nenhuma linguagem registrada neste período", cards["all_projs_bar_vertical.svg"])
        self.assertIn("0h 00min", cards["spedometer.svg"])

    def test_unexpected_wakatime_shape_rejected(self):
        with self.assertRaises(RuntimeError):
            module.generate_cards({"oops": "invalid"}, self.week,
                                  self.summaries, None, self.today)

    def test_xml_escape(self):
        self.month["data"]["languages"][0]["name"] = '<script onload="oops"> &'
        svg = module.generate_cards(self.month, self.week, self.summaries,
                                    None, self.today)["all_projs_bar_vertical.svg"]
        self.assertNotIn("<script", svg)
        self.assertIn("&lt;script", svg)
        ET.fromstring(svg)

    def test_lifetime_rank_and_badges(self):
        lifetime = {"data": {"total_seconds": 3600 * 145}}
        cards = module.generate_cards(self.month, self.week, self.summaries,
                                      None, self.today, lifetime)
        self.assertEqual(len(cards), 6)
        self.assertIn("145h 00min", cards["lifetime.svg"])
        self.assertIn("Artesão", cards["lifetime.svg"])
        self.assertIn("Artesão", cards["rank_emblem.svg"])
        for card in cards.values():
            ET.fromstring(card)

    def test_custom_rank_thresholds(self):
        self.assertEqual(module.level_for_hours(0)[1], "Novato")
        self.assertEqual(module.level_for_hours(100)[1], "Artesão")
        self.assertEqual(module.level_for_hours(2500)[1], "Lenda")
        self.assertEqual(module.level_for_hours(2500)[5], 5)

    def test_invalid_lifetime_rejected(self):
        with self.assertRaises(RuntimeError):
            module.generate_cards(self.month, self.week, self.summaries,
                                  None, self.today, {"data": {}})


    def test_historical_language_stats_override_30_days(self):
        historic={"data":{"total_seconds":3600*250,"languages":[{"name":"Rust","total_seconds":3600*240}]}}
        cards=module.generate_cards(self.month,self.week,self.summaries,None,self.today,
                                    {"data":{"total_seconds":3600*300}}, historic)
        self.assertIn("Histórico completo registrado",cards["all_projs_bar_vertical.svg"])
        self.assertIn("Rust",cards["all_projs_bar_vertical.svg"])
        self.assertNotIn("TypeScript",cards["all_projs_bar_vertical.svg"])
        self.assertIn("250h",cards["all_projs_bar_vertical.svg"])

    def test_badge_sigils_and_gauge_spacing(self):
        from rank_art import standalone
        for level in range(7):
            ET.fromstring(standalone(level))
        cards=module.generate_cards(self.month,self.week,self.summaries,None,self.today,
                                    {"data":{"total_seconds":3600*350}})
        self.assertIn("linearGradient",cards["lifetime.svg"])
        self.assertIn("M 79 210",cards["spedometer.svg"])

    def test_rejects_stale_thirty_day_data_as_historical(self):
        lifetime = {"data": {"total_seconds": 152*3600}}
        mistaken = {"data": {"total_seconds": 14*3600,
                             "languages": [{"name":"TypeScript","total_seconds":14*3600}]}}
        with self.assertRaisesRegex(RuntimeError, "não correspondem"):
            module.generate_cards(self.month, self.week, self.summaries, None,
                                  self.today, lifetime, mistaken)

    def test_verifies_genuine_historical_data(self):
        lifetime = {"data": {"total_seconds": 152*3600}}
        historical = {"data": {"total_seconds": 150*3600,
                               "languages": [{"name":"Rust","total_seconds":125*3600}]}}
        cards = module.generate_cards(self.month, self.week, self.summaries, None,
                                      self.today, lifetime, historical)
        chart = cards["all_projs_bar_vertical.svg"]
        self.assertIn("Histórico completo registrado", chart)
        self.assertIn("125h", chart)
        self.assertNotIn("TypeScript", chart)

    def test_rejects_missing_language_history(self):
        with self.assertRaisesRegex(RuntimeError, "indisponíveis"):
            module.verified_historical_stats(
                {"data":{"total_seconds":100000}},
                {"data":{"total_seconds":100000}}
            )
