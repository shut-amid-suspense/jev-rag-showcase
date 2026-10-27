"""Render the README architecture figure; no image service or browser required.

Usage: python scripts/render_architecture.py --png
SVG generation uses the standard library; PNG export uses PyMuPDF, which is an
existing application dependency. This diagram documents implemented behavior.
"""
import argparse
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/diagrams'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--png', action='store_true')
    args = parser.parse_args()
    parts = ['''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="870" viewBox="0 0 1400 870" role="img" aria-labelledby="title desc">
<title id="title">Jev RAG: three retrieval workflows</title>
<desc id="desc">All modes share a page-labelled document index. Fast sends five hybrid-search passages directly to the answer model. Standard expands queries and uses Jev to rank a pool down to five. Thorough uses Jev during agent searches and can repeat or read a full page, within six model turns.</desc>
<rect width="1400" height="870" fill="#ffffff"/>
''']

    def text(x, y, value, cls='body', anchor=None):
        extra = f' text-anchor="{anchor}"' if anchor else ''
        size = next((size for name, size in [('overline', 13), ('small', 16), ('label', 20), ('body', 19)] if name in cls.split()), 19)
        color = '#546780' if 'muted' in cls else '#172b45'
        weight = '700' if 'label' in cls or 'overline' in cls else '400'
        spacing = ' letter-spacing="1.7"' if 'overline' in cls else ''
        parts.append(f'<text x="{x}" y="{y}" font-family="Arial,Helvetica,sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}"{spacing}{extra}>{escape(value)}</text>')

    def rect(x, y, w, h, fill, stroke='#d8e1eb', radius=14):
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>')

    def arrow(x1, y1, x2, y2):
        parts.append(f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="#718198" stroke-width="2"/>')
        parts.append(f'<polyline points="{x2-7},{y2-5} {x2},{y2} {x2-7},{y2+5}" fill="none" stroke="#718198" stroke-width="2"/>')

    def box(x, y, w, title, subtitle, kind='local'):
        fill, stroke = {'local': ('#f4f7fa', '#ced9e5'),
                        'model': ('#eef2ff', '#b8c6f1'),
                        'jev': ('#e2f7ee', '#55b99a')}[kind]
        rect(x, y, w, 76, fill, stroke)
        text(x+w/2, y+31, title, 'label', 'middle')
        text(x+w/2, y+56, subtitle, 'small muted', 'middle')

    text(56, 48, 'JEV RAG / IMPLEMENTED ARCHITECTURE', 'overline muted')
    parts.append('<text x="56" y="94" font-family="Arial,Helvetica,sans-serif" font-size="36" font-weight="700" fill="#172b45">One document. Three retrieval workflows.</text>')
    text(56, 124, 'Jev selects evidence. The generative model writes the final answer.', 'body muted')
    legend = [(900, '#f4f7fa', 'Local retrieval'), (1070, '#e2f7ee', 'Jev'), (1170, '#eef2ff', 'Generation')]
    for x, fill, label in legend:
        rect(x, 33, 18, 18, fill, '#b8c7d8', 4)
        text(x+27, 48, label, 'small muted')

    rect(56, 160, 180, 100, '#f4f7fa')
    text(146, 201, 'Upload a PDF', 'label', 'middle')
    text(146, 230, 'Extract + label pages', 'small muted', 'middle')
    arrow(242, 210, 269, 210)
    rect(278, 160, 1066, 100, '#f7fafc')
    text(302, 188, 'SHARED DOCUMENT INDEX', 'overline muted')
    text(302, 217, 'Page-labelled passages + keyword index + embedding vectors', 'label')
    text(302, 242, 'Embeddings via OpenRouter; search runs locally. Validated JSON cache keyed by PDF content.', 'small muted')

    for y, h, fill in [(292, 116, '#f8fafc'), (432, 116, '#f0faf6'), (572, 188, '#f6f5fc')]:
        rect(56, y, 1288, h, fill)

    text(82, 329, 'FAST', 'overline muted')
    text(82, 359, 'Single search', 'label')
    text(82, 385, 'Baseline: no Jev', 'small muted')
    box(278, 312, 270, 'Hybrid search', 'Keywords + vector similarity')
    arrow(554, 350, 596, 350)
    box(606, 312, 250, 'Take top 5 passages', 'One fixed retrieval pass')
    arrow(862, 350, 904, 350)
    box(914, 312, 402, 'Generate an answer', 'Selected passages + source IDs', 'model')

    text(82, 469, 'STANDARD', 'overline muted')
    text(82, 499, 'Expand + rank', 'label')
    text(82, 525, 'One Jev call', 'small muted')
    xs, widths = [278, 544, 810, 1076], [236, 236, 236, 240]
    box(xs[0], 452, widths[0], 'Generate terms', 'Up to 6 search terms', 'model')
    box(xs[1], 452, widths[1], 'Hybrid candidate pool', 'Combine up to 40 passages')
    box(xs[2], 452, widths[2], 'Jev ranks passages', 'Keep the best 5', 'jev')
    box(xs[3], 452, widths[3], 'Generate an answer', 'From selected evidence', 'model')
    for x, w, next_x in zip(xs, widths, xs[1:]):
        arrow(x+w+4, 490, next_x-8, 490)

    text(82, 609, 'THOROUGH', 'overline muted')
    text(82, 639, 'Iterate on evidence', 'label')
    text(82, 665, 'Up to 6 model turns', 'small muted')
    box(xs[0], 592, widths[0], 'Agent chooses action', 'Search path shown here', 'model')
    box(xs[1], 592, widths[1], 'Hybrid shortlist', 'Up to 20 passages')
    box(xs[2], 592, widths[2], 'Jev ranks passages', 'Return the best 3', 'jev')
    box(xs[3], 592, widths[3], 'Agent evaluates next', 'Answer or continue', 'model')
    for x, w, next_x in zip(xs, widths, xs[1:]):
        arrow(x+w+4, 630, next_x-8, 630)
    parts.append('<path d="M1196,675 L1196,706 L396,706 L396,675" fill="none" stroke="#718198" stroke-width="2"/>')
    parts.append('<polyline points="391,682 396,675 401,682" fill="none" stroke="#718198" stroke-width="2"/>')
    text(796, 698, 'The agent may search again; read_page can bypass ranking.', 'small muted', 'middle')
    text(278, 741, 'Six turns limit model iterations, not the total number of tool calls or a monetary budget.', 'small muted')

    text(56, 802, 'Evidence coverage and answer completeness are evaluated separately.', 'label')
    text(56, 832, 'Gemini generated the recorded answers. Optional Cerebras/Qwen generation is supported but was not benchmarked here.', 'small muted')
    parts.append('</svg>')
    OUT.mkdir(parents=True, exist_ok=True)
    svg = OUT / 'search-modes.svg'
    svg.write_text('\n'.join(parts)+'\n')
    if args.png:
        import pymupdf
        with pymupdf.open(stream=svg.read_bytes(), filetype='svg') as document:
            document[0].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False).save(OUT / 'search-modes.png')
    print('Rendered '+str(svg.relative_to(ROOT)))


if __name__ == '__main__':
    main()
