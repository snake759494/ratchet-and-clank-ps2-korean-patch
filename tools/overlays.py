"""레벨 코드 오버레이(디스크 비압축 사본) 탐색"""
import os, sys, mmap
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import elf, sig
import paths
ISO = paths.ISO
FUNCS = {'tex': 0x1F4DC8, 'q': 0x1F5D60, 's': 0x1F6118, 'brA': 0x1F6D40, 'brS': 0x1F73C8}
TBL = 0x1DFCB0


def find_all():
    f = open(ISO, 'rb'); m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    key = elf.rd(TBL + 0x200, 64)
    hits = []
    i = m.find(key)
    while i >= 0:
        hits.append(i); i = m.find(key, i + 1)
    pats = {k: sig.masked(v, 16) for k, v in FUNCS.items()}
    out = []
    for H in hits:
        if H == 0x171e30:   # ELF 자체
            continue
        lo, hi = max(0, H - 0x300000), H + 0x300000
        win = m[lo:hi]
        found = {}
        for k, p in pats.items():
            ms = [lo + x.start() for x in p.finditer(win)]
            found[k] = ms
        out.append((H - 0x200, found))   # 글리프 테이블 시작 ISO 오프셋
    return out


if __name__ == '__main__':
    for t, fd in find_all():
        print(hex(t), {k: [hex(x) for x in v] for k, v in fd.items()})
