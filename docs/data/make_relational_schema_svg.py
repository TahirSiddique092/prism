"""Draw PRISM's relational schema in the Elmasri & Navathe Figure 5.7 style.

Each relation is a row of attribute cells under its name; primary keys are
underlined; each foreign key gets its own colour and an arrow, routed through
lanes on the left, to the primary key it references.

Writes relational-schema-diagram.svg next to this file, which
relational-schema.md shows in section 3. Re-run it after a schema change:

    python docs/data/make_relational_schema_svg.py
"""
from pathlib import Path
from xml.sax.saxutils import escape

OUTPUT = Path(__file__).with_name("relational-schema-diagram.svg")

# (name, [(attribute, is_pk)], [(fk_attribute, target_relation, target_attribute, on_delete)])
RELATIONS = [
    ("users", [("user_id", True), ("name", False), ("email", False), ("password_hash", False), ("created_at", False)], []),
    ("documents", [("doc_id", True), ("user_id", False), ("title", False), ("minio_key", False), ("uploaded_at", False), ("status", False)],
     [("user_id", "users", "user_id", "CASCADE")]),
    ("chunks", [("chunk_id", True), ("doc_id", False), ("chunk_text", False), ("chunk_index", False), ("page_start", False), ("page_end", False)],
     [("doc_id", "documents", "doc_id", "CASCADE")]),
    ("topics", [("topic_id", True), ("name", False)], []),
    ("doc_topics", [("doc_id", True), ("topic_id", True)],
     [("doc_id", "documents", "doc_id", "CASCADE"), ("topic_id", "topics", "topic_id", "CASCADE")]),
    ("search_log", [("log_id", True), ("user_id", False), ("query_text", False), ("searched_at", False)],
     [("user_id", "users", "user_id", "CASCADE")]),
    ("search_results", [("result_id", True), ("log_id", False), ("chunk_id", False), ("rank", False), ("similarity_score", False)],
     [("log_id", "search_log", "log_id", "CASCADE"), ("chunk_id", "chunks", "chunk_id", "CASCADE")]),
    ("deletion_audit", [("audit_id", True), ("doc_id", False), ("deleted_at", False)], []),
]

COLORS = ["#2563eb", "#d97706", "#7c3aed", "#059669", "#dc2626", "#0891b2", "#db2777"]
FONT = "'Segoe UI', Helvetica, Arial, sans-serif"
INK, MUTED, BORDER, CELL = "#111827", "#4b5563", "#475569", "#f8fafc"

CHAR_W = 7.4          # average width of a 13px character
CELL_H = 44
NAME_H = 26           # relation name above its cells
LANE_GAP = 13
TRACK_IN = 13         # spacing of arrows entering a row from below
TRACK_OUT = 22        # spacing of arrows leaving a row
ROW_SPACE = 34        # space between a row's tracks and the next relation name


def cell_width(text):
    return max(96, round(len(text) * CHAR_W + 40))


