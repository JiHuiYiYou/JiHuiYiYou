#!/usr/bin/env python3
"""生成 profile 的 CTA 卡片 —— 官网那张「Final CTA」的**同款版式**。

**为什么要有这张卡**：profile 是一扇**门**，点进去就是官网。seckinyasar 的做法是
「一张 OG 图 + 一句 pitch」，所以我们把官网 `en/compiler/index.html` 的
「Final CTA」那张卡（`Write the next / hello.jhyy.`）搬过来当 profile 的门面 ——
看的人认出这是同一个产品，点一下就到官网。

**跟官网那张的差别**（用户定的）：
  - 文字全换（官网那张讲「下载编译器」，这张讲「这门语言本身」）
  - 底下**一排按钮收成一个**「Click Here」—— 整张图本身就是链接，按钮只是提示

**版式是照抄的，不是"差不多"**：canvas 1168×682、圆角 32、padding 96/56/88、
标题 76.8px / line-height 0.98 / letter-spacing -0.02em、正文 16.8px、
按钮 60 高、事实行 13px、clone 框 12.5px 等，全部取自官网那张卡的**实测值**
（在真实官网页面上量出来的，不是猜的）。设计令牌也全抄 `main.css` 的
`--brand-*` / `--text-*` / `--bg-*` / `--hairline-*` / `--r-*`。

**所有文字都转成 path**：SVG 走 camo 渲染时不能引用外部字体文件，也不该指望
渲染机装了同款字体 ⇒ 用 fontTools 把字形轮廓描出来。顺带好处：**字宽是我自己
算的**（同款字体的 advance width），所以代码 chip 的底框、事实行的下划线、
按钮的宽度都能精确落位 —— 不靠猜字宽。

**字体从哪来**：默认读官网仓 `assets/fonts/`（OFL 允许再分发，但那是官网的资产，
不复制进 profile 仓）。`--font-dir` 可以指到别处。

**用法**：
    python tools/make_cta_card.py            # → assets/cta-card.svg
    python tools/make_cta_card.py --font-dir <dir>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fontTools.misc.transform import Transform
from fontTools.pens.basePen import BasePen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "cta-card.svg"
DEFAULT_FONT_DIR = ROOT.parent / "JiHuiYiYou-website" / "assets" / "fonts"

# ── 官网的令牌（JiHuiYiYou-website/assets/css/main.css） ──────────────────
BG_ELEV_1 = "#131316"
BG_ELEV_2 = "#1a1a1f"
BG_DEEP = "#0a0a0a"
TEXT_1 = "#fafafa"
TEXT_2 = "#b4b4ba"
TEXT_3 = "#75757d"
TEXT_4 = "#48484e"
BRAND_200 = "#66e9cc"
BRAND_300 = "#1de9c0"
BRAND_400 = "#00d4aa"
BRAND_500 = "#00a886"
BRAND_600 = "#007a66"
HAIRLINE = "rgba(255,255,255,0.06)"
HAIRLINE_2 = "rgba(255,255,255,0.10)"

# ── 版式（官网那张卡的实测值，真实像素） ─────────────────────────────────
W, H = 1168, 682
R_CARD = 32
PAD_TOP, PAD_X, PAD_BOT = 96, 56, 88

TITLE_SIZE = 76.8
TITLE_TRACK = -0.02 * TITLE_SIZE
TITLE1_Y = 163
TITLE2_Y = 238

SUB_SIZE = 16.8
SUB_LH = 26.04
SUB_MAX_W = 540
CODE_SIZE = 15.12

BTN_Y = 374
BTN_H = 60
BTN_FONT = 15
BTN_PAD_L, BTN_PAD_R, BTN_GAP = 28, 16, 10
ICON = 28

META_Y = 456
META_SIZE = 13

CLONE_Y = 532
CLONE_H = 60
CLONE_FONT = 12.5

# ── 文案（英文为主） ────────────────────────────────────────────────────
TITLE_1 = "A systems language"
TITLE_2 = "that compiles itself."
SUB_PARTS = [
    ("text", "From "),
    ("code", "git clone"),
    ("text", " to your first compiled artifact, or just click through to the site "
             "— one language, four projects, all in one place."),
]
BUTTON = "Click Here"
META = [
    ("teal", "v4.1.5"),
    ("text", "stable"),
    ("text", "amd64"),
    ("text", "281 / 301 PASS"),
    ("link", "Changelog"),
    ("link", "Website"),
    ("link", "the whole family"),
]
CLONE = "git clone https://github.com/JiHuiYiYou/JiHuiYiYou-compiler && cd JiHuiYiYou-compiler"


# ══════════════════════════════════════════════════════════════════════════
# 字体：字宽 + 字形轮廓
# ══════════════════════════════════════════════════════════════════════════
class SvgPathPen(BasePen):
    """把字形轮廓收成一条 SVG path 的 data。"""

    def __init__(self, glyphSet):
        super().__init__(glyphSet)
        self.parts: list[str] = []

    def _moveTo(self, pt):
        self.parts.append(f"M{pt[0]:.1f} {pt[1]:.1f}")

    def _lineTo(self, pt):
        self.parts.append(f"L{pt[0]:.1f} {pt[1]:.1f}")

    def _curveToOne(self, p1, p2, p3):
        self.parts.append(
            f"C{p1[0]:.1f} {p1[1]:.1f} {p2[0]:.1f} {p2[1]:.1f} {p3[0]:.1f} {p3[1]:.1f}")

    def _closePath(self):
        self.parts.append("Z")

    def _endPath(self):
        pass

    def get_path(self) -> str:
        return " ".join(self.parts)


class Font:
    """一个字族：能报字宽，也能把一行字描成 path。"""

    def __init__(self, path: Path):
        self.tt = TTFont(path)
        self.gs = self.tt.getGlyphSet()
        self.cmap = self.tt.getBestCmap()
        self.upm = self.tt["head"].unitsPerEm

    def _glyph(self, ch):
        return self.cmap.get(ord(ch))

    def width(self, text: str, size: float, tracking: float = 0.0) -> float:
        total = 0.0
        for ch in text:
            gn = self._glyph(ch)
            if gn is None:
                continue
            total += self.gs[gn].width * size / self.upm + tracking
        return total

    def path(self, text: str, size: float, tracking: float = 0.0) -> tuple[str, float]:
        sc = size / self.upm
        pen = SvgPathPen(self.gs)
        x = 0.0
        for ch in text:
            gn = self._glyph(ch)
            if gn is None:
                continue
            tp = TransformPen(pen, Transform(sc, 0, 0, -sc, x, 0))
            self.gs[gn].draw(tp)
            x += self.gs[gn].width * sc + tracking
        return pen.get_path(), x


def draw(font: Font, text: str, size: float, x: float, baseline: float, fill: str,
         tracking: float = 0.0, anchor: str = "start") -> tuple[str, float]:
    """画一行描边文字。返回 (svg 片段, 宽度)。"""
    if not text:
        return "", 0.0
    d, w = font.path(text, size, tracking)
    if anchor == "middle":
        x -= w / 2
    elif anchor == "end":
        x -= w
    return (f'<path d="{d}" transform="translate({x:.2f} {baseline:.2f})" '
            f'fill="{fill}"/>'), w


# ══════════════════════════════════════════════════════════════════════════
# 各部件
# ══════════════════════════════════════════════════════════════════════════
def glow_defs() -> str:
    """官网的 `.cta-glow`：两个 radial-gradient。

    `radial-gradient(circle at 20% 0%, c, transparent 50%)` 里的半径是
    「到最远角的距离」—— SVG 的 radialGradient 用 userSpace 的 r 表达。
    """
    import math
    c1 = (0.20 * W, 0.0)
    c2 = (0.80 * W, float(H))
    corners = [(0, 0), (W, 0), (0, H), (W, H)]
    r1 = max(math.dist(c1, c) for c in corners)
    r2 = max(math.dist(c2, c) for c in corners)
    return f"""    <radialGradient id="glowA" gradientUnits="userSpaceOnUse" \
