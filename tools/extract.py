import sys,struct,os,json
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import toc,wad,levels,jpcode,paths
os.chdir(paths.WORK)
os.makedirs('text/jp',exist_ok=True)
allr={}
for e in levels.level_entries():
    lba,sz=e['subs'][1]
    os.makedirs('lv',exist_ok=True)
    p='lv/L%02d.bin'%e['id']
    if os.path.exists(p): d=open(p,'rb').read()
    else:
        raw=toc.read(lba,sz);d,_,_=wad.decompress(raw);open(p,'wb').write(d)
    B=struct.unpack_from('<I',d,0x10)[0]
    cnt,size=struct.unpack_from('<II',d,B)
    rows=[]
    for i in range(cnt):
        o,sid,m,z=struct.unpack_from('<IIiI',d,B+8+16*i)
        s=d[B+o:].split(b'\0')[0]
        rows.append((sid,s))
    with open('text/jp/L%02d.tsv'%e['id'],'w',encoding='utf-8') as f:
        for sid,s in rows: f.write('%04X\t%s\n'%(sid,jpcode.decode(s)))
    print(e['id'],cnt,hex(size),len(d),flush=True)
