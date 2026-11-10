#!/usr/bin/env python3
"""Compose a profile lifetime card with a genuine raster rank illustration.

The WakaTime card's text/bars remain SVG-driven, while the emblem is supplied
as an image-generated transparent PNG. The final public card is a PNG so the
GitHub README does not depend on blocked SVG external-image links.
"""
from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

import cairosvg
from PIL import Image, ImageDraw

RANKS = (
    '01-novice.png', '02-explorer.png', '03-artisan.png',
    '04-specialist.png', '05-veteran.png', '06-master.png',
    '07-legend.png',
)


def render(card: Path, tier: int, assets: Path, output: Path, emblem_output: Path) -> None:
    if not 0 <= tier < len(RANKS):
        raise ValueError('Rank index must be between 0 and 6')
    badge_path = assets / RANKS[tier]
    if not badge_path.is_file():
        raise FileNotFoundError(f'Rank PNG not found: {badge_path}')
    svg = card.read_bytes()
    root = ET.fromstring(svg)
    ns = '{http://www.w3.org/2000/svg}'
    if root.tag != ns + 'svg' or root.attrib.get('viewBox') != '0 0 700 309':
        raise ValueError('Unexpected WakaTime lifetime card dimensions')
    base_rect = root.find(ns + 'rect')
    if base_rect is None:
        raise ValueError('Missing card background')
    background = base_rect.attrib.get('fill', '#0d1117')
    # Render at 2x so README text and bars remain crisp.
    canvas = Image.open(BytesIO(cairosvg.svg2png(bytestring=svg, scale=2))).convert('RGBA')
    if canvas.size != (1400, 618):
        raise ValueError('Unexpected rendered card size')
    # Completely hide the old programmatic shield without covering the stats.
    drawer = ImageDraw.Draw(canvas)
    drawer.rectangle((44, 166, 371, 584), fill=background)
    with Image.open(badge_path) as raw:
        badge = raw.convert('RGBA')
    if not badge.getbbox():
        raise ValueError('Empty rank emblem image')
    badge = badge.resize((320, 320), Image.Resampling.LANCZOS)
    canvas.alpha_composite(badge, (47, 181))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, optimize=True)
    # Keep the standalone rank transparent and independent of a card background.
    badge.save(emblem_output, optimize=True)
    with Image.open(output) as check:
        check.verify()
    with Image.open(emblem_output) as check:
        check.verify()
    print(f'Rank PNG applied: {RANKS[tier]} -> {output}')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--card', type=Path, required=True)
    parser.add_argument('--tier-file', type=Path, required=True)
    parser.add_argument('--assets', type=Path, default=Path('assets/badges'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--emblem-output', type=Path, required=True)
    args = parser.parse_args()
    tier = int(args.tier_file.read_text(encoding='ascii').strip())
    render(args.card, tier, args.assets, args.output, args.emblem_output)


if __name__ == '__main__':
    main()