"""Format-native XMP envelope writers and readers.

One XMP packet, three containers: PNG iTXt, JPEG APP1, WebP RIFF chunk.
All functions are pure byte transforms — no file IO, no logging.
"""

import struct
import zlib

XMP_KEYWORD = b"XML:com.adobe.xmp"
XMP_NAMESPACE = b"http://ns.adobe.com/xap/1.0/\x00"

_ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}
_UNESCAPES = {escaped: ch for ch, escaped in _ESCAPES.items()}
_DESCRIPTION_OPEN = b"<dc:description>"
_DESCRIPTION_CLOSE = b"</dc:description>"


def xmp_packet(text: str) -> bytes:
    """Serialize text as an XMP packet with the text in dc:description."""
    escaped = "".join(_ESCAPES.get(ch, ch) for ch in text)
    return (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"<dc:description>{escaped}</dc:description>"
        "</rdf:Description></rdf:RDF></x:xmpmeta>"
    ).encode()


def extract_description(xml: bytes) -> str:
    """Pull the dc:description text back out of a packet and unescape it.

    Escaping makes this safe: the literal close tag can never appear
    inside the description content.
    """
    start = xml.find(_DESCRIPTION_OPEN)
    end = xml.find(_DESCRIPTION_CLOSE, start)
    if start < 0 or end < 0:
        return ""
    text = xml[start + len(_DESCRIPTION_OPEN) : end].decode("utf-8", errors="replace")
    for escaped, ch in _UNESCAPES.items():
        text = text.replace(escaped, ch)
    return text


# ── PNG ──────────────────────────────────────────────────────────────────────


def _png_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    chunks, pos = [], 8
    while pos + 12 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        ctype = data[pos + 4 : pos + 8]
        chunks.append((ctype, data[pos + 8 : pos + 8 + length]))
        pos += 12 + length
    return chunks


def _png_chunk(ctype: bytes, raw: bytes) -> bytes:
    body = ctype + raw
    return struct.pack(">I", len(raw)) + body + struct.pack(">I", zlib.crc32(body))


def inject_png(data: bytes, text: str) -> bytes:
    chunks = [
        (ctype, raw)
        for ctype, raw in _png_chunks(data)
        if not (ctype.lower() == b"itxt" and raw.lower().startswith(XMP_KEYWORD.lower() + b"\x00"))
    ]
    iend = next(i for i, (ctype, _) in enumerate(chunks) if ctype == b"IEND")
    packet = xmp_packet(text)
    itxt = XMP_KEYWORD + b"\x00\x00\x00\x00\x00" + packet
    chunks.insert(iend, (b"iTXt", itxt))
    return data[:8] + b"".join(_png_chunk(t, r) for t, r in chunks)


def read_png(data: bytes) -> bytes | None:
    for ctype, raw in _png_chunks(data):
        if ctype.lower() != b"itxt":
            continue
        kw_end = raw.find(b"\x00")
        if kw_end <= 0 or raw[:kw_end].lower() != XMP_KEYWORD.lower():
            continue
        flag = raw[kw_end + 1]
        text = raw[kw_end + 5 :]
        return zlib.decompress(text) if flag else text
    return None


# ── JPEG ─────────────────────────────────────────────────────────────────────


def inject_jpeg(data: bytes, text: str) -> bytes:
    body = data[2:]
    # strip a payload segment previously inserted right after SOI
    if len(body) >= 4 and body.startswith(b"\xff\xe1"):
        length = struct.unpack(">H", body[2:4])[0]
        if body[4 : 4 + len(XMP_NAMESPACE)] == XMP_NAMESPACE:
            body = body[2 + length :]
    packet = xmp_packet(text)
    app1 = (
        b"\xff\xe1"
        + struct.pack(">H", len(packet) + len(XMP_NAMESPACE) + 2)
        + XMP_NAMESPACE
        + packet
    )
    return data[:2] + app1 + body


def read_jpeg(data: bytes) -> bytes | None:
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            break
        seg_type = data[pos + 1]
        if seg_type == 0xFF:
            pos += 1
            continue
        if seg_type in (0xD8, 0xD9, 0xDA) or 0xD0 <= seg_type <= 0xD7:
            pos += 2
            continue
        length = struct.unpack(">H", data[pos + 2 : pos + 4])[0]
        if length < 2:
            break
        payload = data[pos + 4 : pos + 2 + length]
        if seg_type == 0xE1 and payload.startswith(XMP_NAMESPACE):
            return payload[len(XMP_NAMESPACE) :]
        pos += 2 + length
    return None


# ── WebP ─────────────────────────────────────────────────────────────────────


def inject_webp(data: bytes, text: str) -> bytes:
    body, pos, kept = data[12:], 0, []
    while pos + 8 <= len(body):
        size = struct.unpack("<I", body[pos + 4 : pos + 8])[0]
        step = 8 + size + (size & 1)
        if body[pos : pos + 4] != b"XMP ":
            kept.append(body[pos : pos + step])
        pos += step
    packet = xmp_packet(text)
    chunk = (
        b"XMP " + struct.pack("<I", len(packet)) + packet + (b"\x00" if len(packet) & 1 else b"")
    )
    rest = b"".join(kept) + chunk
    return b"RIFF" + struct.pack("<I", len(rest) + 4) + b"WEBP" + rest


def read_webp(data: bytes) -> bytes | None:
    body, pos = data[12:], 0
    while pos + 8 <= len(body):
        size = struct.unpack("<I", body[pos + 4 : pos + 8])[0]
        if body[pos : pos + 4] == b"XMP ":
            return body[pos + 8 : pos + 8 + size]
        pos += 8 + size + (size & 1)
    return None


# ── detection ────────────────────────────────────────────────────────────────


def detect_format(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    return None
