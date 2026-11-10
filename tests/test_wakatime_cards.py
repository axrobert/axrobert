import datetime as dt
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

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
        self.assertIn("Sem posição pública disponível", cards["weekly_ranking.svg"])

    def test_zero_activity_does_not_invent_stats(self):
        cards = module.generate_cards(
            {"data": {"languages": []}},
            {"data": {"total_seconds": 0, "daily_average": 0}},
            {"data": []}, None, self.today)
        self.assertIn("Sem atividade", cards["all_projs_bar_vertical.svg"])
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

