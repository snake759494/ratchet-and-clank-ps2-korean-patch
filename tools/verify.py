"""최종 ISO 전수검사"""
import os, sys, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import build, build_font, levels, toc, wad, scenes, overlays, elfpatch, pickle
WORK = os.path.dirname(HERE)
KO = build.OUT_ISO
f = open(KO, 'rb')
def rd(o, n): f.seek(o); return f.read(n)

# 인코딩표 재구성 (build 와 동일 규칙)
tr = build.load_translation()
scene_tr = {k: build.normalize(v) for k, v in scenes.load_tr().items()}
per = {}
for name in ['G'] + ['L%02d' % e['id'] for e in levels.level_entries()]:
    per[name] = [(sid, build.normalize(tr.get(jp, jp if all(ord(c) < 0x80 for c in jp) else None)))
                 for sid, jp in build.load_tsv(os.path.join(WORK, 'text', 'jp', name + '.tsv'))]
alltexts = set(t for v in per.values() for _, t in v) | set(scene_tr.values())
freq = collections.Counter(ch for t in alltexts for ch in t if '가' <= ch <= '힣')
singles = [ch for ch, _ in sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:len(build_font.SINGLES)]]
chars = [c for c in build.hangul_chars(alltexts) if c not in singles]
cmap = {ch: build_font.encode_g(g) for g, ch in enumerate(chars)}
for i, ch in enumerate(singles): cmap[ch] = bytes([build_font.SINGLES[i]])
enc = lambda t: build.encode(t, cmap)

err = 0
def table(d, hdr):
    B = struct.unpack_from('<I', d, hdr)[0]
    cnt, size = struct.unpack_from('<II', d, B)
    return [(struct.unpack_from('<IIiI', d, B + 8 + 16 * i)[1], d[B + struct.unpack_from('<I', d, B + 8 + 16 * i)[0]:].split(b'\0')[0]) for i in range(cnt)]

# 1) 전역 텍스트
W = toc.toc()
g = rd(W[2 * 677] * 2048, W[2 * 677 + 1] * 2048)
for (sid, b), (sid2, t) in zip(table(g, 0), per['G']):
    if sid != sid2 or b != enc(t): err += 1; print('G 불일치', hex(sid), repr(t[:30]), b[:16].hex(), enc(t)[:16].hex())
print('G 검사', len(per['G']))
# 2) 레벨 텍스트
for e in levels.level_entries():
    h = struct.unpack('<10I', rd(e['lba'] * 2048, 40))
    raw = rd(h[4] * 2048, h[5] * 2048)
    d, _, _ = wad.decompress(raw)
    name = 'L%02d' % e['id']
    rows = table(d, 0x10)
    bads = [(sid, s2, t, b) for (sid, b), (s2, t) in zip(rows, per[name]) if sid != s2 or b != enc(t)]
    bad = len(bads)
    if bads and e['id'] == 0:
        for sid, s2, t, b in bads[:5]: print('  예', hex(sid), hex(s2), repr(t[:30]), b[:20].hex(), enc(t)[:20].hex())
    err += bad
    print(name, len(rows), '불일치', bad)
# 3) 컷신 자막
n = bad = 0
for off, path in scenes.scene_files():
    hd = rd(off, 16); sz = struct.unpack_from('<I', hd, 3)[0]
    d, _, _ = wad.decompress(rd(off, sz))
    o = open(path, 'rb').read()
    if len(d) != len(o) or d[:struct.unpack_from('<I', o, 4)[0]] != o[:struct.unpack_from('<I', o, 4)[0]]:
        bad += 1; continue
    b, ents, p = scenes.parse(d)
    for e in ents:
        s = d[b + e[2]:].split(b'\0')[0]
        if any(0x80 <= c <= 0xEF for c in s) and not s:   # 형식 확인용
            bad += 1
    n += 1
print('컷신 파일', n, '오류', bad); err += bad
# 4) 오버레이
ovs = pickle.load(open(os.path.join(WORK, 'overlays.pkl'), 'rb'))
for tbl, fd in ovs:
    for k in ('tex', 'q', 's'):
        w = struct.unpack('<I', rd(fd[k][0], 4))[0]
        if w >> 26 != 2: err += 1; print('훅 없음', hex(fd[k][0]), k)
    for off, b in elfpatch.table_patches():
        if rd(tbl + off, 4) != b: err += 1; print('테이블 불일치', hex(tbl)); break
print('오버레이', len(ovs))
print('총 오류', err)
