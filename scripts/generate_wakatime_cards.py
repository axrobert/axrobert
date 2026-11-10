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
from rank_art import rank_svg

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


def languages_card(stats, all_time=False):
    items = sorted(stats.get("languages") or [],
                   key=lambda v: float(v.get("total_seconds") or 0),
                   reverse=True)[:10]
    maximum = max((float(i.get("total_seconds") or 0) for i in items), default=0)
    total = float(stats.get("total_seconds") or 0)
    parts = [
        txt(32, 109, "TEMPO DE CÓDIGO", 11, MUTED, 700),
        txt(669, 109, words(total), 14, TEXT, 700, "end"),
        '<path d="M 30 125 H 670" stroke="#25303d"/>',
    ]
    if not items or maximum <= 0:
        parts.append(txt(35, 195, "Nenhuma linguagem registrada neste período.", 15, MUTED))
    for n, item in enumerate(items):
        y = 159 + n * 29
        sec = max(0, float(item.get("total_seconds") or 0))
        name = str(item.get("name") or "Outra")
        if len(name) > 22:
            name = name[:20] + "…"
        width = round(286 * sec / maximum, 1) if maximum else 0
        pct = 100 * sec / total if total else 0
        parts.extend([
            txt(32, y, name, 13, TEXT, 600),
            f'<rect x="226" y="{y-12}" width="286" height="14" rx="6" fill="#202b37"/>',
            f'<rect x="226" y="{y-12}" width="{width}" height="14" rx="6" fill="{ACCENT}"/>',
            txt(527, y, f"{pct:.1f}%", 11, MUTED),
            txt(668, y, words(sec), 12, TEXT, 600, "end"),
        ])
    return base(700, 480, "Linguagens", "Histórico completo registrado · WakaTime" if all_time else "Últimos 30 dias · tempo registrado pelo WakaTime",
                "".join(parts))

def arc(cx, cy, r, fraction):
    fraction = min(1.0, max(0.0, fraction))
    if fraction <= 0:
        return ""
    angle = math.pi * (1.0 - fraction)
    x, y = cx + r * math.cos(angle), cy - r * math.sin(angle)
    large = 1 if fraction > 0.5 else 0
    return (f'<path d="M {cx-r} {cy} A {r} {r} 0 {large} 1 {x:.2f} {y:.2f}" '
            f'fill="none" stroke="{GREEN}" stroke-width="13" stroke-linecap="round"/>')

def speed_card(today_seconds, daily_avg):
    # The gauge text sits below the arch apex, isolated from the meter stroke.
    fraction = min(1.0, max(0.0, today_seconds / (8 * 3600)))
    body = (
        '<path d="M 79 210 A 86 86 0 0 1 251 210" fill="none" '
        'stroke="#24303b" stroke-width="13" stroke-linecap="round"/>'
        + arc(165, 210, 86, fraction)
        + txt(165, 175, words(today_seconds), 25, TEXT, 700, "middle")
        + txt(165, 197, "registrado hoje", 12, MUTED, 400, "middle")
        + '<path d="M 26 242 H 304" stroke="#25303d"/>'
        + txt(27, 270, "Média por dia ativo", 11, MUTED)
        + txt(304, 270, words(daily_avg), 12, TEXT, 700, "end")
    )
    return base(330, 293, "Atividade", "Hoje · meta visual de 8h", body)

def rank_card(leader, week):
    current = (leader or {}).get("current_user") or {}
    position = current.get("rank")
    verified = isinstance(position, int) and not isinstance(position, bool) and position > 0
    label = f"#{position}" if verified else "—"
    body = (
        txt(28, 125, "CLASSIFICAÇÃO OFICIAL", 11, MUTED, 700)
        + txt(28, 178, label, 46, GREEN if verified else MUTED, 700)
        + txt(28, 200, "Sua posição no WakaTime" if verified
              else "Sem posição pública confirmada", 12, MUTED)
        + '<path d="M 27 220 H 330" stroke="#25303d"/>'
        + txt(28, 249, "Últimos 7 dias", 12, MUTED)
        + txt(330, 249, words(week.get("total_seconds") or 0),
              14, TEXT, 700, "end")
    )
    return base(360, 271, "Ranking semanal",
                "Ranking público oficial · sem pontuação fictícia", body)

