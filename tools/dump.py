import sys,re,struct,os;sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)));import wad,toc,paths
os.chdir(paths.WORK);os.makedirs('cache',exist_ok=True)
data=open(toc.ISO,'rb').read()
for m in re.finditer(b'WAD',data):
    p=m.start()
    if p%16: continue
    sz=struct.unpack('<I',data[p+3:p+7])[0]
    if sz<32 or sz>64<<20: continue
    try:o,ip,end=wad.decompress(data[p:p+sz])
    except Exception: continue
    if len(o)>=256: open('cache/%09x.bin'%p,'wb').write(o)
