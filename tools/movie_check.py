"""동영상 검사: 1) 원본보다 늦게 도착하는 프레임 0  2) 자막이 없는 프레임은 원본과 픽셀 동일(행렬·헤더 오염 없음)
python tools/movie_check.py [이름 ...]"""
import os, sys, glob, av, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths, pss, mux_check, movie_sub
M = os.path.join(paths.WORK, 'movie')


def frames(d):
    tmp = os.path.join(M, '_chk.m2v'); open(tmp, 'wb').write(pss.video_es(d))
    c = av.open(tmp); f = [x.to_ndarray(format='rgb24') for x in c.decode(video=0)]; c.close(); os.remove(tmp)
    return f


names = sys.argv[1:] or sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(M, 'subs', '*.tsv')))
tot = 0
for n in names:
    a = open(os.path.join(M, 'orig', n + '.PSS'), 'rb').read(); b = open(os.path.join(M, 'enc', n + '.PSS'), 'rb').read()
    late = mux_check.compare(a, b)
    fa, fb = frames(a), frames(b)
    es = pss.video_es(b); gops = movie_sub.split_gops(es)
    eo = pss.video_es(a)
    same_gop = [eo[x:y] == es[x:y] for x, y in gops]
    nf = [es.count(movie_sub.PIC, x, y) for x, y in gops]; first = np.cumsum([0] + nf)
    diff = 0
    for g, same in enumerate(same_gop):
        if same:
            for k in range(first[g] + 2, first[g + 1]):     # 열린 GOP 앞 B 2장 제외
                if not np.array_equal(fa[k], fb[k]): diff += 1
    ok = len(late) == 0 and diff == 0 and len(fa) == len(fb)
    tot += 0 if ok else 1
    print(n, '늦음', len(late), '원본구간 불일치', diff, '프레임', len(fa), len(fb), 'OK' if ok else 'NG', flush=True)
print('문제', tot)
