"""한글패치 ISO 빌드
사용: python tools/build.py [--test]
"""
import os, sys, struct, shutil, re, glob
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import toc, wadc, levels, build_font, elfpatch, scenes, cards, hudimg, overlays, pickle
from iso import Iso

WORK = os.path.dirname(HERE)
ROOT = os.path.dirname(WORK)
import paths
SRC_ISO = paths.ISO
OUT_ISO = paths.OUT_ISO

# 원본 폰트에 있는 ASCII 글리프
ASCII_OK = set(chr(c) for c in range(0x20, 0x7f)) - set('{}')  # 원문에 쓰인 ASCII 허용(%d 등)
SUBST = {'·': '.', '…': '...', '「': '"', '」': '"', '『': '"', '』': '"', '~': '-', '～': '-',
         '“': '"', '”': '"', '‘': "'", '’': "'", '—': '-', '–': '-', '!': '!', '?': '?',
         '（': '(', '）': ')', '：': ':'}
TOKEN = re.compile(r'\{([0-9A-F]{2})\}')


def load_tsv(path):
    rows = []
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line:
            continue
        sid, t = line.split('\t', 1)
        rows.append((int(sid, 16), t))
    return rows


def load_translation():
    """text/src_all.tsv(번호→원문) + text/ko/*.tsv(번호→번역) → {원문: 번역} (레벨 공통)"""
    src = {}
    for line in open(os.path.join(WORK, 'text', 'src_all.tsv'), encoding='utf-8'):
        idx, sid, jp = line.rstrip('\n').split('\t', 2)
        src[idx] = jp
    tr = {}
    for p in sorted(glob.glob(os.path.join(WORK, 'translation', 'ko', '*.tsv'))):
        for line in open(p, encoding='utf-8'):
            line = line.rstrip('\n')
            if not line or line.startswith('#'):
                continue
            idx, ko = line.split('\t', 1)
            tr[src[idx]] = ko
    return tr


def normalize(s):
    for a, b in SUBST.items():
        s = s.replace(a, b)
    return s


def hangul_chars(texts):
    cs = set()
    for t in texts:
        for ch in TOKEN.sub('', t):
            if '가' <= ch <= '힣':
                cs.add(ch)
    return sorted(cs)


def encode(s, cmap):
    out = bytearray()
    pos = 0
    for m in TOKEN.finditer(s):
        out += _enc_plain(s[pos:m.start()], cmap)
        out.append(int(m.group(1), 16))
        pos = m.end()
    out += _enc_plain(s[pos:], cmap)
    return bytes(out)


def _enc_plain(s, cmap):
    out = bytearray()
    for ch in s:
        if ch in cmap:
            out += cmap[ch]
        elif ch in ASCII_OK:
            out.append(ord(ch))
        else:
            raise ValueError('사용할 수 없는 문자 %r in %r' % (ch, s))
    return bytes(out)


def rebuild_table(d, entries_bytes, hdr=0x10):
    """d: 텍스트 파일, entries_bytes: [(id, bytes)] 원래 순서, hdr: 테이블 위치를 담은 헤더 오프셋"""
    d = bytearray(d)
    B = struct.unpack_from('<I', d, hdr)[0]
    cnt, size = struct.unpack_from('<II', d, B)
    assert cnt == len(entries_bytes)
    old_ent = [struct.unpack_from('<IIiI', d, B + 8 + 16 * i) for i in range(cnt)]
    str_start = min(e[0] for e in old_ent)
    limit = size  # 테이블 블록 크기(base 기준)
    blob = bytearray()
    offs = {}
    new_ent = []
    for (sid, b), oe in zip(entries_bytes, old_ent):
        assert oe[1] == sid
        if b in offs:   # 같은 문자열 공유
            new_ent.append(offs[b]); continue
        o = str_start + len(blob)
        offs[b] = o
        blob += b + b'\0'
        while len(blob) % 4:
            blob.append(0)
        new_ent.append(o)
    if str_start + len(blob) > limit:
        raise OverflowError('텍스트 블록 초과 %d > %d (%d 바이트 넘침)' % (str_start + len(blob), limit, str_start + len(blob) - limit))
    for i, o in enumerate(new_ent):
        struct.pack_into('<I', d, B + 8 + 16 * i, o)
    d[B + str_start:B + limit] = bytes(blob) + b'\0' * (limit - str_start - len(blob))
    return bytes(d), limit - str_start - len(blob)


