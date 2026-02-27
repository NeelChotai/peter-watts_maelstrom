#!/usr/bin/env python3
"""
Convert Maelstrom HTML source to Standard Ebooks format.

Source: /tmp/pw/Maelstrom/MAELzip.htm (windows-1252)
Target: /home/neel/projects/standardebooks/peter-watts_maelstrom/src/epub/text/

Structure:
  Frontmatter:
    - Dedication ("For Laurie" + Shakespeare quote)
    - Epigraph (Job 40:15, Isaiah 40:6)
    - Halftitlepage
  Bodymatter:
    - Prelude: Messiah
    - Part 1: Volvox (32 chapters: Mermaid ... Warhorse)
    - Part 2: Physalia (22 chapters: Zeus ... Crucifixion, with Spiders)
    - Part 3: Anthopleura (11 chapters: Mug Shot ... A Niche)
    - Epilog: Sleeping by Firelight
  Backmatter:
    - Endnotes (36 endnotes)
    - Notes and References (author essay with endnote refs)
    - Acknowledgments
"""

import re
import html as html_mod
import os
import sys

SOURCE = '/tmp/pw/Maelstrom/MAELzip.htm'
TARGET = '/home/neel/projects/standardebooks/peter-watts_maelstrom/src/epub/text'

# ============================================================
# Read and decode source
# ============================================================
with open(SOURCE, 'rb') as f:
    raw = f.read()
src = raw.decode('windows-1252')
src = src.replace('\r\n', '\n').replace('\r', '\n')

# ============================================================
# Symbol / special font replacement (do this on raw HTML)
# ============================================================
# Symbol font wrapped chars: <FONT SIZE=3><FONT FACE="Symbol">1</FONT></FONT> -> degree
src = re.sub(r'<FONT[^>]*><FONT[^>]*FACE="Symbol"[^>]*>1</FONT></FONT>', '\u00b0', src)
src = re.sub(r'<FONT[^>]*FACE="Symbol"[^>]*>1</FONT>', '\u00b0', src)

# Symbol font entities
src = src.replace('&#61616;', '\u00b0')   # degree
src = src.replace('&#61668;', '\u2122')   # TM
src = src.replace('&#61541;', '\u03b5')   # epsilon
src = src.replace('&#61555;', '\u03c3')   # sigma
src = src.replace('&#61549;', '\u03bc')   # mu
src = src.replace('&#61472;', '')          # Symbol space -> nothing
src = src.replace('&#61538;', '\u03b2')   # Symbol b -> beta
src = src.replace('&#61603;', '\u2264')   # Symbol <=

# Remove remaining Symbol font wrappers
src = re.sub(r'<FONT[^>]*FACE="Symbol[^"]*"[^>]*>(.*?)</FONT>', r'\1', src, flags=re.DOTALL)

# Remove Albertus Extra Bold font wrappers
src = re.sub(r'<FONT FACE="Albertus Extra Bold[^"]*"[^>]*>(.*?)</FONT>', r'\1', src, flags=re.DOTALL)
# Remove Tahoma font wrappers
src = re.sub(r'<FONT FACE="Tahoma[^"]*"[^>]*>(.*?)</FONT>', r'\1', src, flags=re.DOTALL)
# Remove Verdana font wrappers
src = re.sub(r'<FONT FACE="Verdana[^"]*"[^>]*>(.*?)</FONT>', r'\1', src, flags=re.DOTALL)

# Eszett (ß) in "ßehemoth" -> Behemoth
src = src.replace('\u00dfehemoth', 'Behemoth')
src = src.replace('\u03b2ehemoth', 'Behemoth')

