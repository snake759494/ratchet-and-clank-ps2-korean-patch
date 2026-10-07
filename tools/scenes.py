"""컷신 자막(장면 WAD) 처리"""
import os, struct, glob, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jpcode
WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse(d):
    if len(d) < 16 or struct.unpack_from('<I', d, 8)[0] != 0xfffffffa:
        return None
    b = struct.unpack_from('<I', d, 4)[0]
    if not (0 < b < len(d)):
        return None
    ents = []
    p = b
    while struct.unpack_from('<I', d, p)[0] != 0xffffffff:
        ents.append(list(struct.unpack_from('<8H', d, p)))
        p += 16
    return b, ents, p


def scene_files():
    """(iso_offset, cache_path) 자막이 1개 이상 있는 장면 WAD"""
    out = []
    for fn in sorted(glob.glob(os.path.join(WORK, 'cache', '*.bin'))):
        with open(fn, 'rb') as f:
            h = f.read(16)
        if len(h) < 16 or struct.unpack_from('<I', h, 8)[0] != 0xfffffffa:
            continue
        d = open(fn, 'rb').read()
        r = parse(d)
        if r and r[1]:
            out.append((int(os.path.basename(fn)[:-4], 16), fn))
    return out


def load_tr():
    src = {}
    for l in open(os.path.join(WORK, 'text', 'scene_src.tsv'), encoding='utf-8'):
        i, _, t = l.rstrip('\n').partition('\t')
        src[i] = t
    tr = {}
    for p in glob.glob(os.path.join(WORK, 'translation', 'scene_ko', '*.tsv')):
        for l in open(p, encoding='utf-8'):
            l = l.rstrip('\n')
            if l:
                i, _, t = l.partition('\t')
                tr[src[i]] = t
    return tr


def rebuild(d, tr, enc):
    """d: 장면 파일, tr: 원문→번역, enc: 문자열→바이트"""
    b, ents, p = parse(d)
    end = len(d)
    head = bytearray()
    strs = bytearray(b'\0\0\0\0')  # 공용 빈 문자열 (오프셋 = 표 끝)
    tbl_size = len(ents) * 16 + 16
    pool = {}
    texts = []
    for e in ents:
        jp = jpcode.decode(d[b + e[2]:].split(b'\0')[0])
        ko = tr.get(jp)
        if ko is None:
            raise KeyError('자막 번역 없음: ' + jp)
        texts.append(enc(ko))
    body = bytearray()
    offs = []
    for t in texts:
        if t in pool:
            offs.append(pool[t]); continue
        o = tbl_size + 4 + len(body)
        pool[t] = o
        offs.append(o)
        body += t + b'\0'
        while len(body) % 4:
            body.append(0)
    out = bytearray()
    for e, o in zip(ents, offs):
        out += struct.pack('<8H', e[0], e[1], o, tbl_size, tbl_size, tbl_size, tbl_size, 0)
    out += b'\xff\xff\xff\xff' + b'\0' * 12
    out += b'\0\0\0\0' + body
    room = end - b
    if len(out) > room:
        raise OverflowError('자막 블록 초과 %d > %d' % (len(out), room))
    nd = bytearray(d)
    nd[b:end] = bytes(out) + b'\0' * (room - len(out))
    return bytes(nd)
