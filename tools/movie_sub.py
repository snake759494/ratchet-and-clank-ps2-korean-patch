"""동영상 음성 한국어 자막 합성 (movie/subs/<이름>.tsv: 시작초<TAB>끝초<TAB>자막, 줄바꿈은 \\n).

python tools/movie_sub.py [이름 ...]   -> movie/enc/<이름>.PSS  (원본과 같은 크기)

원본: MPEG-PS, 512x416 30fps 프로그레시브, 4Mbps, VBV 1,310,720비트, GOP 18, 음성 SShd PS-ADPCM 48kHz.
자막이 걸린 GOP 를 하나씩 닫힌 GOP 로 재인코딩한다. 이때 그림(디코드 순서)마다 누적 바이트가
원본의 누적 바이트 이하가 되는 가장 고운 q 를 고른다. 그래야 각 프레임 데이터가 원본보다 늦게
도착하지 않아 디코더가 멈추지 않는다(멈추면 음성이 반복돼 끊겨 들림). GOP 의 남는 바이트는 0 으로
채워 원래 GOP 자리·길이를 그대로 지키고, 영상 ES 를 원래 PES 자리에 되돌려 쓴다(음성 패킷은 그대로).
조건을 맞출 수 없는 GOP 는 원본을 유지한다.
자막: 흰 글자 + 검은 테두리, 화면 아래 가운데. 640폭에서 그린 뒤 512폭으로 줄여 합성.
"""
import os, sys, subprocess
import numpy as np
import av
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pss, paths

M = os.path.join(paths.WORK, 'movie')
W, H = 512, 416
FPS = 30
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SUB_FONT = ImageFont.truetype(os.path.join(paths.FONT_DIR, 'NanumSquareNeo-cBd.ttf'), 19)
MARGIN = 4096                       # 팩 하나 여유 (경계에서 한 팩 늦어지는 것 방지)
Q_STEPS = [2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 17, 20, 24, 28]
PIC = bytes([0, 0, 1, 0])          # picture_start_code
GOP_SC = bytes([0, 0, 1, 0xB8])
SEQ_END = bytes([0, 0, 1, 0xB7])


# ---------- 자막 ----------
def wrap(text, maxw=600):
    """640폭 기준 maxw 를 넘으면 가운데 가까운 공백에서 줄바꿈 (최대 2줄)"""
    out = []
    for ln in text.split('\\n'):
        if SUB_FONT.getlength(ln) <= maxw or ' ' not in ln:
            out.append(ln); continue
        mid = len(ln) // 2
        sp = [i for i, c in enumerate(ln) if c == ' ']
        k = min(sp, key=lambda i: abs(i - mid))
        out += [ln[:k], ln[k + 1:]]
    return out


