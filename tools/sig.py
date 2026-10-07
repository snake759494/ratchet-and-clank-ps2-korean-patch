import re,sys,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import elf
def masked(va,n):
    pat=b''
    for i in range(n):
        w=int.from_bytes(elf.rd(va+4*i,4),'little');op=w>>26
        if op in (2,3): pat+=b'.{3}'+re.escape(bytes([w>>24 & 0xfc]))[:0]+b'.'
        elif op==15 or op in (8,9,12,13,14) or 32<=op<=63: pat+=b'..'+re.escape(w.to_bytes(4,'little')[2:])
        else: pat+=re.escape(w.to_bytes(4,'little'))
    return re.compile(pat,re.S)