# ============================================================
# Parse into header-delimited sections
# ============================================================
header_re = re.compile(r'<H([23])\s+CLASS="western"[^>]*>(.*?)</H\1>', re.DOTALL | re.IGNORECASE)
headers = []
for m in header_re.finditer(src):
    lvl = int(m.group(1))
    inner = m.group(2)
    anchor_m = re.search(r'name="([^"]+)"', inner)
    anchor = anchor_m.group(1) if anchor_m else None
    title = re.sub(r'<[^>]+>', '', inner).strip()
    title = ' '.join(title.split())
    # Clean comma at end of "Fables of the Reconstruction,"
    headers.append({
        'level': lvl, 'anchor': anchor, 'title': title,
        'start': m.start(), 'end': m.end()
    })

sections = {}
for i, h in enumerate(headers):
    end = headers[i+1]['start'] if i+1 < len(headers) else len(src)
    sections[h['anchor'] or h['title']] = {
        **h,
        'body': src[h['end']:end]
    }

# ============================================================
# XHTML template
# ============================================================
XHTML = '''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" epub:prefix="z3998: http://www.daisy.org/z3998/2012/vocab/structure/, se: https://standardebooks.org/vocab/1.0" xml:lang="en-US">
\t<head>
\t\t<title>{title}</title>
\t\t<link href="../css/core.css" rel="stylesheet" type="text/css"/>
\t\t<link href="../css/local.css" rel="stylesheet" type="text/css"/>
\t</head>
\t<body epub:type="{bodytype}">
{body}
\t</body>
</html>
'''

def write_file(fname, title, bodytype, body):
    path = os.path.join(TARGET, fname)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(XHTML.format(title=title, bodytype=bodytype, body=body))
    return fname

# ============================================================
# Paragraph extraction
# ============================================================
P_RE = re.compile(r'<P\s[^>]*>(.*?)</P>', re.DOTALL | re.IGNORECASE)

def classify_p(p_tag_full_match):
    """Classify a <P> tag as normal, arial, or indented-arial."""
    if 'Arial' not in p_tag_full_match:
        return 'normal'
    if 'margin-left: 1.31in' in p_tag_full_match or 'margin-left:1.31in' in p_tag_full_match:
        return 'indented'
    return 'arial'

def is_star_break(txt):
    """Check if text is a *** section break."""
    stripped = re.sub(r'[\s*]+', '', txt)
    return stripped == '' and '*' in txt and txt.count('*') >= 3

