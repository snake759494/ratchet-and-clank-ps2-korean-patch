"""컷신 타이틀 카드(PIF2 512x64 알파) 한글화"""
import os, struct, sys
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pif
WORK = os.path.dirname(HERE); ROOT = os.path.dirname(WORK)
CARD_ISO_OFF = 0x0565e6000
import paths
FONT = os.path.join(paths.FONT_DIR, 'NanumSquareNeo-dEb.ttf')


def lut_from_pal(pal):
    al = [(pal[4 * pif.unsw(i) + 3], i) for i in range(256)]
    return [min(al, key=lambda x: abs(x[0] - a))[1] for a in range(129)]


def draw(text, w, h, size=22):
    S = 4
    big = Image.new('L', (w * S, h * S), 0)
    d = ImageDraw.Draw(big)
    while True:
        f = ImageFont.truetype(FONT, size * S)
        bb = d.textbbox((0, 0), text, font=f)
        if bb[2] - bb[0] <= (w - 16) * S or size <= 14:
            break
        size -= 1
    ref = d.textbbox((0, 0), '한', font=f)
    x = (w * S - (bb[2] - bb[0])) // 2 - bb[0]
    y = (h * S - (ref[3] - ref[1])) // 2 - ref[1]
    d.text((x, y), text, font=f, fill=255)
    return big.resize((w, h), Image.LANCZOS)


def patch(d):
    d = bytearray(d)
    texts = {}
    for l in open(os.path.join(WORK, 'translation', 'cards_ko.tsv'), encoding='utf-8'):
        i, t = l.rstrip('\n').split('\t', 1); texts[int(i)] = t
    n = struct.unpack_from('<I', d, 0)[0]
    offs = struct.unpack_from('<%dI' % n, d, 4)
    for i, o in enumerate(offs[1:]):
        if i not in texts:
            continue
        w, h, psm = pif.parse(d, o)
        assert (w, h, psm) == (512, 64, 0x13)
        lut = lut_from_pal(d[o + 0x20:o + 0x420])
        im = draw(texts[i], w, h)
        px = im.load()
        base = o + 0x420
        for y in range(h):
            for x in range(w):
                d[base + y * w + x] = lut[128 - px[x, y] * 128 // 255]  # 마스크: 글자=투명
    return bytes(d)