cx="{c1[0]:.1f}" cy="{c1[1]:.1f}" r="{r1:.1f}">
      <stop offset="0%" stop-color="{BRAND_400}" stop-opacity="0.20"/>
      <stop offset="50%" stop-color="{BRAND_400}" stop-opacity="0"/>
      <stop offset="100%" stop-color="{BRAND_400}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glowB" gradientUnits="userSpaceOnUse" \
cx="{c2[0]:.1f}" cy="{c2[1]:.1f}" r="{r2:.1f}">
      <stop offset="0%" stop-color="{BRAND_600}" stop-opacity="0.18"/>
      <stop offset="50%" stop-color="{BRAND_600}" stop-opacity="0"/>
      <stop offset="100%" stop-color="{BRAND_600}" stop-opacity="0"/>
    </radialGradient>
"""


def build_sub(sans: Font, serif: Font) -> tuple[str, int]:
    """正文：≤540px 一行，自动折行；`git clone` 带代码 chip。"""
    # 把正文拆成「词」序列，chip 是一个不可拆的原子
    words: list[tuple[str, str]] = []
    for kind, chunk in SUB_PARTS:
        if kind == "code":
            words.append(("code", chunk))
            continue
        first = True
        for w in chunk.split(" "):
            if not first:
                words.append(("text", " "))
            words.append(("text", w))
            first = False

    lines: list[list[tuple[str, str]]] = [[]]
    cur = 0.0
    for kind, txt in words:
        size = CODE_SIZE if kind == "code" else SUB_SIZE
        w = (sans.width(txt, size) if kind == "text"
             else sans.width(txt, CODE_SIZE) + 12 + 3)
        if cur + w > SUB_MAX_W and lines[-1] and txt != " ":
            lines.append([])
            cur = 0.0
            if txt == " ":
                continue
        lines[-1].append((kind, txt))
        cur += w

    out: list[str] = []
    y = SUB_LH * 0 + 301  # 第一行基线
    for i, line in enumerate(lines):
        # 先量这一行的总宽，再居中
        widths = []
        for kind, txt in line:
            if kind == "code":
                widths.append(sans.width(txt, CODE_SIZE) + 12 + 3)
            else:
                widths.append(sans.width(txt, SUB_SIZE))
        total = sum(widths)
        x = (W - total) / 2
        for (kind, txt), w in zip(line, widths):
            if kind == "code":
                chip_w = sans.width(txt, CODE_SIZE) + 12
                out.append(f'<rect x="{x:.2f}" y="{y - 17:.2f}" width="{chip_w:.2f}" '
                           f'height="24" rx="5" fill="{BG_ELEV_2}" '
                           f'stroke="{HAIRLINE}" stroke-width="1.5"/>')
                frag, _ = draw(sans, txt, CODE_SIZE, x + 6, y, BRAND_200)
                out.append(frag)
                x += w
            else:
                frag, _ = draw(sans, txt, SUB_SIZE, x, y, TEXT_2)
                out.append(frag)
                x += w
        y += SUB_LH
    return "\n".join(out), len(lines)


def build_button(sans: Font) -> str:
    """一颗按钮（官网那排收成的一颗）。"""
    label_w = sans.width(BUTTON, BTN_FONT)
    btn_w = BTN_PAD_L + label_w + BTN_GAP + ICON + BTN_PAD_R
    x0 = (W - btn_w) / 2
    label_x = x0 + BTN_PAD_L
    icon_cx = x0 + BTN_PAD_L + label_w + BTN_GAP + ICON / 2
    icon_cy = BTN_Y + BTN_H / 2
    frag, _ = draw(sans, BUTTON, BTN_FONT, label_x, BTN_Y + 37, "#050505")
    arrow = ('<path d="M7 17 L17 7 M9 7 L17 7 L17 15" fill="none" stroke="#050505" '
             'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')
    return f"""    <rect x="{x0:.2f}" y="{BTN_Y}" width="{btn_w:.2f}" height="{BTN_H}" rx="{BTN_H / 2}" \