def clean_inline(h):
    """Clean HTML inline content to SE XHTML, preserving <i>, <b>, noteref links."""
    # CRITICAL: Move spaces from inside closing tags to outside
    h = re.sub(r'\s+(</[IiBbUuEeMmSsTtRrOoNnGg]+>)', r'\1 ', h)
    h = re.sub(r'&nbsp;(</[IiBbUu]>)', r'\1 ', h)
    # Move spaces from start of opening tags to before them
    h = re.sub(r'(<[IiBbUu]>)\s+', r' \1', h)

    # BR -> space
    h = re.sub(r'<BR\s*/?>', ' ', h, flags=re.IGNORECASE)

    # &nbsp; -> non-breaking space (but we'll normalize later)
    h = h.replace('&nbsp;', '\u00a0')
    h = h.replace('&shy;', '')

    # Decode HTML entities BEFORE tag processing
    # But protect < and > in tags first
    # Actually, html.unescape will decode &quot; &amp; etc. We need to be careful.
    # Let's decode entities that aren't part of tags
    h = h.replace('&lt;', '\x01LT\x01')
    h = h.replace('&gt;', '\x01GT\x01')
    h = h.replace('&amp;', '\x01AMP\x01')
    h = html_mod.unescape(h)
    h = h.replace('\x01LT\x01', '&lt;')
    h = h.replace('\x01GT\x01', '&gt;')
    h = h.replace('\x01AMP\x01', '&amp;')

    # Endnote references: <SUP><A CLASS="sdendnoteanc"...>...<SUP>N</SUP></A></SUP>
    # Handle both with and without <I> wrapper
    h = re.sub(
        r'<SUP>(?:<I>)?<A\s+CLASS="sdendnoteanc"\s+NAME="sdendnote(\d+)anc"\s+HREF="[^"]*"><SUP>(\d+)</SUP></A>(?:</I>)?</SUP>',
        r'<a href="endnotes.xhtml#note-\1" id="noteref-\1" epub:type="noteref">\2</a>',
        h, flags=re.IGNORECASE
    )
    # Variant without double-SUP
    h = re.sub(
        r'<SUP><A\s+CLASS="sdendnoteanc"\s+NAME="sdendnote(\d+)anc"\s+HREF="[^"]*">(\d+)</A></SUP>',
        r'<a href="endnotes.xhtml#note-\1" id="noteref-\1" epub:type="noteref">\2</a>',
        h, flags=re.IGNORECASE
    )
    # Clean up comma separators between adjacent endnote refs
    h = re.sub(r'<SUP>,?\s*</SUP>', '', h, flags=re.IGNORECASE)

    # Convert formatting tags to lowercase
    h = re.sub(r'<B>(.*?)</B>', r'<b>\1</b>', h, flags=re.DOTALL|re.IGNORECASE)
    h = re.sub(r'<I>(.*?)</I>', r'<i>\1</i>', h, flags=re.DOTALL|re.IGNORECASE)
    h = re.sub(r'<EM>(.*?)</EM>', r'<em>\1</em>', h, flags=re.DOTALL|re.IGNORECASE)
    h = re.sub(r'<STRONG>(.*?)</STRONG>', r'<strong>\1</strong>', h, flags=re.DOTALL|re.IGNORECASE)

    # Strip SUB tags (keep content)
    h = re.sub(r'</?SUB>', '', h, flags=re.IGNORECASE)
    # Strip SUP tags (keep content)  -- only orphaned ones
    h = re.sub(r'</?SUP>', '', h, flags=re.IGNORECASE)

    # Now strip all remaining HTML tags EXCEPT our safe ones
    def _strip(m):
        tag = m.group(0)
        low = tag.lower()
        # Keep <i>, </i>, <b>, </b>, <em>, </em>, <strong>, </strong>
        if re.match(r'</?[ib]>', low):
            return tag
        if re.match(r'</?em>', low):
            return tag
        if re.match(r'</?strong>', low):
            return tag
        if 'epub:type="noteref"' in tag:
            return tag
        if low == '</a>':
            return tag
        return ''

    h = re.sub(r'<[^>]+>', _strip, h)

    # Collapse whitespace
    h = re.sub(r'[ \t]+', ' ', h)
    # Collapse across newlines too
    h = re.sub(r'\s*\n\s*', ' ', h)
    h = h.strip()

    # Fix empty <b></b> and <i></i>
    h = re.sub(r'<([bi])>\s*</\1>', '', h)

    # Remove orphaned </a> tags (those not preceded by noteref close pattern)
    # Noteref links produce: ...epub:type="noteref">N</a>
    # Orphaned </a> are standalone from stripped <A NAME="..."></A>
    h = re.sub(r'(?<!\d)</[Aa]>', '', h)

    return h

def extract_paras(body_html):
    """Extract paragraphs from a section's body HTML.
    Returns list of dicts: {type, text, raw_match}
    type is one of: 'normal', 'arial', 'indented', 'break', 'blank'
    """
    result = []
    for m in P_RE.finditer(body_html):
        full = m.group(0)
        inner = m.group(1)

        # Check for blank paragraph
        stripped = re.sub(r'<[^>]+>', '', inner).strip()
        if not stripped:
            result.append({'type': 'blank', 'text': '', 'pos': m.start()})
            continue

        # Check for star break
        if is_star_break(stripped):
            result.append({'type': 'break', 'text': '', 'pos': m.start()})
            continue

        cls = classify_p(full)
        text = clean_inline(inner)
        if text:
            result.append({'type': cls, 'text': text, 'pos': m.start()})

    return result


