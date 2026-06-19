#!/usr/bin/env python3
"""
clean_sdd_for_customer.py — Produce a customer-ready copy of the SDD v2.2:
  1. Remove ALL comments (9 review comments by Derek Abdinor).
  2. Reject the tracked insertion (the 'TODO: MAR3->MAR5 hostname' note added in a prior session)
     so neither the TODO text nor a tracked-change appears.
  3. Fix the one objective heading defect: stray manual number "1.1.2.1   " in the
     "Zug zu Server zuweisung" heading.

Surgical zip-level edit on the comment/document XML parts only — every other part
(57 media images, headers/footers, styles) is copied byte-for-byte. Heading-casing
style issues are NOT touched (reported separately for the author to decide).
"""
import re
import shutil
import zipfile

SRC = "design freeze/ND-DEL-OBB-035-SDD-002-01_v2.2.docx"
OUT = "design freeze/ND-DEL-OBB-035-SDD-002-01_v2.2_clean.docx"

# comment part files to drop entirely
COMMENT_PARTS = {
    "word/comments.xml",
    "word/commentsIds.xml",
    "word/commentsExtended.xml",
    "word/commentsExtensible.xml",
}

def clean_document_xml(xml: str) -> str:
    # --- 1. remove comment anchors/refs from the body ---
    # <w:commentRangeStart .../> and <w:commentRangeEnd .../>
    xml = re.sub(r'<w:commentRangeStart[^>]*/>', '', xml)
    xml = re.sub(r'<w:commentRangeEnd[^>]*/>', '', xml)
    # the comment reference run: <w:r ...><w:rPr>...<w:rStyle .../>...</w:rPr><w:commentReference .../></w:r>
    # remove any run that contains a commentReference, plus bare commentReference elements
    xml = re.sub(r'<w:r\b[^>]*>(?:(?!</w:r>).)*?<w:commentReference[^>]*/>.*?</w:r>', '', xml, flags=re.S)
    xml = re.sub(r'<w:commentReference[^>]*/>', '', xml)

    # --- 2. reject the tracked insertion(s): drop <w:ins>...</w:ins> entirely ---
    # (rejecting an insertion = removing the inserted content). There is 1 ins (the TODO).
    xml = re.sub(r'<w:ins\b[^>]*>.*?</w:ins>', '', xml, flags=re.S)
    # also handle self-closed / empty ins just in case
    xml = re.sub(r'<w:ins\b[^>]*/>', '', xml)

    # --- 3. fix stray manual heading number "1.1.2.1<nbsp><nbsp> Zug zu Server zuweisung" ---
    # The number is separated from the heading text by non-breaking spaces ( ) and/or
    # regular spaces/tabs. Only strip when it directly precedes "Zug zu Server zuweisung"
    # (the heading) so we DON'T touch the legitimate body cross-ref "...in Kapitel 1.1.2.1...".
    xml = re.sub(r'1\.1\.2\.1[  \t]+(Zug zu Server zuweisung)', r'\1', xml)

    return xml

def clean_rels(xml: str) -> str:
    # drop relationship entries pointing at the comment parts
    for tgt in ('comments.xml', 'commentsIds.xml', 'commentsExtended.xml', 'commentsExtensible.xml'):
        xml = re.sub(r'<Relationship\b[^>]*Target="[^"]*' + re.escape(tgt) + r'"[^>]*/>', '', xml)
    return xml

def clean_content_types(xml: str) -> str:
    # drop the Override entries for the comment parts
    for part in ('/word/comments.xml', '/word/commentsIds.xml',
                 '/word/commentsExtended.xml', '/word/commentsExtensible.xml'):
        xml = re.sub(r'<Override\b[^>]*PartName="' + re.escape(part) + r'"[^>]*/>', '', xml)
    return xml

with zipfile.ZipFile(SRC) as zin:
    items = zin.infolist()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in items:
            if item.filename in COMMENT_PARTS:
                continue  # drop comment parts entirely
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = clean_document_xml(data.decode("utf-8")).encode("utf-8")
            elif item.filename == "word/_rels/document.xml.rels":
                data = clean_rels(data.decode("utf-8")).encode("utf-8")
            elif item.filename == "[Content_Types].xml":
                data = clean_content_types(data.decode("utf-8")).encode("utf-8")
            zi = zipfile.ZipInfo(item.filename, date_time=item.date_time)
            zi.compress_type = item.compress_type
            zi.external_attr = item.external_attr
            zi.internal_attr = item.internal_attr
            zi.create_system = item.create_system
            zout.writestr(zi, data)

print("WROTE", OUT)
