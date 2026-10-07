"""PSS 타이밍 검사: 각 영상 프레임의 마지막 바이트가 도착하는 팩 SCR 이 그 프레임 DTS 보다 늦으면 위반(재생 끊김 원인).
python tools/mux_check.py <PSS 파일...>"""
import sys, struct


def scr(d, i):
    b = d[i + 4:i + 10]
    return (((b[0] >> 3) & 7) << 30 | (b[0] & 3) << 28 | b[1] << 20 | ((b[2] >> 3) & 31) << 15 |
            (b[2] & 3) << 13 | b[3] << 5 | (b[4] >> 3))


def ts(b):
    return ((b[0] >> 1) & 7) << 30 | b[1] << 22 | (b[2] >> 1) << 15 | b[3] << 7 | (b[4] >> 1)


def analyze(d):
    """반환: [(프레임 번호, 도착-디코딩 시각 차 ms)] 위반 목록, 프레임 수"""
    es_pos = 0; cur_scr = 0
    chunks = []      # (es 시작, es 끝, scr, dts or None)
    i = 0
    while i < len(d) - 4:
        if d[i:i + 3] != b'\0\0\1': i += 1; continue
        sid = d[i + 3]
        if sid == 0xba:
            cur_scr = scr(d, i); i += 14 + (d[i + 13] & 7); continue
        if sid == 0xb9: break
        ln = struct.unpack('>H', d[i + 4:i + 6])[0]
        if sid == 0xe0:
            flags = d[i + 7]; hl = d[i + 8]; ps = i + 9 + hl; pe = i + 6 + ln
            dts = None
            if flags & 0x80:
                p = ts(d[i + 9:i + 14]); dts = ts(d[i + 14:i + 19]) if flags & 0x40 else p
            chunks.append((es_pos, es_pos + pe - ps, cur_scr, dts, ps))
            es_pos += pe - ps
        i += 6 + ln
    es = b''.join(d[c[4]:c[4] + c[1] - c[0]] for c in chunks)
    # 프레임 시작 위치 (ES 내)
    pics = []; k = es.find(b'\0\0\1\0')
    while k >= 0: pics.append(k); k = es.find(b'\0\0\1\0', k + 4)
    # 프레임 DTS: 원본 PES 의 DTS 를 프레임 순서로 (1프레임 = 3003 또는 3000 단위)
    dts_list = [c[3] for c in chunks if c[3] is not None]
    t0 = dts_list[0]; step = 3000
    # 프레임 k 의 데이터 끝 = 다음 프레임 시작
    ends = pics[1:] + [len(es)]
    import bisect
    starts = [c[0] for c in chunks]
    arr = []
    for k, e in enumerate(ends):
        j = bisect.bisect_right(starts, max(0, e - 1)) - 1
        arr.append(chunks[j][2])
    return arr


def compare(orig, new):
    """원본보다 늦게 도착하는 프레임 [(프레임, 늦은 ms)]"""
    a, b = analyze(orig), analyze(new)
    assert len(a) == len(b)
    return [(k, (y - x) / 90) for k, (x, y) in enumerate(zip(a, b)) if y > x]


if __name__ == '__main__':
    o, n = sys.argv[1], sys.argv[2]
    bad = compare(open(o, 'rb').read(), open(n, 'rb').read())
    print('원본보다 늦게 도착한 프레임', len(bad), '최대 %.0fms' % max([b for _, b in bad], default=0))
