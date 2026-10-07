"""한글 폰트 텍스처 생성: 256x1024 PSMT8 (상단 256행 = 원본 폰트)
글리프 셀: 16x16. 한글 g번째 글자 셀:
  g < 768 : u=(g%16)*16, v=256+(g//16)*16
  g >= 768: (가나 영역 재사용) u=(g2%16)*16, v=16+(g2//16)*16  (g2=g-768, 최대 128)
인코딩: 리드 0xF0+g//70, 트레일 TRAIL[g%70]
"""
import os, sys
from PIL import Image, ImageFont, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
ROOT = os.path.dirname(WORK)

TRAIL = [b for b in range(0xA8, 0xF0) if b not in (0xBD, 0xBE)]
assert len(TRAIL) == 70
LEADS = list(range(0xF0, 0x100))
SINGLES = list(range(0x80, 0xA8))      # 1바이트 한글 코드 40개
SINGLE_CELL0 = 88                      # 가나 영역 셀 88~127
HROWS = 47                             # 한글 영역 행 수 (v<=1007: UV 14비트 한계)
HCELLS = HROWS * 16                    # 752
MAXG = HCELLS + SINGLE_CELL0

sys.path.insert(0, HERE)
import paths
FONT_FILE = os.path.join(paths.FONT_DIR, 'NanumSquareNeo-cBd.ttf')
FONT_PX = 14


def encode_g(g):
    return bytes([LEADS[g // 70], TRAIL[g % 70]])


def cell(g):
    if g < HCELLS:
        return (g % 16) * 16, 256 + (g // 16) * 16
    g2 = g - HCELLS
    return (g2 % 16) * 16, 16 + (g2 // 16) * 16


def single_cell(i):
    c = SINGLE_CELL0 + i
    return (c % 16) * 16, 16 + (c // 16) * 16


def unsw(i):
    return (i & 0xe7) | ((i & 8) << 1) | ((i & 16) >> 1)


def alpha_index_map(pal):
    """알파(0..128) -> 회색(128) 팔레트 인덱스"""
    gray = []
    for i in range(256):
        p = unsw(i)
        r, g, b, a = pal[4 * p:4 * p + 4]
        if r == g == b == 128:
            gray.append((a, i))
    gray.sort()
    lut = []
    for a in range(129):
        best = min(gray, key=lambda x: abs(x[0] - a))
        lut.append(best[1])
    return lut


def render_glyph(font, ch):
    """16x16 알파(0..128) 배열"""
    S = 4  # 슈퍼샘플
    big = Image.new('L', (16 * S, 16 * S), 0)
    d = ImageDraw.Draw(big)
    fb = ImageFont.truetype(FONT_FILE, FONT_PX * S)
    bbox = d.textbbox((0, 0), '한', font=fb)  # 기준 높이
    h = bbox[3] - bbox[1]
    y0 = (16 * S - h) // 2 - bbox[1]
    bb = d.textbbox((0, 0), ch, font=fb)
    w = bb[2] - bb[0]
    x0 = (14 * S - w) // 2 - bb[0]
    d.text((x0, y0), ch, font=fb, fill=255)
    small = big.resize((16, 16), Image.LANCZOS)
    px = small.load()
    out = [[0] * 16 for _ in range(16)]
    for y in range(16):
        for x in range(16):
            v = px[x, y]
            # 원본처럼 또렷하게: 대비 강화
            v = max(0, min(255, int((v - 30) * 1.35)))
            out[y][x] = v * 128 // 255
    return out


def build(chars, pal_path, pix_path, out_path, preview=None, singles=()):
    pal = open(pal_path, 'rb').read()
    pix = bytearray(open(pix_path, 'rb').read())
    assert len(pal) == 1024 and len(pix) == 65536
    lut = alpha_index_map(pal)
    img = bytearray(256 * 1024)
    img[:65536] = pix
    font = None
    if len(chars) > MAXG:
        raise SystemExit('한글 글자 수 초과: %d > %d' % (len(chars), MAXG))
    assert len(singles) <= len(SINGLES)
    jobs = [(cell(g), ch) for g, ch in enumerate(chars)] + [(single_cell(i), ch) for i, ch in enumerate(singles)]
    for (u, v), ch in jobs:
        a = render_glyph(font, ch)
        for y in range(16):
            for x in range(16):
                img[(v + y) * 256 + u + x] = lut[a[y][x]]
    open(out_path, 'wb').write(pal + bytes(img))
    if preview:
        cols = [tuple(pal[4 * unsw(i):4 * unsw(i) + 4]) for i in range(256)]
        im = Image.new('RGB', (256, 1024))
        im.putdata([(min(255, cols[p][3] * 2),) * 3 for p in img])
        im.save(preview)
    cmap = {ch: encode_g(g) for g, ch in enumerate(chars)}
    for i, ch in enumerate(singles):
        cmap[ch] = bytes([SINGLES[i]])
    return cmap
