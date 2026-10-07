import struct
def decompress(src):
    assert src[:3]==b'WAD'
    end=struct.unpack('<I',src[3:7])[0]
    ip=16; op=bytearray()
    def ext(base):
        nonlocal ip
        t=0
        while src[ip]==0: t+=255; ip+=1
        t+=base+src[ip]; ip+=1; return t
    def copy(dist,n):
        s=len(op)-dist
        assert s>=0,(ip,dist)
        if dist>=n: op.extend(op[s:s+n])
        else:
            for k in range(n): op.append(op[s+k])
    state=0
    if src[ip]>17:
        t=src[ip]-17; ip+=1; op.extend(src[ip:ip+t]); ip+=t; state=1 if t>=4 else 2
    while ip<end:
        t=src[ip]; ip+=1
        if t<16:
            if state==0:
                if t==0: t=ext(15)
                n=t+3; op.extend(src[ip:ip+n]); ip+=n; state=1; continue
            elif state==1:
                d=1+0x800+(t>>2)+(src[ip]<<2); ip+=1; copy(d,3)
            else:
                d=1+(t>>2)+(src[ip]<<2); ip+=1; copy(d,2)
        elif t>=64:
            d=1+((t>>2)&7)+(src[ip]<<3); ip+=1; copy(d,(t>>5)+1)
        elif t>=32:
            n=t&31
            if n==0: n=ext(31)
            v=src[ip]|src[ip+1]<<8; ip+=2; copy(1+(v>>2),n+2)
        else:
            hi=(t&8)<<11; n=t&7
            if n==0: n=ext(7)
            v=src[ip]|src[ip+1]<<8; ip+=2
            d=hi+(v>>2)
            if d==0:
                if t!=0x11:
                    ip=((ip-0x10+0x1fff)//0x2000)*0x2000+0x10
                    state=0; continue
            else: copy(d+0x4000,n+2)
        tr=src[ip-2]&3
        if tr==0: state=0
        else: op.extend(src[ip:ip+tr]); ip+=tr; state=2
    return bytes(op),ip,end
