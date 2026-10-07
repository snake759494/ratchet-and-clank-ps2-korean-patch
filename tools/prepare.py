"""원본 ISO에서 빌드 준비 자료를 만든다 (저장소에는 넣지 않는 것들).
 - SCPS_150.37 (ELF), font_pal.bin/font_pix.bin (원본 폰트)
 - text/jp/*.tsv (일본어 원문), text/src_all.tsv, text/scene_src.tsv (번호 → 원문)
 - cache/ (WAD 압축 해제본), lv/ (레벨 텍스트)
사용: python tools/prepare.py   (먼저 tools/dump.py 로 cache/ 생성)"""
import os, sys, io, struct, shutil, collections, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import paths, toc, levels, jpcode
os.chdir(paths.WORK)

# ELF
import pycdlib
iso = pycdlib.PyCdlib(); iso.open(paths.ISO)
b = io.BytesIO(); iso.get_file_from_iso_fp(b, iso_path='/SCPS_150.37;1'); iso.close()
open('SCPS_150.37', 'wb').write(b.getvalue())

# 원본 폰트 (메뉴 레벨 HUD 텍스처 1번)
d = open('cache/001b6f000.bin', 'rb').read()
cnt, lst = struct.unpack_from('<II', d, 0x58)
B = 0x5c000 + struct.unpack_from('<I', d, 0x68)[0]
po, xo, w, h = struct.unpack_from('<4I', d, lst + 16)
assert (w, h) == (256, 256)
open('font_pal.bin', 'wb').write(d[B + po:B + po + 1024])
open('font_pix.bin', 'wb').write(d[B + xo:B + xo + w * h])

# 레벨 텍스트 파일
os.makedirs('lv', exist_ok=True)
for e in levels.level_entries():
    shutil.copy('cache/%09x.bin' % (e['subs'][1][0] * 2048), 'lv/L%02d.bin' % e['id'])

# 일본어 원문 (레벨 + 전역)
os.makedirs('text/jp', exist_ok=True)
def dump_table(dd, hdr, out):
    B = struct.unpack_from('<I', dd, hdr)[0]
    cnt, size = struct.unpack_from('<II', dd, B)
    with open(out, 'w', encoding='utf-8') as f:
        for k in range(cnt):
            o, sid, _, _ = struct.unpack_from('<IIiI', dd, B + 8 + 16 * k)
            f.write('%04X\t%s\n' % (sid, jpcode.decode(dd[B + o:].split(b'\0')[0])))
for e in levels.level_entries():
    dump_table(open('lv/L%02d.bin' % e['id'], 'rb').read(), 0x10, 'text/jp/L%02d.tsv' % e['id'])
W = toc.toc()
dump_table(toc.read(W[2 * 677], W[2 * 677 + 1]), 0, 'text/jp/G.tsv')

# 번호 → 원문 목록 (translation/ko 의 번호와 대응)
allt = collections.OrderedDict()
for fn in ['text/jp/G.tsv'] + sorted(glob.glob('text/jp/L*.tsv')):
    for l in open(fn, encoding='utf-8'):
        sid, t = l.rstrip('\n').split('\t', 1)
        allt.setdefault(t, sid)
with open('text/src_all.tsv', 'w', encoding='utf-8') as f:
    for i, (t, sid) in enumerate(allt.items()):
        f.write('%04d\t%s\t%s\n' % (i, sid, t))

import scenes
texts = set()
for off, path in scenes.scene_files():
    dd = open(path, 'rb').read()
    bb, ents, p = scenes.parse(dd)
    for en in ents:
        texts.add(jpcode.decode(dd[bb + en[2]:].split(b'\0')[0]))
with open('text/scene_src.tsv', 'w', encoding='utf-8') as f:
    for i, t in enumerate(sorted(texts)):
        f.write('%d\t%s\n' % (i, t))
print('준비 완료: 원문 %d, 자막 %d' % (len(allt), len(texts)))