def heat_card(summaries, today):
    by_date = {}
    for item in summaries:
        day = (item.get("range") or {}).get("date")
        if day:
            by_date[day] = max(0, float((item.get("grand_total") or {}).get("total_seconds") or 0))
    start = today - dt.timedelta(days=29)
    grid_start = start - dt.timedelta(days=start.weekday())
    total_seconds = 0
    active_days = 0
    cells = []
    for i in range(30):
        day = start + dt.timedelta(days=i)
        seconds = by_date.get(day.isoformat(), 0)
        total_seconds += seconds
        if seconds > 0:
            active_days += 1
        palette = ["#202a35", "#145c51", "#18836e", "#25ae8d", "#34d399"]
        level = 0 if seconds == 0 else min(4, max(1, math.ceil(seconds / 7200)))
        offset = (day - grid_start).days
        x, y = 62 + (offset // 7) * 29, 99 + (offset % 7) * 25
        cells.append(f'<rect x="{x}" y="{y}" width="20" height="20" rx="4" '
                     f'fill="{palette[level]}"><title>{day.isoformat()}: {esc(words(seconds))}</title></rect>')
    palette = ["#202a35", "#145c51", "#18836e", "#25ae8d", "#34d399"]
    body = (
        "".join(cells)
        + txt(299, 139, words(total_seconds), 31, TEXT, 700)
        + txt(299, 160, "Total · últimos 30 dias", 13, MUTED)
        + txt(299, 215, f"{active_days}/30", 26, GREEN, 700)
        + txt(299, 236, "Dias com atividade registrada", 13, MUTED)
        + '<path d="M 30 288 H 670" stroke="#25303d"/>'
        + txt(48, 314, "Menos", 11, MUTED)
        + "".join(f'<rect x="{99+i*25}" y="301" width="18" height="18" rx="4" fill="{c}"/>'
                  for i, c in enumerate(palette))
        + txt(238, 314, "Mais", 11, MUTED)
    )
    return base(700, 344, "Calendário de atividade",
                "30 dias de registros · fuso de Alagoas (UTC−3)", body)

# These levels are original to this README; they are NOT WakaTime leaderboards.
LEVELS = (
    (0, "Novato", "#94a3b8"),
    (25, "Explorador", "#38bdf8"),
    (100, "Artesão", "#34d399"),
    (250, "Especialista", "#a78bfa"),
    (500, "Veterano", "#f59e0b"),
    (1000, "Mestre", "#eab308"),
    (2500, "Lenda", "#fb7185"),
)


def level_for_hours(hours):
    hours = max(0, float(hours))
    idx = max(i for i, (minimum, _, _) in enumerate(LEVELS) if hours >= minimum)
    min_hours, name, color = LEVELS[idx]
    next_hours = LEVELS[idx + 1][0] if idx + 1 < len(LEVELS) else None
    progress = (min(1, (hours - min_hours) / (next_hours - min_hours))
                if next_hours else 1.0)
    # Stars indicate completion of the CURRENT tier, not GitHub/WakaTime ratings.
    stars = 5 if next_hours is None else min(5, int(progress * 5))
    return idx, name, color, next_hours, progress, stars


def star_path(cx, cy, outer=8, inner=3.7):
    points = []
    for i in range(10):
        angle = math.pi * (-0.5 + i / 5)
        radius = outer if i % 2 == 0 else inner
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in points) + " Z"


def stars_svg(x, y, count, color, radius=8, gap=24):
    return "".join(
        f'<path d="{star_path(x + n*gap, y, radius, radius*0.47)}" '
        f'fill="{color if n < count else "#293544"}" '
        f'stroke="{color if n < count else "#445160"}" stroke-width="0.7"/>'
        for n in range(5)
    )


def insignia_svg(level_idx, color, x=34, y=90, scale=1):
    """Embed a tier-specific original 2.5D AXR rank sigil."""
    return rank_svg(level_idx, x, y, float(scale)*0.70)

