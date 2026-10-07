"""ToC 의 동영상(PSS) 추출 -> movie/orig/V###.PSS, movie/wav/V###.wav (16kHz 모노)"""
import os, sys, struct, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import paths, pss, numpy as np, imageio_ffmpeg
M = os.path.join(paths.WORK, 'movie')


def movie_entries():
    f = open(paths.ISO, 'rb'); f.seek(1500 * 2048 + 760 * 8); d = f.read(8 * 100)
    out = []
    for k in range(100):
        lba, size = struct.unpack_from('<II', d, 8 * k)
        if lba and size > 100000:
            f.seek(lba * 2048)
            if f.read(4) == b'\0\0\1\xba':
                out.append((760 + k, lba, size))
    return out


if __name__ == '__main__':
    os.makedirs(os.path.join(M, 'orig'), exist_ok=True); os.makedirs(os.path.join(M, 'wav'), exist_ok=True)
    f = open(paths.ISO, 'rb')
    for idx, lba, size in movie_entries():
        name = 'V%03d' % idx
        if os.path.exists(os.path.join(M, 'wav', name + '.wav')): continue
        f.seek(lba * 2048); d = f.read(size)
        open(os.path.join(M, 'orig', name + '.PSS'), 'wb').write(d)
        a, rate = pss.audio_adpcm(d)
        mono = a.astype(np.int32).mean(1).astype(np.int16)
        tmp = os.path.join(M, 'wav', name + '.raw'); mono.tofile(tmp)
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-y', '-f', 's16le',
                        '-ar', str(rate), '-ac', '1', '-i', tmp, '-ar', '16000', os.path.join(M, 'wav', name + '.wav')], check=True)
        os.remove(tmp)
        print(name, hex(lba), size, '%.1fs' % (len(mono) / rate), flush=True)