def render_sub(text):
    im = Image.new('RGBA', (640, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    lines = wrap(text); lh = 24; y = H - 30 - lh * len(lines)
    for ln in lines:
        d.text((320, y + lh / 2), ln, font=SUB_FONT, anchor='mm', fill=(255, 255, 255, 255),
               stroke_width=2, stroke_fill=(0, 0, 0, 255))
        y += lh
    return im.resize((W, H), Image.LANCZOS)


def load_subs(name):
    p = os.path.join(M, 'subs', name + '.tsv'); out = []
    if os.path.exists(p):
        for ln in open(p, encoding='utf-8').read().splitlines():
            if ln.strip() and not ln.startswith('#'):
                s, e, t = ln.split('\t', 2); out.append((float(s), float(e), t))
    return out


# ---------- MPEG ----------
def split_gops(es):
    st = []; i = 0
    while True:
        i = es.find(GOP_SC, i)
        if i < 0: break
        st.append(i); i += 4
    st[0] = 0
    end = len(es) - 4 if es.endswith(SEQ_END) else len(es)
    return [(s, st[k + 1] if k + 1 < len(st) else end) for k, s in enumerate(st)]


def pic_ends(es, a, b):
    """[a,b) 안 각 그림(디코드 순서)의 데이터 끝까지의 누적 바이트(a 기준)"""
    st = []; i = es.find(PIC, a)
    while 0 <= i < b:
        st.append(i); i = es.find(PIC, i + 4)
    return [x - a for x in st[1:]] + [b - a]


ZIGZAG = [0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5, 12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6,
          7, 14, 21, 28, 35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51, 58, 59, 52, 45, 38, 31,
          39, 46, 53, 60, 61, 54, 47, 55, 62, 63]


class Bits:
    def __init__(self, b, pos): self.b = b; self.p = pos * 8

    def get(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | ((self.b[self.p >> 3] >> (7 - (self.p & 7))) & 1); self.p += 1
        return v


def seq_matrices(es):
    """원본 시퀀스 헤더의 양자화 행렬 (래스터 순서) -> (intra, inter) 또는 None"""
    i = es.find(bytes([0, 0, 1, 0xB3]))
    r = Bits(es, i + 4); r.get(12); r.get(12); r.get(4); r.get(4); r.get(18); r.get(1); r.get(10); r.get(1)
    mats = []
    for _ in range(2):
        if r.get(1):
            m = [0] * 64
            for k in range(64): m[ZIGZAG[k]] = r.get(8)
            mats.append(m)
        else:
            mats.append(None)
    return mats


MATS = [None, None]


def strip_seq(enc):
    """GOP 헤더 앞의 시퀀스 헤더·확장 제거 (원본 스트림처럼 맨 앞에만 둔다)"""
    return enc[enc.find(GOP_SC):]


def encode(frames, q):
    mat = []
    if MATS[0]: mat += ['-intra_matrix', ','.join(map(str, MATS[0]))]
    if MATS[1]: mat += ['-inter_matrix', ','.join(map(str, MATS[1]))]
    cmd = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
           '-c:v', 'mpeg2video', '-pix_fmt', 'yuv420p', '-qscale:v', str(q), '-qmin', '1', '-qmax', '28',
           '-g', '18', '-bf', '2', '-flags', '+cgop', '-sc_threshold', '1000000000',
           '-alternate_scan', '1', '-intra_vlc', '1', '-non_linear_quant', '1', '-dc', '10',
           '-maxrate', '4000000', '-bufsize', '1310720', '-aspect', '16:13', '-seq_disp_ext', 'never',
           ] + mat + ['-f', 'mpeg2video', '-']
    r = subprocess.run(cmd, input=b''.join(f.tobytes() for f in frames), capture_output=True)
    if r.returncode: raise RuntimeError(r.stderr.decode())
    es = r.stdout
    return es[:-4] if es.endswith(SEQ_END) else es


def process(name):
    src = open(os.path.join(M, 'orig', name + '.PSS'), 'rb').read()
    es = pss.video_es(src); gops = split_gops(es)
    MATS[:] = seq_matrices(es)
    nf = [es.count(PIC, a, b) for a, b in gops]; first = np.cumsum([0] + nf); total = int(first[-1])
    tmp = os.path.join(M, 'enc', name + '.m2v'); os.makedirs(os.path.dirname(tmp), exist_ok=True)
    open(tmp, 'wb').write(es)
    c = av.open(tmp); orig = np.stack([f.to_ndarray(format='rgb24') for f in c.decode(video=0)]); c.close(); os.remove(tmp)
    assert len(orig) == total, (len(orig), total)
    frames = orig.copy()
    cache = {}
    for s, e, t in load_subs(name):
        if t not in cache: cache[t] = render_sub(t)
        for k in range(int(round(s * FPS)), min(total, int(round(e * FPS)))):
            base = Image.fromarray(frames[k]).convert('RGBA'); base.alpha_composite(cache[t])
            frames[k] = np.asarray(base.convert('RGB'))
    changed = np.array([not np.array_equal(frames[k], orig[k]) for k in range(total)])
    out = bytearray(es); qs = []; kept = 0
    for g, (a0, b0) in enumerate(gops):
        if not changed[first[g]:first[g + 1]].any():
            continue
        seg = [frames[k] for k in range(first[g], first[g + 1])]
        o_ends = pic_ends(es, a0, b0)
        best = None
        for q in Q_STEPS:
            enc = encode(seg, q)
            if g > 0: enc = strip_seq(enc)
            assert enc.count(PIC) == len(seg), (name, g, enc.count(PIC), len(seg))
            n_ends = pic_ends(enc, 0, len(enc))
            if len(enc) <= b0 - a0 and all(n <= o - MARGIN for n, o in zip(n_ends[:-1], o_ends[:-1])):
                best = (q, enc); break
        if best is None:
            kept += 1; continue
        q, enc = best
        out[a0:b0] = enc + bytes(b0 - a0 - len(enc)); qs.append(q)
    assert len(out) == len(es)
    dst = pss.put_video_es(src, bytes(out))
    assert len(dst) == len(src)
    open(os.path.join(M, 'enc', name + '.PSS'), 'wb').write(dst)
    pv = os.path.join(M, 'preview'); os.makedirs(pv, exist_ok=True)
    idx = np.where(changed)[0]
    for k in idx[::max(1, len(idx) // 6)][:6]:
        Image.fromarray(frames[k]).save(os.path.join(pv, f'{name}_{k:04d}.png'))
    print(name, '바뀐 프레임', int(changed.sum()), 'GOP', len(qs), '원본유지', kept,
          'q', sorted(set(qs)), flush=True)


if __name__ == '__main__':
    import glob
    names = sys.argv[1:] or sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(M, 'subs', '*.tsv')))
    for n in names:
        process(n)
