"""메뉴 레벨(001B6F000) HUD 텍스처 한글화: 4번 'スタートボタン'"""
import os, struct, sys
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pif
WORK = os.path.dirname(HERE); ROOT = os.path.dirname(WORK)
MENU_ISO_OFF = 0x001b6f000
import paths
FONT = os.path.join(paths.FONT_DIR, 'NanumSquareNeo-dEb.ttf')
TEXT = 'START 버튼'


def patch(d):
    d = bytearray(d)
    cnt, lst = struct.unpack_from('<II', d, 0x58)
    B = 0x5c000 + struct.unpack_from('<I', d, 0x68)[0]
    po, xo, w, h = struct.unpack_from('<4I', d, lst + 16 * 4)
    assert (w, h) == (256, 128)
    pal = d[B + po:B + po + 1024]
    cols = [tuple(pal[4 * pif.unsw(i):4 * pif.unsw(i) + 4]) for i in range(256)]
    old = d[B + xo:B + xo + w * h]
    bgi = max(set(old), key=old.count)
    bg = cols[bgi][:3]
    fg = (116, 160, 250)
    S = 4
    big = Image.new('L', (w * S, h * S), 0)
    dr = ImageDraw.Draw(big)
    size = 28
    while True:
        f = ImageFont.truetype(FONT, size * S)
        bb = dr.textbbox((0, 0), TEXT, font=f)
        if bb[2] - bb[0] <= 236 * S:
            break
        size -= 1
    ref = dr.textbbox((0, 0), '버', font=f)
    x = (w * S - (bb[2] - bb[0])) // 2 - bb[0]
    y = 64 * S - (ref[3] - ref[1]) // 2 - ref[1]  # 띠 중앙(원본 행 48~79)
    dr.text((x, y), TEXT, font=f, fill=255)
    cov = big.resize((w, h), Image.LANCZOS).load()
    # RGB = 원본 세로 그라데이션 유지, 알파 = 한글 글자 모양
    cache = {}
    for yy in range(h):
        for xx in range(w):
            oi = old[yy * w + xx]
            r, g, b, _ = cols[oi]
            a = cov[xx, yy] * 128 // 255
            key = (r, g, b, a)
            if key not in cache:
                cache[key] = min(range(256), key=lambda i: 16 * (cols[i][3] - a) ** 2 +
                                 sum((cols[i][k] - key[k]) ** 2 for k in range(3)))
            d[B + xo + yy * w + xx] = cache[key]
    return bytes(d)
