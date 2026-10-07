"""faster-whisper 로 동영상 음성 받아쓰기 -> movie/asr/V###.json"""
import os, sys, json, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import paths
from faster_whisper import WhisperModel
M = os.path.join(paths.WORK, 'movie')
os.makedirs(os.path.join(M, 'asr'), exist_ok=True)
model = WhisperModel('large-v3', device='cpu', compute_type='int8', cpu_threads=os.cpu_count())
names = sys.argv[1:] or sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(M, 'wav', '*.wav')))
for n in names:
    out = os.path.join(M, 'asr', n + '.json')
    if os.path.exists(out):
        continue
    segs, info = model.transcribe(os.path.join(M, 'wav', n + '.wav'), language='ja', vad_filter=True,
                                  beam_size=5, condition_on_previous_text=False)
    rows = [dict(s=round(s.start, 2), e=round(s.end, 2), t=s.text.strip()) for s in segs]
    json.dump(rows, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(n, len(rows), flush=True)