def build():
    fks = []  # one dict per foreign key
    for r, (name, _, refs) in enumerate(RELATIONS):
        for fk_attr, target, target_attr, action in refs:
            t = next(i for i, rel in enumerate(RELATIONS) if rel[0] == target)
            fks.append({"src": r, "attr": fk_attr, "dst": t, "dst_attr": target_attr, "action": action})

    # Lanes: shorter spans run nearest the boxes, longer ones further out.
    order = sorted(range(len(fks)), key=lambda i: (fks[i]["src"] - fks[i]["dst"], fks[i]["src"]))
    for lane, i in enumerate(order):
        fks[i]["lane"] = lane
        fks[i]["color"] = COLORS[lane % len(COLORS)]
    n_lanes = len(fks)
    x0 = 40 + n_lanes * LANE_GAP + 26  # left edge of every relation

    # Cell geometry per relation
    cells = []
    for name, attrs, _ in RELATIONS:
        x, row = x0, []
        for attr, pk in attrs:
            w = cell_width(attr)
            row.append({"attr": attr, "pk": pk, "x": x, "w": w})
            x += w
        cells.append(row)

    def cell(r, attr):
        return next(c for c in cells[r] if c["attr"] == attr)

    # Tracks below each row: incoming first (nearest the box), then outgoing.
    incoming = {r: [] for r in range(len(RELATIONS))}
    outgoing = {r: [] for r in range(len(RELATIONS))}
    for f in fks:
        incoming[f["dst"]].append(f)
        outgoing[f["src"]].append(f)

    y = 112
    rows_y = []
    for r in range(len(RELATIONS)):
        name_y = y
        box_y = y + NAME_H
        bottom = box_y + CELL_H
        # Incoming: outer lanes take the higher track and enter further left,
        # so they never cross the inner arrows.
        ins = sorted(incoming[r], key=lambda f: -f["lane"])
        for k, f in enumerate(ins):
            f["y_in"] = bottom + 12 + k * TRACK_IN
        in_space = 12 + len(ins) * TRACK_IN if ins else 0
        # Outgoing: cells further right drop further down.
        outs = sorted(outgoing[r], key=lambda f: cell(r, f["attr"])["x"])
        for k, f in enumerate(outs):
            f["y_out"] = bottom + in_space + 16 + k * TRACK_OUT
        out_space = 16 + len(outs) * TRACK_OUT if outs else 0
        rows_y.append((name_y, box_y, bottom))
        y = bottom + max(in_space + out_space, 16) + ROW_SPACE

    # Arrow entry points into a primary-key cell: spread when several arrive.
    for r in range(len(RELATIONS)):
        by_target = {}
        for f in incoming[r]:
            by_target.setdefault(f["dst_attr"], []).append(f)
        for attr, group in by_target.items():
            c = cell(r, attr)
            group.sort(key=lambda f: -f["lane"])  # outer lane enters further left
            for k, f in enumerate(group):
                f["x_in"] = c["x"] + c["w"] / 2 + (k - (len(group) - 1) / 2) * 16

    label_right = 0
    width = max(row[-1]["x"] + row[-1]["w"] for row in cells) + 40
    height = y + 10
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="{FONT}">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        "<defs>" + "".join(
            f'<marker id="arrow{i}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>' for i, c in enumerate(COLORS)
        ) + "</defs>",
        f'<text x="40" y="38" font-size="21" font-weight="700" fill="{INK}">PRISM: Relational Database Schema Diagram</text>',
        f'<text x="40" y="62" font-size="13" fill="{MUTED}">Referential integrity constraints and foreign key references '
        f'(Elmasri &amp; Navathe, Chapter 5, Figure 5.7 format).</text>',
        f'<text x="40" y="80" font-size="13" fill="{MUTED}">Primary keys are underlined. Each foreign key has its own colour, '
        f'with an arrow to the primary key it references.</text>',
    ]

    fk_color = {(f["src"], f["attr"]): f["color"] for f in fks}
    for r, (name, _, _) in enumerate(RELATIONS):
        name_y, box_y, _ = rows_y[r]
        title = name.upper() + (" (M:N association)" if name == "doc_topics" else "")
        out.append(f'<text x="{x0}" y="{name_y + 16}" font-size="15" font-weight="700" fill="{INK}">{escape(title)}</text>')
        for c in cells[r]:
            color = fk_color.get((r, c["attr"]), INK)
            weight = "700" if c["pk"] or (r, c["attr"]) in fk_color else "400"
            deco = ' text-decoration="underline"' if c["pk"] else ""
            out.append(f'<rect x="{c["x"]}" y="{box_y}" width="{c["w"]}" height="{CELL_H}" fill="{CELL}" stroke="{BORDER}" stroke-width="1.5"/>')
            out.append(f'<text x="{c["x"] + c["w"] / 2}" y="{box_y + CELL_H / 2 + 5}" text-anchor="middle" font-size="13" '
                       f'font-weight="{weight}" fill="{color}"{deco}>{escape(c["attr"])}</text>')

    for f in fks:
        lane_x = 40 + (n_lanes - 1 - f["lane"]) * LANE_GAP + 0.5
        src = cell(f["src"], f["attr"])
        sx = src["x"] + src["w"] / 2
        _, _, sb = rows_y[f["src"]]
        _, _, tb = rows_y[f["dst"]]
        color, marker = f["color"], COLORS.index(f["color"])
        points = [(sx, sb), (sx, f["y_out"]), (lane_x, f["y_out"]), (lane_x, f["y_in"]), (f["x_in"], f["y_in"]), (f["x_in"], tb + 1)]
        d = "M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in points)
        out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" marker-end="url(#arrow{marker})"/>')
        # Labels sit right of the row's last foreign-key drop line, level with
        # their own arrow, where no other line runs.
        label = f'{RELATIONS[f["src"]][0]}.{f["attr"]} → {RELATIONS[f["dst"]][0]}.{f["dst_attr"]} (ON DELETE {f["action"]})'
        label_x = max(cell(f["src"], g["attr"])["x"] + cell(f["src"], g["attr"])["w"] / 2
                      for g in outgoing[f["src"]]) + 14
        out.append(f'<text x="{label_x:.1f}" y="{f["y_out"] + 4.5:.1f}" font-size="12" '
                   f'font-weight="600" fill="{color}">{escape(label)}</text>')
        label_right = max(label_right, label_x + len(label) * 6.9)

    out.append("</svg>")
    # Widen the canvas if a label runs past the widest relation.
    needed = max(width, round(label_right) + 30, 760)
    out[0] = out[0].replace(f'width="{width}"', f'width="{needed}"').replace(f'viewBox="0 0 {width} ', f'viewBox="0 0 {needed} ')
    out[1] = out[1].replace(f'width="{width}"', f'width="{needed}"')
    return "\n".join(out)


if __name__ == "__main__":
    OUTPUT.write_text(build())
    print(f"wrote {OUTPUT}")
