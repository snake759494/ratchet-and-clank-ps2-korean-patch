import struct,sys
import os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import toc
def level_entries():
    f=open(toc.ISO,'rb');f.seek(1500*2048);raw=f.read(0x60*2048)
    w=struct.unpack('<%dI'%(len(raw)//4),raw)
    out=[]
    for i in range(0,len(w)-1,2):
        lba,sz=w[i],w[i+1]
        if lba<0x1000 or sz==0: continue
        f.seek(lba*2048);bb=f.read(40)
        if len(bb)<40: continue
        h=struct.unpack("<10I",bb)
        if h[1]==0x2434 and h[2]==lba+5:
            out.append(dict(toc_word=i,lba=lba,size=sz,id=h[0],subs=[(h[2+2*k],h[3+2*k]) for k in range(4)]))
    return out
if __name__=='__main__':
    for e in level_entries(): print(e['toc_word'],hex(e['lba']),e['id'],[(hex(a),hex(b)) for a,b in e['subs']])