def build_body(sec_key, sec=None):
    """Build XHTML body content from a section key."""
    if sec is None:
        sec = sections[sec_key]
    paras = extract_paras(sec['body'])

    # Filter out blanks (they served as spacers in the original)
    # But we need them to understand dialog structure
    # For now, just filter blanks and work with content paras + breaks
    content_paras = [p for p in paras if p['type'] != 'blank']

    lines = []
    in_network = False

    for p in content_paras:
        if p['type'] == 'break':
            if in_network:
                lines.append('\t\t\t</blockquote>')
                in_network = False
            lines.append('\t\t\t<hr/>')
            continue

        if p['type'] in ('arial', 'indented'):
            if not in_network:
                lines.append('\t\t\t<blockquote epub:type="z3998:letter" class="network-post">')
                in_network = True
            lines.append(f'\t\t\t\t<p>{p["text"]}</p>')
        else:  # normal
            if in_network:
                lines.append('\t\t\t</blockquote>')
                in_network = False
            lines.append(f'\t\t\t<p>{p["text"]}</p>')

    if in_network:
        lines.append('\t\t\t</blockquote>')

    return '\n'.join(lines)

# ============================================================
# Structure definition
# ============================================================
CHAPTERS = {
    'Volvox': [
        ('mermaid', 'Mermaid'),
        ('fables', 'Fables of the Reconstruction'),
        ('deathbed', 'Deathbed'),
        ('breeder', '94 Megabytes: Breeder'),
        ('cascade', 'Cascade'),
        ('backflash', 'Backflash'),
        ('maps', 'Maps and Legends'),
        ('corpse', 'Corpse'),
        ('bang', 'Bang'),
        ('stickman', 'Stickman'),
        ('invitation', 'An Invitation to Dance'),
        ('pixelpal', 'Pixelpal'),
        ('limited', 'Third-person Limited'),
        ('remora', 'Remora'),
        ('firebug', 'Firebug'),
        ('afterburn', 'Afterburn'),
        ('stockpile', 'Stockpile'),
        ('icarus', 'Icarus'),
        ('jailbreak', 'Jailbreak'),
        ('next', 'The Next Best Thing'),
        ('beachhead', 'Beachhead'),
        ('drugstore', 'Drugstore'),
        ('source', 'Source Code'),
        ('groundswell', 'Groundswell'),
        ('hitchhiker', '128 Megabytes: Hitchhiker'),
        ('animal', 'Animal Control'),
        ('ghost', 'Ghost'),
        ('blip', 'Blip'),
        ('womb', 'Womb'),
        ('eclipse', 'Eclipse'),
        ('monster', 'Monster'),
        ('warhorse', 'Warhorse'),
    ],
    'Physalia': [
        ('zeus', 'Zeus'),
        ('jiminy', 'Jiminy Cricket'),
        ('footprints', 'Footprints'),
        ('archetype', 'An Archetype of Dislocation'),
        ('punctuated', '400 Megabytes: Punctuated Equilibrium'),
        ('microstar', 'Microstar'),
        ('matchmaker', 'Matchmaker'),
        ('heat', 'Heat Death'),
        ('blind', 'Blind Date'),
        ('necrosis', 'Necrosis'),
        ('snare', 'Snare'),
        ('complicity', 'Complicity'),
        ('vision', 'Vision Quest'),
        ('algebra', 'The Algebra of Guilt'),
        ('starfucker', 'Starfucker'),
        ('mask', 'Mask'),
        ('scalpel', 'Scalpel'),
        ('thousand', 'By a Thousand Cuts'),
        ('generals', '500 Megabytes: The Generals'),
        ('sparkler', 'Sparkler'),
        ('decoys', 'Decoys'),
        ('crucifixion', 'Crucifixion, with Spiders'),
    ],
    'Anthopleura': [
        ('mug', 'Mug Shot'),
        ('anemone', 'Anemone'),
        ('behind', 'Behind the Lines'),
        ('spartacus', 'Spartacus'),
        ('tursipops', 'TursiPops'),
        ('terrarium', 'Terrarium'),
        ('soul', 'Soul Mate'),
        ('awol', 'AWOL'),
        ('scheherezade', 'Scheherezade'),
        ('adaptive', 'Adaptive Shatter'),
        ('niche', 'A Niche'),
    ],
}

