#!/usr/bin/env python3
"""生成 profile 的 CTA 卡片 —— 官网那张「Final CTA」的同款，但换成了 profile 的文案。

**为什么要有这张卡**：profile 是一扇**门**，点进去就是官网。seckinyasar 的做法是
「一张 OG 图 + 一句 pitch」，所以我们把官网 `en/compiler/index.html` 的
「Final CTA」那张卡（`Write the next / hello.jhyy.`）搬过来当 profile 的门面 ——
看的人认出这是同一个产品，点一下就到官网。

**跟官网那张的差别**（用户定的）：
  - 文字全换（官网那张讲的是「下载编译器」，这张讲的是「这门语言本身」）
  - 底下**一排按钮收成一个**「Click Here」—— 整张图本身就是链接，按钮只是提示

**为什么标题要转成 path**：Instrument Serif 是网站自托管的字体，SVG 走
camo 渲染时**不能引用外部字体文件**（也不该指望渲染机装了同款字体）⇒
把字形轮廓用 fontTools 描出来，输出纯矢量路径 —— 哪儿渲染都一样。

**设计令牌全部来自官网** `JiHuiYiYou-website/assets/css/main.css` 的
`--brand-*` / `--text-*` / `--bg-*` / `--hairline-*` / `--r-*`，改官网的令牌时
两边一起改（这一份是抄过来的，别当真相源）。

**用法**：
    python tools/make_cta_card.py            # → assets/cta-card.svg
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

from fontTools.misc.transform import Transform
from fontTools.pens.basePen import BasePen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
OUT = ROOT / "assets" / "cta-card.svg"
CALLIGRAPHY = ROOT / "assets" / "jhyy-calligraphy.png"

# ── 官网的令牌（JiHuiYiYou-website/assets/css/main.css） ──────────────────
BG_ELEV_1 = "#131316"
BG_DEEP = "#0a0a0a"
TEXT_1 = "#fafafa"
TEXT_2 = "#b4b4ba"
TEXT_3 = "#75757d"
TEXT_4 = "#48484e"
BRAND_300 = "#1de9c0"
BRAND_400 = "#00d4aa"
BRAND_500 = "#00a886"
BRAND_600 = "#007a66"
HAIRLINE = "rgba(255,255,255,0.06)"
HAIRLINE_2 = "rgba(255,255,255,0.10)"
R_CARD = 32

SANS = "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
MONO = "SFMono-Regular, Consolas, 'Liberation Mono', monospace"

W, H = 1200, 700
CX = W / 2

# ── 卡片文案（英文为主；中文只出现在书法图里） ───────────────────────────
TITLE_1 = "A systems language"
TITLE_2 = "that compiles itself."
SUB = [
    "JHYY is a statically typed, expression-oriented systems language.",
    "The compiler is written in the language itself — and the backend is a",
    "self-written amd64 emitter. No LLVM, no vendored QBE, no garbage collector.",
]
BUTTON = "Click Here"
META = [
    ("v4.1.5", BRAND_300),
    ("stable", TEXT_2),
    ("amd64", TEXT_2),
    ("281 / 301 PASS", TEXT_2),
    ("one language, four projects", TEXT_2),
]
CLONE = "git clone https://github.com/JiHuiYiYou/JiHuiYiYou-compiler"


class SvgPathPen(BasePen):
    """把字形轮廓收成一条 SVG path 的 data。"""

    def __init__(self, glyphSet):
        super().__init__(glyphSet)
        self.parts: list[str] = []

    def _moveTo(self, pt):
        self.parts.append(f"M{pt[0]:.2f} {pt[1]:.2f}")

    def _lineTo(self, pt):
        self.parts.append(f"L{pt[0]:.2f} {pt[1]:.2f}")

    def _curveToOne(self, p1, p2, p3):
        self.parts.append(
            f"C{p1[0]:.2f} {p1[1]:.2f} {p2[0]:.2f} {p2[1]:.2f} {p3[0]:.2f} {p3[1]:.2f}")

    def _closePath(self):
        self.parts.append("Z")

    def _endPath(self):
        pass

    def get_path(self) -> str:
        return " ".join(self.parts)


def outline(font: TTFont, text: str, size: float, tracking: float = 0.0) -> tuple[str, float]:
    """把一行字转成 path。返回 (path data, 宽度 px)。

    字体的 y 轴朝上、SVG 朝下 ⇒ 变换里带一个负的 y 缩放。
    """
    upm = font["head"].unitsPerEm
    sc = size / upm
    gs = font.getGlyphSet()
    cmap = font.getBestCmap()
    pen = SvgPathPen(gs)
    x = 0.0
    for ch in text:
        name = cmap.get(ord(ch))
        if name is None:
            continue
        tp = TransformPen(pen, Transform(sc, 0, 0, -sc, x, 0))
        gs[name].draw(tp)
        x += gs[name].width * sc + tracking
    return pen.get_path(), x


def centered_path(font: TTFont, text: str, size: float, baseline: float,
                  tracking: float = 0.0, fill: str = TEXT_1) -> str:
    """一行居中的描边标题。"""
    d, w = outline(font, text, size, tracking)
    x = CX - w / 2
    return (f'<path d="{d}" transform="translate({x:.2f} {baseline})" fill="{fill}"/>')


def embed_calligraphy(target_w: int) -> str:
    """把书法印记内嵌成 data URI。

    SVG 引外部图片会被浏览器掐掉（SVG-as-image 是 secure static mode）⇒ 必须内嵌。
    但原图 600px 宽有 122 KB，内嵌后整张卡要 210 KB ⇒ 先缩到实际显示宽度的 2 倍
    （视网膜够用，体积掉一个数量级）。没有 PIL 就退回原图。
    """
    raw = CALLIGRAPHY.read_bytes()
    try:
        import io

        from PIL import Image

        im = Image.open(io.BytesIO(raw)).convert("RGBA")
        h = round(target_w * im.height / im.width)
        im = im.resize((target_w, h), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        raw = buf.getvalue()
    except ImportError:
        pass
    return base64.b64encode(raw).decode("ascii")


def build() -> str:
    normal = TTFont(FONTS / "instrument-serif-400-normal-latin.woff2")
    italic = TTFont(FONTS / "instrument-serif-400-italic-latin.woff2")

    # ── 书法印记（中文）—— 内嵌成 data URI，SVG 引外部图片会被浏览器掐掉 ──
    calligraphy_h = 60
    calligraphy_w = calligraphy_h * 600 / 334
    png = embed_calligraphy(round(calligraphy_w * 2))

    # ── 标题（Instrument Serif，转成 path） ────────────────────────────
    title_size = 78
    t1 = centered_path(normal, TITLE_1, title_size, 232, tracking=-1.6)
    t2 = centered_path(italic, TITLE_2, title_size, 308, tracking=-1.6, fill=BRAND_300)

    # ── 正文 ────────────────────────────────────────────────────────────
    sub = "".join(
        f'<text x="{CX}" y="{y}" font-family="{SANS}" font-size="17" fill="{TEXT_2}" '
        f'text-anchor="middle">{line}</text>'
        for y, line in zip((356, 382, 408), SUB)
    )

    # ── 一颗按钮（官网那排收成一个） ─────────────────────────────────────
    btn_w, btn_h, btn_y = 214, 56, 438
    btn_x = CX - btn_w / 2
    icon = ('<path d="M7 17 L17 7 M9 7 L17 7 L17 15" fill="none" stroke="#050505" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')
    button = (
        f'<g>'
        f'<rect x="{btn_x}" y="{btn_y}" width="{btn_w}" height="{btn_h}" rx="{btn_h / 2}" '
        f'fill="{BRAND_400}" stroke="{BRAND_500}" stroke-width="1"/>'
        f'<text x="{btn_x + 42}" y="{btn_y + 35}" font-family="{SANS}" font-size="15" '
        f'font-weight="600" fill="#050505">{BUTTON}</text>'
        f'<circle cx="{btn_x + btn_w - 42}" cy="{btn_y + btn_h / 2}" r="14" fill="rgba(5,5,5,0.18)"/>'
        f'<g transform="translate({btn_x + btn_w - 49} {btn_y + btn_h / 2 - 7})">{icon}</g>'
        f'</g>'
    )

    # ── 事实行 ──────────────────────────────────────────────────────────
    meta_parts = []
    for i, (txt, col) in enumerate(META):
        if i:
            meta_parts.append(f'<tspan fill="{TEXT_4}"> · </tspan>')
        meta_parts.append(f'<tspan fill="{col}">{txt}</tspan>')
    meta = (f'<text x="{CX}" y="540" font-family="{SANS}" font-size="13" '
            f'text-anchor="middle">{"".join(meta_parts)}</text>')

    # ── clone 命令 ──────────────────────────────────────────────────────
    box_w, box_h, box_y = 720, 46, 578
    box_x = CX - box_w / 2
    copy_icon = ('<rect x="9" y="9" width="13" height="13" rx="2"/>'
                 '<path d="M5 15 H4 a2 2 0 0 1 -2 -2 V4 a2 2 0 0 1 2 -2 h9 a2 2 0 0 1 2 2 v1"/>')
    clone = (
        f'<g>'
        f'<rect x="{box_x}" y="{box_y}" width="{box_w}" height="{box_h}" rx="{box_h / 2}" '
        f'fill="{BG_DEEP}" stroke="{HAIRLINE_2}" stroke-width="1"/>'
        f'<text x="{box_x + 26}" y="{box_y + 29}" font-family="{MONO}" font-size="12.5" '
        f'fill="{BRAND_400}" font-weight="500">$</text>'
        f'<text x="{box_x + 46}" y="{box_y + 29}" font-family="{MONO}" font-size="12.5" '
        f'fill="{TEXT_2}">{CLONE}</text>'
        f'<g transform="translate({box_x + box_w - 40} {box_y + 17})" fill="none" '
        f'stroke="{TEXT_3}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        f'{copy_icon}</g>'
        f'</g>'
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" \
viewBox="0 0 {W} {H}" role="img" aria-label="{TITLE_1} {TITLE_2}">
  <title>机会翼游 JHYY — {TITLE_1} {TITLE_2}</title>
  <defs>
    <radialGradient id="glowA" cx="0.2" cy="0" r="0.62">
      <stop offset="0%" stop-color="{BRAND_400}" stop-opacity="0.20"/>
      <stop offset="100%" stop-color="{BRAND_400}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glowB" cx="0.8" cy="1" r="0.62">
      <stop offset="0%" stop-color="{BRAND_600}" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="{BRAND_600}" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="card"><rect x="0" y="0" width="{W}" height="{H}" rx="{R_CARD}"/></clipPath>
  </defs>

  <g clip-path="url(#card)">
    <rect x="0" y="0" width="{W}" height="{H}" fill="{BG_ELEV_1}"/>
    <rect x="0" y="0" width="{W}" height="{H}" fill="url(#glowA)"/>
    <rect x="0" y="0" width="{W}" height="{H}" fill="url(#glowB)"/>
    <image x="{CX - calligraphy_w / 2:.2f}" y="60" width="{calligraphy_w:.2f}" \
height="{calligraphy_h}" href="data:image/png;base64,{png}"/>
{t1}
{t2}
{sub}
{button}
{meta}
{clone}
  </g>

  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="{R_CARD - 0.5}" fill="none" \
stroke="{HAIRLINE_2}" stroke-width="1"/>
</svg>
"""


def main() -> int:
    if not CALLIGRAPHY.is_file():
        print(f"[cta-card] 缺 {CALLIGRAPHY}", file=sys.stderr)
        return 1
    svg = build()
    OUT.write_text(svg, encoding="utf-8")
    print(f"[cta-card] 已生成 {OUT.relative_to(ROOT)}  ({len(svg.encode('utf-8')) / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
