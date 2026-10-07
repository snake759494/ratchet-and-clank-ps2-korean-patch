"""동영상 음성 한국어 자막 합성 (movie/subs/<이름>.tsv: 시작초	끝초	자막, 줄바꿈은 \n).

python tools/movie_sub.py [이름 ...]   -> movie/enc/<이름>.PSS  (원본과 같은 크기)

원본: MPEG-PS, 512x416 30fps 프로그레시브, 4Mbps, VBV 1,310,720비트, GOP 18, 음성 SShd PS-ADPCM 48kHz.
바뀐 프레임이 든 GOP 구간만 닫힌 GOP로 재인코딩하고, 구간 바이트가 원본 이하가 되는 가장 고운 q를 고른 뒤
남는 바이트는 0으로 채워 비디오 ES 길이를 원본과 같게 맞춰 PES 자리에 되돌려 쓴다(간츠·블랙 방식).
자막: 흰 글자 + 검은 테두리, 대사 글자와 같은 크기, 화면 아래 가운데. 640폭에서 그린 뒤 512폭으로 줄여 합성.
"""
import os, sys, json, subprocess
import numpy as np
import av
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pss, paths

M = os.path.join(paths.WORK, 'movie')
W, H = 512, 416
FPS = 30
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SUB_FONT = ImageFont.truetype(os.path.join(paths.FONT_DIR, 'NanumSquareNeo-cBd.ttf'), 19)
Q_STEPS = [2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 17, 20, 24, 28]


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
        i = es.find(b'\x00\x00\x01\xb8', i)
        if i < 0: break
        st.append(i); i += 4
    st[0] = 0
    end = len(es) - 4 if es.endswith(b'\x00\x00\x01\xb7') else len(es)
    return [(s, st[k + 1] if k + 1 < len(st) else end) for k, s in enumerate(st)]


def nframes(es, a, b):
    return es.count(b'\x00\x00\x01\x00', a, b)


def encode(frames, q):
    cmd = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
           '-c:v', 'mpeg2video', '-pix_fmt', 'yuv420p', '-qscale:v', str(q), '-qmin', '1', '-qmax', '28',
           '-g', '18', '-bf', '2', '-flags', '+cgop', '-sc_threshold', '1000000000',
           '-alternate_scan', '1', '-intra_vlc', '1', '-non_linear_quant', '1', '-dc', '10',
           '-maxrate', '4000000', '-bufsize', '1310720', '-aspect', '16:13', '-seq_disp_ext', 'never',
           '-f', 'mpeg2video', '-']
    r = subprocess.run(cmd, input=b''.join(f.tobytes() for f in frames), capture_output=True)
    if r.returncode: raise RuntimeError(r.stderr.decode())
    es = r.stdout
    return es[:-4] if es.endswith(b'\x00\x00\x01\xb7') else es


def process(name):
    src = open(os.path.join(M, 'orig', name + '.PSS'), 'rb').read()
    es = pss.video_es(src); gops = split_gops(es)
    nf = [nframes(es, a, b) for a, b in gops]; first = np.cumsum([0] + nf); total = int(first[-1])
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
    hit = [changed[first[g]:first[g + 1]].any() for g in range(len(gops))]
    runs, g = [], 0
    while g < len(gops):
        if hit[g]:
            h = g
            while h + 1 < len(gops) and hit[h + 1]: h += 1
            runs.append((g, h)); g = h + 1
        else: g += 1
    out = bytearray(); prev = 0; qs = []
    for a, b in runs:
        out += es[prev:gops[a][0]]
        seg = [frames[k] for k in range(first[a], first[b + 1])]
        budget = gops[b][1] - gops[a][0]
        for q in Q_STEPS:
            enc = encode(seg, q)
            if len(enc) <= budget: break
        assert len(enc) <= budget, (name, a, b, len(enc), budget)
        k = 0; cnt = enc.count(b'\x00\x00\x01\x00')
        assert cnt == len(seg), (cnt, len(seg))
        out += enc + b'\0' * (budget - len(enc)); prev = gops[b][1]; qs.append(q)
    out += es[prev:]
    assert len(out) == len(es)
    dst = pss.put_video_es(src, bytes(out))
    assert len(dst) == len(src)
    open(os.path.join(M, 'enc', name + '.PSS'), 'wb').write(dst)
    # 미리보기
    pv = os.path.join(M, 'preview'); os.makedirs(pv, exist_ok=True)
    idx = np.where(changed)[0]
    for k in idx[::max(1, len(idx) // 6)][:6]:
        Image.fromarray(frames[k]).save(os.path.join(pv, f'{name}_{k:04d}.png'))
    print(name, '바뀐 프레임', int(changed.sum()), '구간', len(runs), 'q', qs, flush=True)


if __name__ == '__main__':
    import glob
    names = sys.argv[1:] or sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(M, 'subs', '*.tsv')))
    for n in names:
        process(n)
