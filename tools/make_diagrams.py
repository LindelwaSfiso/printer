"""Generate the report figures for the ESprints project.

One description, two outputs, so the report and the slides always agree:

    docs/diagrams/*.svg   vector, editable in Inkscape / Word / PowerPoint
    docs/diagrams/*.png   2x raster, for pasting into a document

    .venv\\Scripts\\python.exe tools\\make_diagrams.py

Pure standard library + Pillow. No browser, no Graphviz, no extra install.
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "diagrams"

INK = "#18181b"
MUTED = "#71717a"
LINE = "#a1a1aa"
SOFT = "#d4d4d8"
PANEL = "#fafafa"
ACCENT = "#0f766e"
ACCENT_SOFT = "#ecfdf5"
WARN = "#b45309"
WARN_SOFT = "#fffbeb"
RED = "#b91c1c"
RED_SOFT = "#fef2f2"
RED_LINE = "#fecaca"
AMBER_LINE = "#fcd34d"
VIOLET = "#5b21b6"
VIOLET_SOFT = "#f5f3ff"
VIOLET_LINE = "#ddd6fe"
INDIGO = "#4338ca"
INDIGO_SOFT = "#e0e7ff"
FONT_STACK = "'Segoe UI', 'Inter', Arial, sans-serif"


# --------------------------------------------------------------------------- #
# Canvas interface: one drawing API, two renderers
# --------------------------------------------------------------------------- #
class SvgCanvas:
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" '
            f'font-family="{FONT_STACK}">',
            "<defs>"
            f'<marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
            f'markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{LINE}"/></marker>'
            f'<marker id="b" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
            f'markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{INK}"/></marker>'
            "</defs>",
            f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        ]

    def text(self, x, y, value, size=13, weight="400", fill=INK, anchor="middle",
             italic=False, spacing=None):
        value = (value.replace("&", "&amp;").replace("<", "&lt;")
                      .replace(">", "&gt;"))
        style = f'font-size="{size}" font-weight="{weight}" fill="{fill}"'
        if italic:
            style += ' font-style="italic"'
        if spacing:
            style += f' letter-spacing="{spacing}"'
        self.parts.append(
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" {style}>{value}</text>')

    def rect(self, x, y, w, h, fill="#ffffff", stroke=SOFT, width=1.2, rx=0,
             dash=None):
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"{dash_attr}/>')

    def line(self, x1, y1, x2, y2, stroke=LINE, width=1.5, dash=None, arrow=False,
             ink=False):
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        marker = f' marker-end="url(#{"b" if ink else "a"})"' if arrow else ""
        self.parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" '
            f'stroke-width="{width}"{dash_attr}{marker}/>')

    def polygon(self, points, fill="#ffffff", stroke=SOFT, width=1.2):
        pts = " ".join(f"{x},{y}" for x, y in points)
        self.parts.append(
            f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{width}"/>')

    def save(self, path: Path):
        path.write_text("\n".join(self.parts + ["</svg>"]), encoding="utf-8")


class PilCanvas:
    """Same API, drawn with Pillow at `scale` times the SVG size."""

    def __init__(self, width, height, scale=2):
        from PIL import Image, ImageDraw

        self.scale = scale
        self.width, self.height = width, height
        self.image = Image.new("RGB", (int(width * scale), int(height * scale)),
                               "#ffffff")
        self.draw = ImageDraw.Draw(self.image)
        self._fonts = {}

    # -- helpers ---------------------------------------------------------
    def _s(self, value):
        return value * self.scale

    def _font(self, size, weight, italic):
        key = (weight if weight in ("400", "600", "700") else "400", italic)
        if key not in self._fonts:
            self._fonts[key] = self._load_font(size, key)
        return self._fonts[key]

    def _load_font(self, size, key):
        from PIL import ImageFont

        for name in FONT_FILES.get(key, FONT_FILES[("400", False)]):
            candidate = FONT_DIR / name
            if candidate.exists():
                return ImageFont.truetype(str(candidate), int(size * self.scale))
        return ImageFont.load_default()

    def _dash(self, x1, y1, x2, y2, colour, width, dash):
        width = max(1, int(round(width)))
        if not dash:
            self.draw.line([(x1, y1), (x2, y2)], fill=colour, width=width)
            return
        on, off = (float(part) for part in dash.split())
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        if not length:
            return
        ux, uy = (x2 - x1) / length, (y2 - y1) / length
        position = 0.0
        while position < length:
            end = min(position + on, length)
            self.draw.line(
                [(x1 + ux * position, y1 + uy * position),
                 (x1 + ux * end, y1 + uy * end)], fill=colour, width=width)
            position += on + off

    # -- API -------------------------------------------------------------
    def text(self, x, y, value, size=13, weight="400", fill=INK, anchor="middle",
             italic=False, spacing=None):
        font = self._font(size, weight, italic)
        modes = {"middle": "ms", "start": "ls", "end": "rs"}
        self.draw.text((self._s(x), self._s(y)), str(value), font=font, fill=fill,
                       anchor=modes.get(anchor, "ms"))

    def rect(self, x, y, w, h, fill="#ffffff", stroke=SOFT, width=1.2, rx=0,
             dash=None):
        box = [self._s(x), self._s(y), self._s(x + w), self._s(y + h)]
        stroke_colour = stroke if stroke else None
        if dash:
            self._dash_rect(box, stroke or SOFT, self._s(width), dash, rx, fill)
            return
        self.draw.rounded_rectangle(
            box, radius=self._s(rx), fill=fill, outline=stroke_colour,
            width=max(1, int(round(self._s(width)))))

    def _dash_rect(self, box, stroke, width, dash, rx, fill):
        from PIL import ImageDraw

        overlay = ImageDraw.Draw(self.image)
        overlay.rounded_rectangle(box, radius=rx, fill=fill)
        x1, y1, x2, y2 = box
        inset = width / 2
        self._dash(x1 + rx, y1 + inset, x2 - rx, y1 + inset, stroke, width, dash)
        self._dash(x1 + rx, y2 - inset, x2 - rx, y2 - inset, stroke, width, dash)
        self._dash(x1 + inset, y1 + rx, x1 + inset, y2 - rx, stroke, width, dash)
        self._dash(x2 - inset, y1 + rx, x2 - inset, y2 - rx, stroke, width, dash)

    def line(self, x1, y1, x2, y2, stroke=LINE, width=1.5, dash=None, arrow=False,
             ink=False):
        sx1, sy1, sx2, sy2 = (self._s(v) for v in (x1, y1, x2, y2))
        w = max(1, int(round(self._s(width))))
        self._dash(sx1, sy1, sx2, sy2, stroke, w, dash)
        if arrow:
            self._arrowhead(sx1, sy1, sx2, sy2, stroke, self._s(width))

    def _arrowhead(self, x1, y1, x2, y2, colour, width):
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        if not length:
            return
        ux, uy = (x2 - x1) / length, (y2 - y1) / length
        size, half = self._s(9), self._s(3.6)
        base_x, base_y = x2 - ux * size, y2 - uy * size
        self.draw.polygon(
            [(x2, y2), (base_x - uy * half, base_y + ux * half),
             (base_x + uy * half, base_y - ux * half)], fill=colour)

    def polygon(self, points, fill="#ffffff", stroke=SOFT, width=1.2):
        self.draw.polygon([(self._s(x), self._s(y)) for x, y in points], fill=fill,
                          outline=stroke, width=max(1, int(round(self._s(width)))))

    def save(self, path: Path):
        self.image.save(path, "PNG", optimize=True)


# --------------------------------------------------------------------------- #
# Shared higher-level shapes
# --------------------------------------------------------------------------- #
class Figure:
    """Wraps a canvas and adds boxes, arrows, diamonds and titles."""

    def __init__(self, canvas):
        self.c = canvas

    def text(self, *args, **kwargs):
        self.c.text(*args, **kwargs)

    def rect(self, *args, **kwargs):
        self.c.rect(*args, **kwargs)

    def line(self, *args, **kwargs):
        self.c.line(*args, **kwargs)

    def title(self, main, sub=None):
        self.c.text(40, 52, main, size=25, weight="700", anchor="start")
        if sub:
            self.c.text(40, 78, sub, size=12.5, fill=MUTED, anchor="start")

    def box(self, x, y, w, h, title=None, sub=None, fill="#ffffff", stroke=SOFT,
            rx=10, title_size=14, sub_size=11.5, weight="600"):
        self.c.rect(x, y, w, h, fill=fill, stroke=stroke, rx=rx)
        if title:
            self.c.text(x + w / 2, y + h / 2 + (-6 if sub else 5), title,
                        size=title_size, weight=weight)
        if sub:
            self.c.text(x + w / 2, y + h / 2 + 14, sub, size=sub_size, fill=MUTED)

    def group(self, x, y, w, h, label, fill=PANEL):
        self.c.rect(x, y, w, h, fill=fill, stroke=SOFT, rx=14, dash="6 5", width=1.2)
        self.c.text(x + 16, y + 26, label, size=12, weight="700", fill=MUTED,
                    anchor="start")

    def arrow(self, x1, y1, x2, y2, label=None, dashed=False, ink=False,
              label_dx=0, label_dy=0, label_anchor="middle"):
        self.c.line(x1, y1, x2, y2, stroke=INK if ink else LINE, width=1.5,
                    dash="5 4" if dashed else None, arrow=True, ink=ink)
        if label:
            self.c.text((x1 + x2) / 2 + label_dx, (y1 + y2) / 2 - 8 + label_dy,
                        label, size=10.5, fill=MUTED, anchor=label_anchor)

    def diamond(self, cx, cy, w, h, label, sub=None, fill=WARN_SOFT,
                stroke=AMBER_LINE):
        self.c.polygon([(cx, cy - h / 2), (cx + w / 2, cy), (cx, cy + h / 2),
                        (cx - w / 2, cy)], fill=fill, stroke=stroke)
        self.c.text(cx, cy + (-4 if sub else 5), label, size=12.5, weight="600")
        if sub:
            self.c.text(cx, cy + 13, sub, size=10.5, fill=MUTED)

    def note(self, x, y, value):
        self.c.text(x, y, value, size=10.5, fill=MUTED, anchor="start", italic=True)


# --------------------------------------------------------------------------- #
# 1. Block diagram
# --------------------------------------------------------------------------- #
def block_diagram(figure: Figure):
    f = figure
    f.title("Block diagram — ESprints printing service",
            "Final Year Project 2026/2027 · Engineering Society, University of Eswatini")

    f.group(30, 110, 250, 350, "MEMBERS")
    f.box(50, 150, 210, 72, "Phone browser", "upload · history · top-up")
    f.box(50, 240, 210, 72, "Laptop browser", "same portal")
    f.box(50, 330, 210, 72, "Treasurer's browser", "approvals · dashboard")

    f.box(340, 250, 180, 104, "Wi-Fi router", "private LAN, no internet",
          title_size=13.5)

    f.group(580, 110, 440, 610, "DEPARTMENT LAPTOP — ONE MACHINE")
    f.box(600, 150, 400, 74, "Waitress + Django", "portal, auth, pricing, invoices",
          stroke=INK)
    f.box(600, 252, 192, 70, "SQLite (WAL)", "jobs · ledger · invoices")
    f.box(808, 252, 192, 70, "private_media/", "job PDFs · printout")
    f.box(600, 350, 400, 66, "Print worker", "run_worker claims QUEUED jobs",
          fill=ACCENT_SOFT, stroke=ACCENT)
    f.box(600, 444, 400, 66, "OS print spooler", "Windows spooler / CUPS")
    f.box(600, 538, 400, 62, "Desk console + dashboard", "queue, printer, reports")
    f.note(600, 700, "One machine: no cloud, no agent, no inbound ports.")

    f.box(1078, 430, 132, 130, "Printer", "USB", title_size=15)

    f.arrow(280, 216, 340, 280, "Wi-Fi")
    f.arrow(280, 306, 340, 302, "HTTPS")
    f.arrow(520, 302, 580, 302, "HTTP :8000")
    f.arrow(696, 224, 696, 252, None, ink=True)
    f.arrow(904, 224, 904, 252, None, ink=True)
    f.arrow(696, 350, 696, 322, "claim", ink=True, label_dx=34, label_dy=8,
            label_anchor="start")
    f.arrow(800, 416, 800, 444, "PDF + options", ink=True, label_dx=12,
            label_dy=10, label_anchor="start")
    f.arrow(1000, 477, 1078, 477, "USB cable", ink=True)

    f.text(600, 780,
           "Figure 1 · The portal, the queue and the printer all live on the laptop "
           "at the desk.", size=11, fill=MUTED)


# --------------------------------------------------------------------------- #
# 2. Flow diagram
# --------------------------------------------------------------------------- #
def flow_diagram(figure: Figure):
    f = figure
    f.title("Flow diagram — the life of a print job",
            "Every state is recorded; credits are only spent after a successful print")

    cx, w = 430, 420
    left = cx - w // 2

    for y, title, sub in [
        (110, "Member uploads a PDF", "phone or laptop"),
        (216, "Validate the file", "PDF header · size · page count"),
        (322, "Price it from the tariff", "pages × copies × rate, duplex discount"),
    ]:
        f.box(left, y, w, 70, title, sub, title_size=13.5)
        f.arrow(cx, y + 70, cx, y + 106, None, ink=True)

    f.box(left, 428, w, 56, "Reserve the credits", "quoted amount, held not spent",
          title_size=13.5)
    f.arrow(cx, 484, cx, 512, None, ink=True)
    f.diamond(cx, 566, 300, 96, "Enough credits?", "balance − held ≥ cost")
    f.arrow(cx, 614, cx, 652, "yes", ink=True, label_dx=22, label_dy=6,
            label_anchor="start")

    f.box(800, 534, 270, 64, "Blocked", "member tops up first",
          fill=WARN_SOFT, stroke=AMBER_LINE, title_size=13, sub_size=11)
    f.arrow(580, 566, 800, 566, "no", dashed=True)

    f.box(left, 652, w, 62, "QUEUED", "visible on the desk console",
          fill=ACCENT_SOFT, stroke=ACCENT, title_size=13.5)
    f.arrow(cx, 714, cx, 752, "worker claims", ink=True, label_dx=14,
            label_dy=8, label_anchor="start")

    f.box(left, 752, w, 62, "PRINTING", "PDF + options handed to the spooler",
          title_size=13.5)
    f.arrow(cx, 814, cx, 852, None, ink=True)

    f.diamond(cx, 906, 320, 96, "Printer confirmed?", "spooler reports success")
    f.arrow(cx, 954, cx, 992, "yes", ink=True, label_dx=22, label_dy=6,
            label_anchor="start")

    f.box(left, 992, w, 66, "PRINTED · credits captured",
          "one ledger entry, reference job:<id>:capture",
          fill=ACCENT_SOFT, stroke=ACCENT, title_size=13.5)

    f.box(800, 874, 270, 64, "FAILED", "hold released, no charge",
          fill=RED_SOFT, stroke=RED_LINE, title_size=13, sub_size=11)
    f.arrow(590, 906, 800, 906, "no", dashed=True)

    f.box(800, 968, 270, 64, "UNKNOWN", "operator checks the tray",
          fill=VIOLET_SOFT, stroke=VIOLET_LINE, title_size=13, sub_size=11)
    f.arrow(800, 938, 800, 968, None, dashed=True)

    f.arrow(cx, 1058, cx, 1096, None, ink=True)
    f.box(200, 1096, 460, 56, "History, statement and reports",
          "member sees it; the dashboard totals it", title_size=13)

    f.note(40, 1160, "Nothing is charged unless the print succeeds — a failure or a "
                     "cancellation only releases the reservation.")


# --------------------------------------------------------------------------- #
# 3. Gantt chart
# --------------------------------------------------------------------------- #
TASKS = [
    ("Requirements, literature review, use cases", 0.0, 1.0, "design"),
    ("Hardware selection and procurement", 0.0, 1.2, "hardware"),
    ("Architecture, ERD and database design", 0.3, 1.2, "design"),
    ("Environment setup, accounts and roles", 0.8, 1.2, "build"),
    ("Credit ledger and subscription engine", 1.6, 1.4, "build"),
    ("PDF upload, validation and tariff", 2.2, 1.2, "build"),
    ("Print queue and printer integration", 2.6, 1.6, "build"),
    ("Manual top-up invoices and approval", 3.2, 1.3, "build"),
    ("Admin dashboard and reports", 3.8, 1.2, "build"),
    ("Testing, billing matrix and UAT", 4.2, 1.2, "test"),
    ("Report writing and corrections", 4.4, 1.4, "docs"),
    ("Final demonstration and submission", 5.2, 0.8, "docs"),
]
COLOURS = {
    "design": ("#e4e4e7", "#52525b"),
    "hardware": ("#fef3c7", WARN),
    "build": ("#ccfbf1", ACCENT),
    "test": (INDIGO_SOFT, INDIGO),
    "docs": ("#f4f4f5", "#3f3f46"),
}
MILESTONES = [(0.5, "Presentation 1"), (3.0, "Presentation 2"), (5.6, "Submission")]
MONTHS = ["Nov 2026", "Dec", "Jan 2027", "Feb", "Mar", "Apr"]


def gantt_chart(figure: Figure):
    f = figure
    left, top, width = 470, 150, 900
    row_h = 40
    col = width / 6
    rows_bottom = top + row_h * len(TASKS)

    f.title("Project timeline — six months (Gantt chart)",
            "Engineering Society printing service · November 2026 to April 2027")

    for index, name in enumerate(MONTHS):
        x = left + index * col
        if index % 2 == 0:
            f.rect(x, top - 10, col, row_h * len(TASKS) + 10, fill=PANEL,
                   stroke=PANEL, width=0)
        f.line(x, top - 10, x, rows_bottom, stroke="#e4e4e7", width=1)
        f.text(x + col / 2, top - 22, name, size=12, weight="600", fill=MUTED)
    f.line(left + width, top - 10, left + width, rows_bottom, stroke="#e4e4e7",
           width=1)

    for index, (name, start, duration, kind) in enumerate(TASKS):
        y = top + index * row_h
        if index % 2 == 0:
            f.rect(30, y, left + width - 30, row_h, fill="#fcfcfc",
                   stroke="#fcfcfc", width=0)
        f.text(40, y + row_h / 2 + 4, name, size=12.5, anchor="start")
        fill, stroke = COLOURS[kind]
        f.rect(left + start * col, y + 9, duration * col, row_h - 18, fill=fill,
               stroke=stroke, rx=5)

    for position, label in MILESTONES:
        x = left + position * col
        f.line(x, top - 10, x, rows_bottom + 6, stroke=INK, width=1, dash="4 4")
        f.c.polygon([(x, rows_bottom + 8), (x + 7, rows_bottom + 17),
                     (x, rows_bottom + 26), (x - 7, rows_bottom + 17)],
                    fill=INK, stroke=INK)
        f.text(x, rows_bottom + 44, label, size=11, weight="600")

    legend_y = rows_bottom + 74
    for index, (kind, label) in enumerate([
            ("design", "Design"), ("hardware", "Hardware"),
            ("build", "Implementation"), ("test", "Testing"),
            ("docs", "Report & demo")]):
        x = 40 + index * 168
        fill, stroke = COLOURS[kind]
        f.rect(x, legend_y, 16, 10, fill=fill, stroke=stroke, rx=3)
        f.text(x + 24, legend_y + 9, label, size=11, fill=MUTED, anchor="start")


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
FIGURES = {
    "block_diagram": (block_diagram, 1240, 820),
    "flow_diagram": (flow_diagram, 1120, 1180),
    "gantt_chart": (gantt_chart, 1460, 880),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Writing figures to {OUT}")
    for name, (draw, width, height) in FIGURES.items():
        canvas = SvgCanvas(width, height)
        draw(Figure(canvas))
        target = OUT / f"{name}.svg"
        canvas.save(target)
        print(f"  {name:<14} {width}x{height}  {target.stat().st_size:>6,} bytes  "
              f"{len(canvas.parts)} elements")


if __name__ == "__main__":
    main()
