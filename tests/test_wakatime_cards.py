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
        self.assertIn("Aprendiz", cards["lifetime.svg"])
        self.assertIn("Aprendiz", cards["rank_emblem.svg"])
        for card in cards.values():
            ET.fromstring(card)

    def test_custom_rank_thresholds(self):
        self.assertEqual(module.level_for_hours(0)[1], "Iniciante")
        self.assertEqual(module.level_for_hours(100)[1], "Aprendiz")
        self.assertEqual(module.level_for_hours(2500)[1], "Arquiteto")
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
        self.assertIn("data:image/png;base64,",cards["lifetime.svg"])
        self.assertIn("M 91 218",cards["spedometer.svg"])

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

    def test_real_png_medal_rendering(self):
        import tempfile
        from PIL import Image
        from render_rank_png import render
        lifetime={"data":{"total_seconds":3600*145}}
        svg=module.generate_cards(self.month,self.week,self.summaries,
                                  None,self.today,lifetime)["lifetime.svg"]
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            source=root/"lifetime.svg"
            source.write_text(svg,encoding="utf-8")
            output=root/"lifetime.png"
            emblem=root/"emblem.png"
            badges=Path(__file__).resolve().parents[1]/"assets/badges/current"
            render(source,2,badges,output,emblem)
            with Image.open(output) as card:
                self.assertEqual(card.size,(1400,618))
            with Image.open(emblem) as image:
                self.assertEqual(image.size,(320,320))

    def test_twelve_real_rank_boundaries(self):
        self.assertEqual(len(module.RANKS), 12)
        for i, rank in enumerate(module.RANKS):
            self.assertEqual(module.level_for_hours(rank['min_hours'])[0], i)
            self.assertEqual(module.level_for_hours(rank['min_hours'])[1], rank['name'])
            self.assertIn('data:image/png;base64,', module.insignia_svg(i, rank['color']))
            if rank['max_hours_exclusive'] is not None:
                self.assertEqual(module.level_for_hours(rank['max_hours_exclusive']-0.01)[0], i)
        self.assertEqual(module.level_for_hours(8000)[1], 'Soberano')

    def test_paired_cards_equal_geometry_and_baselines(self):
        """Both GitHub profile cards must have identical boxes and footer rules."""
        pairs = (module.speed_card(3600, 1800), module.rank_card(
            {"current_user": {"rank": 8937}}, {"total_seconds": 3600}))
        svg_ns = "{http://www.w3.org/2000/svg}"
        for svg in pairs:
            root = ET.fromstring(svg)
            self.assertEqual(root.attrib["width"], "350")
            self.assertEqual(root.attrib["height"], "300")
            self.assertEqual(root.attrib["viewBox"], "0 0 350 300")
            self.assertIn('M 28 251 H 322', svg)
            self.assertIn('y="280"', svg)
        self.assertIn("#8937", pairs[1])

