"""PSS (MPEG-PS) helpers: iterate PES packets, extract video ES / SShd-SSbd PCM audio, write video ES back in place."""
import struct
import numpy as np

def packets(d):
    """yield (sid, payload_start, payload_end) for each PES packet"""
    i = 0
    while i < len(d) - 4:
        if d[i:i + 3] != b'\0\0\1': i += 1; continue
        sid = d[i + 3]
        if sid == 0xba: i += 14 + (d[i + 13] & 7); continue
        if sid == 0xb9: break
        ln = struct.unpack('>H', d[i + 4:i + 6])[0]
        if sid in (0xe0, 0xbd):
            hl = d[i + 8]; ps = i + 9 + hl
            if sid == 0xbd: ps += 4           # substream id + 3 bytes
            yield sid, ps, i + 6 + ln
        i += 6 + ln

def video_es(d):
    return b''.join(d[a:b] for s, a, b in packets(d) if s == 0xe0)

def put_video_es(d, es):
    d = bytearray(d); o = 0
    for s, a, b in packets(bytes(d)):
        if s == 0xe0: d[a:b] = es[o:o + b - a]; o += b - a
    assert o == len(es), (o, len(es))
    return bytes(d)

def audio(d):
    """-> (int16 array [n, ch], rate)"""
    raw = b''.join(d[a:b] for s, a, b in packets(d) if s == 0xbd)
    assert raw[:4] == b'SShd'
    hl = struct.unpack_from('<I', raw, 4)[0]
    typ, rate, ch, inter = struct.unpack_from('<IIII', raw, 8)
    body = raw[8 + hl:]
    assert body[:4] == b'SSbd'
    pcm = body[8:]
    blk = inter * ch; n = len(pcm) // blk
    a = np.frombuffer(pcm[:n * blk], '<i2').reshape(n, ch, inter // 2)
    return a.transpose(0, 2, 1).reshape(-1, ch), rate

# ---------- PS-ADPCM (SShd type 0x10) ----------
_F = [(0, 0), (60, 0), (115, -52), (98, -55), (122, -60)]


def adpcm_decode(buf):
    """PS2 VAG ADPCM 바이트 -> int16 numpy (모노)"""
    n = len(buf) // 16
    out = np.zeros(n * 28, np.int16)
    s1 = s2 = 0
    for k in range(n):
        f = buf[16 * k:16 * k + 16]
        sh = f[0] & 15; fi = (f[0] >> 4) & 7
        if fi > 4: fi = 0
        f0, f1 = _F[fi]
        for j in range(28):
            b = f[2 + j // 2]
            nib = (b >> 4) if j & 1 else (b & 15)
            if nib >= 8: nib -= 16
            v = (nib << 12) >> sh
            v += (s1 * f0 + s2 * f1 + 32) >> 6
            v = max(-32768, min(32767, v))
            out[28 * k + j] = v; s2 = s1; s1 = v
    return out


def audio_adpcm(d, inter=None):
    raw = b''.join(d[a:b] for s, a, b in packets(d) if s == 0xbd)
    hl = struct.unpack_from('<I', raw, 4)[0]
    typ, rate, ch, it = struct.unpack_from('<IIII', raw, 8)
    body = raw[8 + hl:]; data = body[8:]
    inter = inter or it
    blk = inter * ch; n = len(data) // blk
    chans = [b''.join(data[i * blk + c * inter:i * blk + (c + 1) * inter] for i in range(n)) for c in range(ch)]
    return np.stack([adpcm_decode(x) for x in chans], 1), rate