def lifetime_card(lifetime, month, week):
    data = lifetime.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("total_seconds"), (float, int)):
        raise RuntimeError("WakaTime não forneceu total histórico verificável")
    total = max(0, float(data["total_seconds"]))
    idx, name, color, next_hours, progress, filled = level_for_hours(total / 3600)
    bars = 232 * progress
    progression = (f"Próximo: {next_hours:,}h".replace(",", ".")
                   if next_hours else "Patamar máximo desta edição")
    body = (
        insignia_svg(idx, color, 31, 92, 1.05)
        + txt(193, 113, "CLASSIFICAÇÃO PRÓPRIA · POR HORAS", 11, MUTED, 700)
        + txt(193, 149, name, 28, color, 700)
        + stars_svg(205, 176, filled, color, 9, 25)
        + txt(193, 209, "Horas desde a criação da conta", 12, MUTED)
        + txt(193, 246, words(total), 30, TEXT, 700)
        + '<rect x="194" y="265" width="232" height="7" rx="3.5" fill="#26313d"/>'
        + f'<rect x="194" y="265" width="{bars:.1f}" height="7" rx="3.5" fill="{color}"/>'
        + txt(193, 287, progression, 11, MUTED)
        + '<path d="M 447 95 V 271" stroke="#25303d"/>'
        + txt(472, 119, "ÚLTIMOS 30 DIAS", 11, MUTED, 700)
        + txt(472, 155, words(month.get("total_seconds") or 0), 22, TEXT, 700)
        + txt(472, 213, "ÚLTIMOS 7 DIAS", 11, MUTED, 700)
        + txt(472, 248, words(week.get("total_seconds") or 0), 22, TEXT, 700)
    )
    return base(700, 309, "Tempo total & evolução",
                "WakaTime + sistema de progressão personalizado", body)


def rank_emblem(lifetime):
    data = lifetime.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("total_seconds"), (float, int)):
        raise RuntimeError("Sem dados verificados para o emblema")
    idx, name, color, _, _, filled = level_for_hours(float(data["total_seconds"]) / 3600)
    body = (insignia_svg(idx, color, 37, 82, 0.85)
            + txt(96, 213, name, 16, color, 700, "middle")
            + stars_svg(55, 238, filled, color, 6.4, 20))
    return base(192, 259, "Emblema", "Nível por horas", body)

def generate_cards(month, week, summaries, leader, today, lifetime=None, all_languages=None):
    days = summaries.get("data")
    if not isinstance(days, list):
        raise RuntimeError("Formato inesperado das atividades diárias")
    stats30, stats7 = month.get("data"), week.get("data")
    if not isinstance(stats30, dict) or not isinstance(stats7, dict):
        raise RuntimeError("Formato inesperado das estatísticas")
    daily = {(entry.get("range") or {}).get("date"):
             float((entry.get("grand_total") or {}).get("total_seconds") or 0)
             for entry in days}
    cards = {
        "all_projs_bar_vertical.svg": languages_card(all_languages["data"], all_time=True)
        if all_languages is not None else languages_card(stats30),
        "spedometer.svg": speed_card(daily.get(today.isoformat(), 0),
                                    float(stats7.get("daily_average") or 0)),
        "weekly_ranking.svg": rank_card(leader, stats7),
        "heatmap.svg": heat_card(days, today),
    }
    if lifetime is not None:
        cards["lifetime.svg"] = lifetime_card(lifetime, stats30, stats7)
        cards["rank_emblem.svg"] = rank_emblem(lifetime)
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
    all_languages = api("users/current/stats/all_time", token)
    lifetime = api("users/current/all_time_since_today", token)
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
    cards = generate_cards(month, week, summaries, leader, today, lifetime, all_languages)
    OUT.mkdir(parents=True, exist_ok=True)
    for filename, svg in cards.items():
        (OUT / filename).write_text(svg, encoding="utf-8")
    print(f"{len(cards)} SVGs gerados e validados a partir da API oficial do WakaTime.")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print("ERRO: " + str(exc), file=sys.stderr)
        sys.exit(1)