fill="{BRAND_400}" stroke="{BRAND_500}" stroke-width="1"/>
    {frag}
    <circle cx="{icon_cx:.2f}" cy="{icon_cy:.2f}" r="{ICON / 2}" fill="rgba(5,5,5,0.18)"/>
    <g transform="translate({icon_cx - 7:.2f} {icon_cy - 7:.2f})">{arrow}</g>"""


def build_meta(sans: Font) -> str:
    """事实行：teal 的版本号 + 普通项 + 带下划线的链接项。"""
    sep = " · "
    sep_w = sans.width(sep, META_SIZE)
    items = []
    for kind, txt in META:
        w = sans.width(txt, META_SIZE)
        items.append((kind, txt, w))
    total = sum(w for _, _, w in items) + sep_w * (len(items) - 1)
    x = (W - total) / 2
    out: list[str] = []
    for i, (kind, txt, w) in enumerate(items):
        if i:
            frag, _ = draw(sans, sep, META_SIZE, x, META_Y + 12, TEXT_4)
            out.append(frag)
            x += sep_w
        if kind == "teal":
            frag, _ = draw(sans, txt, META_SIZE, x, META_Y + 12, BRAND_300)
        elif kind == "link":
            frag, _ = draw(sans, txt, META_SIZE, x, META_Y + 12, TEXT_1)
            out.append(f'<rect x="{x:.2f}" y="{META_Y + 15:.2f}" width="{w:.2f}" height="1" '
                       f'fill="{HAIRLINE}"/>')
        else:
            frag, _ = draw(sans, txt, META_SIZE, x, META_Y + 12, TEXT_2)
        out.append(frag)
        x += w
    return "\n".join(out)


def build_clone(mono: Font) -> str:
    """clone 命令框。"""
    cmd_w = mono.width(CLONE, CLONE_FONT)
    prompt_w = mono.width("$", CLONE_FONT)
    box_w = 22 + prompt_w + 12 + cmd_w + 12 + ICON + 18
    x0 = (W - box_w) / 2
    y = CLONE_Y + 34
    cmd, _ = draw(mono, CLONE, CLONE_FONT, x0 + 22 + prompt_w + 12, y, TEXT_2)
    prompt, _ = draw(mono, "$", CLONE_FONT, x0 + 22, y, BRAND_400)
    icon = ('<rect x="9" y="9" width="13" height="13" rx="2"/>'
            '<path d="M5 15 H4 a2 2 0 0 1 -2 -2 V4 a2 2 0 0 1 2 -2 h9 a2 2 0 0 1 2 2 v1"/>')
    cx = x0 + box_w - 18 - ICON / 2
    cy = CLONE_Y + CLONE_H / 2
    return f"""    <rect x="{x0:.2f}" y="{CLONE_Y}" width="{box_w:.2f}" height="{CLONE_H}" \