def main(test=False):
    tr = load_translation()
    lvls = levels.level_entries()
    per_level = {}
    for e in [{'id': 'G'}] + lvls:
        name = 'G' if e['id'] == 'G' else 'L%02d' % e['id']
        rows = load_tsv(os.path.join(WORK, 'text', 'jp', name + '.tsv'))
        out = []
        for sid, jp in rows:
            if test:
                ko = '한글 라쳇 %X' % (sid & 0xff) if jp else ''
            else:
                ko = tr.get(jp)
                if ko is None and all(ord(c) < 0x80 for c in jp):
                    ko = jp   # 일본어 없음(크레디트 등) → 그대로
                if ko is None:
                    raise KeyError('번역 없음 %s %04X: %s' % (name, sid, jp))
            out.append((sid, normalize(ko)))
        per_level[e['id']] = out
    import collections
    scene_tr = {k: normalize(v) for k, v in scenes.load_tr().items()}
    alltexts = set(t for v in per_level.values() for _, t in v) | set(scene_tr.values())
    freq = collections.Counter(ch for t in alltexts for ch in t if '가' <= ch <= '힣')
    singles = [ch for ch, _ in sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:len(build_font.SINGLES)]]
    chars = [c for c in hangul_chars(alltexts) if c not in singles]
    print('한글 글자 수', len(chars) + len(singles), '(1바이트 %d)' % len(singles))
    font_bin = os.path.join(WORK, 'build', 'font_ko.bin')
    os.makedirs(os.path.dirname(font_bin), exist_ok=True)
    cmap = build_font.build(chars, os.path.join(WORK, 'font_pal.bin'), os.path.join(WORK, 'font_pix.bin'),
                            font_bin, preview=os.path.join(WORK, 'build', 'font_preview.png'), singles=singles)

    print('ISO 복사...')
    shutil.copyfile(SRC_ISO, OUT_ISO)
    iso = Iso(OUT_ISO)

    # ELF
    elf_out = os.path.join(WORK, 'build', 'SCPS_150.37')
    ovp = os.path.join(WORK, 'overlays.pkl')
    if os.path.exists(ovp):
        ovs = pickle.load(open(ovp, 'rb'))
    else:
        ovs = overlays.find_all(); pickle.dump(ovs, open(ovp, 'wb'))
    srcf = open(SRC_ISO, 'rb')
    def src_read(o, n):
        srcf.seek(o); return srcf.read(n)
    ov_vars = [elfpatch.overlay_variant(src_read, fd) for _, fd in ovs]
    labels = elfpatch.patch(os.path.join(WORK, 'SCPS_150.37'), elf_out, open(font_bin, 'rb').read(), ov_vars)
    elf = open(elf_out, 'rb').read()
    recs = {n: (lba, sz) for n, _, lba, sz in iso.root_records()}
    elf_lba = recs[b'SCPS_150.37;1'][0]
    iop_lba, iop_sz = recs[b'IOPRP243.IMG;1']
    iop = iso.read(iop_lba, iop_sz)
    new_iop_lba = 1500 - (iop_sz + 2047) // 2048 - 1
    elf_secs = (len(elf) + 2047) // 2048
    assert elf_lba + elf_secs <= new_iop_lba, 'ELF 공간 부족'
    iso.write(new_iop_lba, iop)
    iso.set_file(b'IOPRP243.IMG;1', new_iop_lba, iop_sz)
    iso.write(elf_lba, elf)
    iso.set_file(b'SCPS_150.37;1', elf_lba, len(elf))

    # 전역 텍스트 (비압축, ToC 677)
    W = toc.toc()
    g_lba, g_secs = W[2 * 677], W[2 * 677 + 1]
    gd = toc.read(g_lba, g_secs)
    enc = [(sid, encode(t, cmap)) for sid, t in per_level['G']]
    nd, free = rebuild_table(gd, enc, hdr=0)
    assert len(nd) == g_secs * 2048
    iso.write(g_lba, nd)
    print('G 여유 %d 바이트' % free)

    # 레벨 텍스트
    for e in lvls:
        d = open(os.path.join(WORK, 'lv', 'L%02d.bin' % e['id']), 'rb').read()
        enc = [(sid, encode(t, cmap)) for sid, t in per_level[e['id']]]
        nd, free = rebuild_table(d, enc)
        comp = wadc.compress(nd)
        lba, secs = e['subs'][1]
        need = (len(comp) + 2047) // 2048
        if need <= secs:
            iso.write(lba, comp + b'\0' * (secs * 2048 - len(comp)))
            where = 'in-place'
        else:
            nl = iso.append(comp)
            hdr = bytearray(iso.read(e['lba'], 2048))
            struct.pack_into('<II', hdr, 8 + 8 * 1, nl, need)
            iso.write(e['lba'], bytes(hdr))
            where = 'moved %x' % nl
        print('L%02d 여유 %d 바이트, 압축 %d/%d 섹터 %s' % (e['id'], free, need, secs, where))
    # 컷신 자막
    n = 0
    for off, path in scenes.scene_files():
        d = open(path, 'rb').read()
        nd = scenes.rebuild(d, scene_tr, lambda t: encode(t, cmap))
        comp = wadc.compress(nd)
        hdr = iso.read(off // 2048, 2048)[off % 2048:off % 2048 + 16]
        assert hdr[:3] == b'WAD'
        osz = struct.unpack_from('<I', hdr, 3)[0]
        if len(comp) > osz:
            raise OverflowError('장면 %x 압축 초과 %d > %d' % (off, len(comp), osz))
        assert off % 2048 == 0
        iso.write(off // 2048, comp)
        n += 1
    print('컷신 자막 파일 %d개' % n)

    # 컷신 타이틀 카드 이미지
    off = cards.CARD_ISO_OFF
    nd = cards.patch(open(os.path.join(WORK, 'cache', '%09x.bin' % off), 'rb').read())
    comp = wadc.compress(nd)
    osz = struct.unpack_from('<I', src_read(off, 16), 3)[0]
    assert len(comp) <= osz, '카드 압축 초과'
    iso.write(off // 2048, comp)
    print('타이틀 카드 완료')

    # 메뉴 레벨 HUD 이미지 (START 버튼)
    off = hudimg.MENU_ISO_OFF
    nd = hudimg.patch(open(os.path.join(WORK, 'cache', '%09x.bin' % off), 'rb').read())
    comp = wadc.compress(nd)
    osz = struct.unpack_from('<I', src_read(off, 16), 3)[0]
    assert len(comp) <= osz, 'HUD 압축 초과'
    iso.write(off // 2048, comp)
    print('START 버튼 이미지 완료')
    # 동영상 자막 (movie/enc/V###.PSS, 원본과 같은 크기)
    import movie_extract
    nm = 0
    for idx, lba, size in movie_extract.movie_entries():
        p = os.path.join(WORK, 'movie', 'enc', 'V%03d.PSS' % idx)
        if os.path.exists(p):
            mv = open(p, 'rb').read()
            assert len(mv) == size, p
            iso.write(lba, mv); nm += 1
    print('동영상 자막 %d편' % nm)

    # 레벨 코드 오버레이 패치
    for n, (tbl_off, fd) in enumerate(ovs, start=1):
        elfpatch.patch_overlay(iso.pread, iso.pwrite, tbl_off, fd, labels, n)
        lo = tbl_off - 0x300000
        for off, b in elfpatch.subtitle_patch_blob(src_read(lo, 0x600000), lo):
            iso.pwrite(off, b)
    print('코드 오버레이 %d개 패치 (자막 기본 켜기 포함)' % len(ovs))
    iso.fix_volume_size()
    iso.close()
    print('완료:', OUT_ISO)


if __name__ == '__main__':
    main(test='--test' in sys.argv)
