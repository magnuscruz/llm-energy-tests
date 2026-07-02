#!/usr/bin/env python3
"""Simple MD/TXT -> PDF converter using reportlab.

Usage: python make_pdf.py input.md output.pdf
"""
import sys
import textwrap
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm


def text_to_pdf(in_path, out_path, page_size=A4, font_name='Courier', font_size=10):
    width, height = page_size
    c = canvas.Canvas(out_path, pagesize=page_size)
    c.setFont(font_name, font_size)
    left_margin = 15 * mm
    right_margin = 15 * mm
    top_margin = 15 * mm
    bottom_margin = 15 * mm
    max_width = width - left_margin - right_margin
    line_height = font_size * 1.2
    y = height - top_margin

    with open(in_path, 'r', encoding='utf-8') as f:
        for raw_line in f:
            line = raw_line.rstrip('\n')
            # wrap long lines
            wrapped = textwrap.wrap(line, width= int(max_width / (font_size * 0.6)) ) or ['']
            for part in wrapped:
                if y - line_height < bottom_margin:
                    c.showPage()
                    c.setFont(font_name, font_size)
                    y = height - top_margin
                c.drawString(left_margin, y, part)
                y -= line_height

    c.save()


def main():
    if len(sys.argv) < 3:
        print('Usage: make_pdf.py input.md output.pdf')
        sys.exit(2)
    in_path = sys.argv[1]
    out_path = sys.argv[2]
    text_to_pdf(in_path, out_path)


if __name__ == '__main__':
    main()