# ============================================================
# Generate files
# ============================================================
generated_files = []

print("=" * 60)
print("Generating Maelstrom SE files")
print("=" * 60)

# --- Dedication ---
ded = '''\t\t<section id="dedication" epub:type="dedication">
\t\t\t<p>For Laurie</p>
\t\t\t<blockquote>
\t\t\t\t<p>\u201cThough she be but little, she is fierce.\u201d</p>
\t\t\t</blockquote>
\t\t</section>'''
generated_files.append(write_file('dedication.xhtml', 'Dedication', 'frontmatter', ded))

# --- Epigraph ---
epi = '''\t\t<section id="epigraph" epub:type="epigraph">
\t\t\t<blockquote>
\t\t\t\t<p>Behold now behemoth, which I made with thee; he eateth grass as an ox.</p>
\t\t\t\t<cite>Job 40:15</cite>
\t\t\t</blockquote>
\t\t\t<blockquote>
\t\t\t\t<p>All flesh is grass.</p>
\t\t\t\t<cite>Isaiah 40:6</cite>
\t\t\t</blockquote>
\t\t</section>'''
generated_files.append(write_file('epigraph.xhtml', 'Epigraph', 'frontmatter', epi))

# --- Halftitlepage ---
htp = '''\t\t<section id="halftitlepage" epub:type="halftitlepage">
\t\t\t<h2 epub:type="fulltitle">Maelstrom</h2>
\t\t</section>'''
generated_files.append(write_file('halftitlepage.xhtml', 'Maelstrom', 'frontmatter', htp))

# --- Prelude ---
print("Prelude: Messiah")
body = build_body('prelude')
pre = f'''\t\t<section id="prelude" epub:type="prologue">
\t\t\t<h2 epub:type="title">
\t\t\t\t<span>Prelude</span>
\t\t\t\t<span epub:type="subtitle">Messiah</span>
\t\t\t</h2>
{body}
\t\t</section>'''
generated_files.append(write_file('prelude.xhtml', 'Prelude: Messiah', 'bodymatter', pre))

# --- Parts and chapters ---
part_num = 0
for part_name, ch_list in CHAPTERS.items():
    part_num += 1
    pf = f'part-{part_num}.xhtml'
    part_body = f'''\t\t<section id="part-{part_num}" epub:type="part">
\t\t\t<h2 epub:type="title">Part {part_num}<br/>
\t\t\t<span epub:type="subtitle">{part_name}</span></h2>
\t\t</section>'''
    generated_files.append(write_file(pf, f'Part {part_num}: {part_name}', 'bodymatter', part_body))
    print(f"Part {part_num}: {part_name}")

    for ch_i, (anchor, ch_title) in enumerate(ch_list, 1):
        ch_id = f'chapter-{part_num}-{ch_i}'
        fname = f'{ch_id}.xhtml'

        body = build_body(anchor)

        # Title markup: split "N Megabytes: Subtitle"
        if re.match(r'^\d+ Megabytes:', ch_title):
            main, sub = ch_title.split(': ', 1)
            tmk = f'''<h3 epub:type="title">
\t\t\t\t<span>{main}</span>
\t\t\t\t<span epub:type="subtitle">{sub}</span>
\t\t\t</h3>'''
        else:
            tmk = f'<h3 epub:type="title">{ch_title}</h3>'

        sec_body = f'''\t\t<section id="{ch_id}" epub:type="chapter">
\t\t\t{tmk}
{body}
\t\t</section>'''
        generated_files.append(write_file(fname, ch_title, 'bodymatter', sec_body))
        print(f"  {ch_i}. {ch_title}")

