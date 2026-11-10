#!/usr/bin/env python3
"""Render private WakaTime API stats as public, dependency-free SVG cards.

Only WakaTime's official API receives the OAuth bearer token. A failed API
request never overwrites the last successful SVGs.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import math
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

BASE = "https://api.wakatime.com/api/v1"
OUT = pathlib.Path("wakatime")
BG, BORDER, TEXT, MUTED = "#0d1117", "#30363d", "#e6edf3", "#8b949e"
ACCENT, GREEN = "#38bdf8", "#34d399"


def api(path: str, token: str, params: dict | None = None) -> dict:
    url = BASE + "/" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url, headers={"Authorization": "Bearer " + token, "Accept": "application/json",
                      "User-Agent": "axrobert-readme-stats/1.0"}
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                status = response.status
                payload = json.load(response)
        except urllib.error.HTTPError as err:
            # Avoid logging response bodies or request headers: they can be sensitive.
            raise RuntimeError("WakaTime HTTP %s em %s" % (err.code, path)) from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
            raise RuntimeError("Falha de conexão/resposta em %s (%s)" %
                               (path, type(err).__name__)) from None
        if "error" in payload or "errors" in payload:
            raise RuntimeError("Resposta de erro do WakaTime em " + path)
        data = payload.get("data")
        if status == 202 or (isinstance(data, dict) and data.get("is_up_to_date") is False):
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError("WakaTime ainda processando estatísticas: " + path)
        return payload
    raise RuntimeError("WakaTime indisponível: " + path)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def words(value: float) -> str:
    minutes = max(0, round(float(value or 0) / 60))
    h, m = divmod(minutes, 60)
    return f"{h}h {m:02d}min"


def txt(x, y, value, size=15, color=TEXT, weight=400, anchor=None):
    extra = ' text-anchor="%s"' % anchor if anchor else ""
    return (f'<text x="{x}" y="{y}" fill="{color}" font-family="Arial, sans-serif" '
            f'font-size="{size}" font-weight="{weight}"{extra}>{esc(value)}</text>')


def base(width, height, title, subtitle, body):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">'
           f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="16" '
           f'fill="{BG}" stroke="{BORDER}" stroke-width="2"/>'
           f'<rect x="28" y="24" width="4" height="24" rx="2" fill="{ACCENT}"/>'
           + txt(44, 43, title, 20, TEXT, 700)
           + txt(28, 69, subtitle, 12, MUTED)
           + body + '</svg>')
    ET.fromstring(svg)  # Refuse malformed SVG.
    return svg + "\n"


def languages_card(stats):
    items = sorted(stats.get("languages") or [],
                   key=lambda v: v.get("total_seconds") or 0, reverse=True)[:10]
    amount = max((float(i.get("total_seconds") or 0) for i in items), default=0)
    parts = []
    if not items or amount == 0:
        parts.append(txt(35, 135, "Sem atividade por linguagem nos últimos 30 dias.", 15, MUTED))
    for n, item in enumerate(items):
        y = 118 + n * 31
        sec = float(item.get("total_seconds") or 0)
        w = round(310 * sec / amount, 1) if amount else 0
        parts.extend([
            txt(32, y, str(item.get("name") or "Outra")[:23], 13, TEXT),
            f'<rect x="230" y="{y-13}" width="310" height="15" rx="5" fill="#212b36"/>',
            f'<rect x="230" y="{y-13}" width="{w}" height="15" rx="5" fill="{ACCENT}"/>',
            txt(554, y, words(sec), 12, MUTED),
        ])
    return base(700, 450, "Linguagens", "Atividade verificada · últimos 30 dias",
                "".join(parts))


def arc(cx, cy, r, fraction):
    fraction = min(1.0, max(0.0, fraction))
    if fraction <= 0:
        return ""
    angle = math.pi * (1.0 - fraction)
    x, y = cx + r * math.cos(angle), cy - r * math.sin(angle)
    large = 1 if fraction > 0.5 else 0
    return (f'<path d="M {cx-r} {cy} A {r} {r} 0 {large} 1 {x:.2f} {y:.2f}" '
            f'fill="none" stroke="{GREEN}" stroke-width="15" stroke-linecap="round"/>')


def speed_card(today_seconds, daily_avg):
    # The 8-hour target is a display scale, not a claim about a WakaTime tier.
    fraction = today_seconds / (8 * 3600)
    body = (f'<path d="M 65 172 A 100 100 0 0 1 265 172" '
            f'fill="none" stroke="#26313b" stroke-width="15" stroke-linecap="round"/>'
            + arc(165, 172, 100, fraction)
            + txt(165, 150, words(today_seconds), 25, TEXT, 700, "middle")
            + txt(165, 178, "hoje", 13, MUTED, 400, "middle")
            + txt(165, 227, "Média diária (7 dias): " + words(daily_avg),
                  12, MUTED, 400, "middle"))
    return base(330, 250, "Atividade", "Tempo de programação", body)


def rank_card(leader, week):
    current = (leader or {}).get("current_user") or {}
    rank = current.get("rank")
    valid = isinstance(rank, int) and rank > 0
    status = "#" + str(rank) if valid else "—"
    description = "Posição no ranking público" if valid else "Sem posição pública disponível"
    body = (txt(31, 135, status, 53, GREEN if valid else MUTED, 700)
            + txt(31, 163, description, 14, MUTED)
            + '<path d="M 30 183 H 330" stroke="#30363d"/>'
            + txt(31, 211, "Últimos 7 dias", 13, MUTED)
            + txt(331, 211, words(week.get("total_seconds") or 0),
                  15, TEXT, 700, "end"))
    return base(360, 250, "Ranking semanal", "WakaTime · atividade pública", body)


def heat_card(summaries, today):
    by_date = {}
    for day in summaries:
        key = (day.get("range") or {}).get("date")
        if key:
            by_date[key] = float((day.get("grand_total") or {}).get("total_seconds") or 0)
    start = today - dt.timedelta(days=29)
    first_monday = start - dt.timedelta(days=start.weekday())
    total = sum(by_date.get((start + dt.timedelta(days=k)).isoformat(), 0)
                for k in range(30))
    active = 0
    squares = []
    for k in range(30):
        day = start + dt.timedelta(days=k)
        sec = by_date.get(day.isoformat(), 0)
        if sec:
            active += 1
        level = 0 if sec <= 0 else min(4, max(1, math.ceil(sec / 7200)))
        colors = ["#202a35", "#145c51", "#18836e", "#25ae8d", "#34d399"]
        delta = (day - first_monday).days
        x, y = 57 + (delta // 7) * 28, 89 + (delta % 7) * 24
        squares.append(
            f'<rect x="{x}" y="{y}" width="20" height="20" rx="4" '
            f'fill="{colors[level]}"><title>{day.isoformat()}: {esc(words(sec))}</title></rect>'
        )
    body = ("".join(squares)
            + txt(295, 121, words(total), 31, TEXT, 700)
            + txt(295, 147, "Total nos últimos 30 dias", 13, MUTED)
            + txt(295, 190, str(active) + "/30", 26, GREEN, 700)
            + txt(295, 215, "Dias com atividade", 13, MUTED)
            + txt(57, 277, "Menos", 11, MUTED)
            + "".join(f'<rect x="{100+i*25}" y="265" width="17" height="17" '
                      f'rx="4" fill="{c}"/>' for i, c in enumerate(
                          ["#202a35", "#145c51", "#18836e", "#25ae8d", "#34d399"]))
            + txt(244, 277, "Mais", 11, MUTED))
    return base(700, 302, "Calendário de atividade",
                "Últimos 30 dias · horário America/Maceio", body)


def generate_cards(month, week, summaries, leader, today):
    days = summaries.get("data")
    if not isinstance(days, list):
        raise RuntimeError("Formato inesperado das atividades diárias")
    stats30, stats7 = month.get("data"), week.get("data")
    if not isinstance(stats30, dict) or not isinstance(stats7, dict):
        raise RuntimeError("Formato inesperado das estatísticas")
    daily = {((entry.get("range") or {}).get("date")):
             float((entry.get("grand_total") or {}).get("total_seconds") or 0)
             for entry in days}
    cards = {
        "all_projs_bar_vertical.svg": languages_card(stats30),
        "spedometer.svg": speed_card(daily.get(today.isoformat(), 0),
                                    float(stats7.get("daily_average") or 0)),
        "weekly_ranking.svg": rank_card(leader, stats7),
        "heatmap.svg": heat_card(days, today),
    }
    for filename, content in cards.items():
        if "Card Error" in content or "Heatmap Error" in content:
            raise RuntimeError("Gerador inválido: " + filename)
        ET.fromstring(content)
    return cards


def main():
    token = os.environ.get("WAKATIME_OAUTH_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "Configure WAKATIME_OAUTH_TOKEN nos Secrets do repositório. "
            "Não envie o token em arquivos, URLs ou mensagens."
        )
    timezone = ZoneInfo("America/Maceio")
    today = dt.datetime.now(timezone).date()
    month = api("users/current/stats/last_30_days", token)
    week = api("users/current/stats/last_7_days", token)
    summaries = api("users/current/summaries", token, {
        "start": (today - dt.timedelta(days=29)).isoformat(), "end": today.isoformat(),
        "timezone": "America/Maceio"
    })
    # Public leaderboards are optional and may not list the account.
    # Do not present an invented rank if unavailable.
    try:
        leader = api("leaders", token)
    except RuntimeError:
        leader = None
    cards = generate_cards(month, week, summaries, leader, today)
    OUT.mkdir(parents=True, exist_ok=True)
    for filename, svg in cards.items():
        (OUT / filename).write_text(svg, encoding="utf-8")
    print("4 SVGs gerados e validados a partir da API oficial do WakaTime.")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print("ERRO: " + str(exc), file=sys.stderr)
        sys.exit(1)
