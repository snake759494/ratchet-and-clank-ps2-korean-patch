"""라쳇&클랭크 WAD(LZO1X 변형) 압축기.
원본 스트림 관례를 따름:
 - 0x10 헤더("WAD" + u32 전체크기 + 0 패딩)
 - 압축 데이터는 0x2000 블록 단위. 블록 끝: 12 00 00 후 0xEE 패딩, 다음 블록 시작: 11 00 00
 - 긴 리터럴(>273)은 11 00 00(무동작) 으로 분할
 - 확장 길이 바이트는 0을 쓰지 않음(단일 바이트 확장만 사용)
"""
import struct

BLK = 0x2000
MAX_LIT = 15 + 255 + 3          # 273
M2_MAXD, M3_MAXD, M4_MAXD = 0x800, 0x4000, 0xBFFF
M3_MAXL = 31 + 255 + 2          # 288
M4_MAXL = 7 + 255 + 2           # 264


def _lit_run_bytes(n):
    """state0 리터럴 런 토큰(n>=4)"""
    if n - 3 <= 15:
        return bytes([n - 3])
    return bytes([0, n - 18])


def _match_bytes(dist, length, trail):
    """매치 토큰 (trail = 뒤따르는 리터럴 수 0..3)"""
    if 3 <= length <= 8 and dist <= M2_MAXD:
        d = dist - 1
        t = ((length - 1) << 5) | ((d & 7) << 2) | trail
        return bytes([t, d >> 3])
    if dist <= M3_MAXD:
        d = dist - 1
        n = length - 2
        if n <= 31:
            head = bytes([0x20 | n])
        else:
            head = bytes([0x20, n - 31])
        v = (d << 2) | trail
        return head + bytes([v & 0xff, v >> 8])
    d = dist - 0x4000
    hi = 8 if d >= 0x4000 else 0
    d &= 0x3fff
    n = length - 2
    if n <= 7:
        head = bytes([0x10 | hi | n])
    else:
        head = bytes([0x10 | hi, n - 7])
    v = (d << 2) | trail
    return head + bytes([v & 0xff, v >> 8])


def compress(data):
    n = len(data)
    out = bytearray(b'\0' * 0x10)
    # 매치 찾기용 해시 체인
    head = {}
    prev = [-1] * n

    def insert(i):
        if i + 3 <= n:
            k = data[i:i + 3]
            prev[i] = head.get(k, -1)
            head[k] = i

    def find(i):
        if i + 3 > n:
            return 0, 0
        k = data[i:i + 3]
        j = head.get(k, -1)
        best_l, best_d = 0, 0
        tries = 0
        lim = min(n - i, M3_MAXL)
        while j >= 0 and tries < 48:
            d = i - j
            if d > M4_MAXD:
                break
            if d == 0x4000:  # 예약(마커) 거리
                j = prev[j]; tries += 1; continue
            maxl = lim if d <= M3_MAXD else min(lim, M4_MAXL)
            if data[j + best_l:j + best_l + 1] == data[i + best_l:i + best_l + 1] if best_l < maxl else False:
                l = 0
                while l < maxl and data[j + l] == data[i + l]:
                    l += 1
                cost_ok = (l >= 3 and d <= M2_MAXD) or (l >= 3 and d <= M3_MAXD) or l >= 4
                if cost_ok and l > best_l:
                    best_l, best_d = l, d
                    if l == maxl:
                        break
            j = prev[j]; tries += 1
        return best_l, best_d

    # 토큰 목록 생성: ('L', bytes) / ('M', dist, len)
    toks = []
    i = 0
    lit_start = 0
    while i < n:
        l, d = find(i)
        if l >= 3:
            if i > lit_start:
                toks.append(('L', lit_start, i))
            toks.append(('M', d, l))
            for k in range(i, i + l):
                insert(k)
            i += l
            lit_start = i
        else:
            insert(i)
            i += 1
    if n > lit_start:
        toks.append(('L', lit_start, n))

    # 바이트 스트림 출력 (블록 경계 고려)
    blk_end = 0x10 + BLK
    state = 0   # 0: 직전이 매치(trail 0) 또는 시작, 1: 리터럴 런 직후, 2: trail 리터럴 직후

    def room():
        return blk_end - 3 - len(out)

    def new_block():
        nonlocal blk_end, state
        out.extend(b'\x12\x00\x00')
        while len(out) < blk_end:
            out.append(0xEE)
        blk_end += BLK
        out.extend(b'\x11\x00\x00')
        state = 0

    def emit(b):
        if len(b) > room():
            new_block()
        out.extend(b)

    k = 0
    pending_trail_slot = None   # 직전 매치 토큰의 trail 비트 위치 (out 인덱스)
    while k < len(toks):
        t = toks[k]
        if t[0] == 'L':
            s, e = t[1], t[2]
            while s < e:
                m = e - s
                if state != 1 and pending_trail_slot is not None and m <= 3 and pending_trail_slot[1] >= len(out) - 3 and room() >= m:
                    # 직전 매치에 trail 리터럴로 붙임
                    pos = pending_trail_slot[0]
                    out[pos] |= m
                    out.extend(data[s:e]); s = e
                    state = 2
                    pending_trail_slot = None
                    break
                if state != 0:
                    # 리터럴 런 시작 전 상태 0으로 (무동작 매치)
                    emit(b'\x11\x00\x00'); state = 0
                    pending_trail_slot = None
                if m < 4:
                    # 3 이하 리터럴: 무동작 매치의 trail 로 표현
                    b = bytes([0x11, m, 0x00]) + data[s:e]
                    if len(b) > room():
                        new_block()
                        # 새 블록 시작 11 00 00 의 trail 비트 활용
                        out[-2] = m
                        out.extend(data[s:e])
                    else:
                        out.extend(b)
                    s = e; state = 2; pending_trail_slot = None
                    break
                take = min(m, MAX_LIT)
                if m - take in (1, 2, 3):
                    take -= 4 - (m - take) if take - (4 - (m - take)) >= 4 else 0
                take = min(take, max(4, room() - 2))
                if room() < 6:
                    new_block()
                    take = min(m, MAX_LIT)
                    if m - take in (1, 2, 3) and take - 4 >= 4:
                        take -= 4
                hdr = _lit_run_bytes(take)
                out.extend(hdr); out.extend(data[s:s + take])
                s += take; state = 1; pending_trail_slot = None
                if s < e:
                    emit(b'\x11\x00\x00'); state = 0
            k += 1
        else:
            _, d, l = t
            b = _match_bytes(d, l, 0)
            if len(b) + 3 > room():
                new_block()
            out.extend(b)
            # trail 비트 위치: M2 는 첫 바이트, M3/M4 는 v 하위바이트(끝에서 2번째)
            if b[0] >= 0x40:
                pos = len(out) - 2
            else:
                pos = len(out) - 2
            pending_trail_slot = (pos, len(out))
            state = 0
            k += 1
    total = len(out)
    out[0:0x10] = b'WAD' + struct.pack('<I', total) + b'\0' * 9
    return bytes(out)