# --- Epilog ---
print("Epilog: Sleeping by Firelight")
body = build_body('epilog')
epl = f'''\t\t<section id="epilog" epub:type="epilogue">
\t\t\t<h2 epub:type="title">
\t\t\t\t<span>Epilog</span>
\t\t\t\t<span epub:type="subtitle">Sleeping by Firelight</span>
\t\t\t</h2>
{body}
\t\t</section>'''
generated_files.append(write_file('epilog.xhtml', 'Epilog: Sleeping by Firelight', 'bodymatter', epl))

# --- Endnotes ---
print("Endnotes")
endnote_divs = re.finditer(
    r'<DIV ID="sdendnote(\d+)"[^>]*>(.*?)</DIV>',
    src, re.DOTALL | re.IGNORECASE
)
endnotes = []
for m in endnote_divs:
    num = int(m.group(1))
    raw = m.group(2)
    # Strip the backlink anchor
    raw = re.sub(r'<A[^>]*sdendnotesym[^>]*>.*?</A>', '', raw, flags=re.DOTALL|re.IGNORECASE)
    # Remove <P> wrappers
    raw = re.sub(r'<P[^>]*>', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'</P>', '', raw, flags=re.IGNORECASE)
    text = clean_inline(raw)
    # Remove leading number
    text = re.sub(r'^\d+\s+', '', text)
    endnotes.append((num, text.strip()))
endnotes.sort(key=lambda x: x[0])
print(f"  {len(endnotes)} endnotes found")

en_lines = [
    '\t\t<section id="endnotes" epub:type="endnotes">',
    '\t\t\t<h2 epub:type="title">Endnotes</h2>',
    '\t\t\t<ol>'
]
for num, text in endnotes:
    en_lines.append(f'\t\t\t\t<li id="note-{num}" epub:type="endnote">')
    en_lines.append(f'\t\t\t\t\t<p>{text} <a href="notes-and-references.xhtml#noteref-{num}" epub:type="backlink">\u21a9</a></p>')
    en_lines.append(f'\t\t\t\t</li>')
en_lines.append('\t\t\t</ol>')
en_lines.append('\t\t</section>')
generated_files.append(write_file('endnotes.xhtml', 'Endnotes', 'backmatter', '\n'.join(en_lines)))

# --- Notes and References ---
print("Notes and References")
body = build_body('notes')
nar = f'''\t\t<section id="notes-and-references" epub:type="appendix">
\t\t\t<h2 epub:type="title">Notes and References</h2>
{body}
\t\t</section>'''
generated_files.append(write_file('notes-and-references.xhtml', 'Notes and References', 'backmatter', nar))

# --- Acknowledgments ---
print("Acknowledgments")
body = build_body('acknowledgments')
ack = f'''\t\t<section id="acknowledgments" epub:type="acknowledgments">
\t\t\t<h2 epub:type="title">Acknowledgments</h2>
{body}
\t\t</section>'''
generated_files.append(write_file('acknowledgments.xhtml', 'Acknowledgments', 'backmatter', ack))

# ============================================================
# Word count verification
# ============================================================
print("\n" + "=" * 60)
total = 0
for fn in os.listdir(TARGET):
    if fn.endswith('.xhtml') and fn not in ('titlepage.xhtml', 'imprint.xhtml', 'colophon.xhtml', 'uncopyright.xhtml'):
        with open(os.path.join(TARGET, fn)) as fh:
            ct = re.sub(r'<[^>]+>', ' ', fh.read())
            total += len(ct.split())
print(f"Output word count: {total}")
print(f"Source word count:  ~111561 (includes HTML overhead)")
print(f"Generated {len(generated_files)} files")
print("=" * 60)