rx="{CLONE_H / 2}" fill="{BG_DEEP}" stroke="{HAIRLINE_2}" stroke-width="1.5"/>
    {prompt}
    {cmd}
    <circle cx="{cx:.2f}" cy="{cy:.2f}" r="{ICON / 2}" fill="{BG_ELEV_2}"/>
    <g transform="translate({cx - 6:.2f} {cy - 6:.2f})" fill="none" stroke="{TEXT_3}" \
stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">{icon}</g>"""


def build(font_dir: Path) -> str:
    serif = Font(font_dir / "instrument-serif-400-normal-latin.woff2")
    serif_i = Font(font_dir / "instrument-serif-400-italic-latin.woff2")
    sans = Font(font_dir / "space-grotesk-400-normal-latin.woff2")
    mono = Font(font_dir / "jetbrains-mono-400-normal-latin.woff2")

    t1, _ = draw(serif, TITLE_1, TITLE_SIZE, W / 2, TITLE1_Y, TEXT_1,
                 tracking=TITLE_TRACK, anchor="middle")
    t2, _ = draw(serif_i, TITLE_2, TITLE_SIZE, W / 2, TITLE2_Y, BRAND_300,
                 tracking=TITLE_TRACK, anchor="middle")
    sub, sub_lines = build_sub(sans, serif)
    meta = build_meta(sans)
    button = build_button(sans)
    clone = build_clone(mono)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" \
viewBox="0 0 {W} {H}" role="img" \
aria-label="机会翼游 JHYY — {TITLE_1} {TITLE_2}. Click to visit the official site.">
  <title>机会翼游 JHYY — {TITLE_1} {TITLE_2}</title>
  <defs>
{glow_defs()}    <clipPath id="card"><rect x="0" y="0" width="{W}" height="{H}" rx="{R_CARD}"/></clipPath>
  </defs>

  <g clip-path="url(#card)">
    <rect x="0" y="0" width="{W}" height="{H}" fill="{BG_ELEV_1}"/>
    <rect x="0" y="0" width="{W}" height="{H}" fill="url(#glowA)"/>
    <rect x="0" y="0" width="{W}" height="{H}" fill="url(#glowB)"/>
    {t1}
    {t2}
{sub}
{button}
{meta}
{clone}
  </g>

  <rect x="0.75" y="0.75" width="{W - 1.5}" height="{H - 1.5}" rx="{R_CARD - 0.75}" fill="none" \
stroke="{HAIRLINE_2}" stroke-width="1.5"/>
</svg>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--font-dir", type=Path, default=DEFAULT_FONT_DIR)
    args = ap.parse_args()
    if not args.font_dir.is_dir():
        print(f"[cta-card] 找不到字体目录 {args.font_dir} —— "
              f"用 --font-dir 指到官网的 assets/fonts/", file=sys.stderr)
        return 1
    svg = build(args.font_dir)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg, encoding="utf-8")
    print(f"[cta-card] 已生成 {OUT.relative_to(ROOT)}  "
          f"({len(svg.encode('utf-8')) / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
