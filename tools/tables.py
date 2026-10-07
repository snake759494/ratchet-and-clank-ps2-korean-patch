import struct
def find_tables(d):
    runs=[];cur=None
    for a in range(0,len(d)-16,4):
        o,i,m,z=struct.unpack_from('<IIiI',d,a)
        if m==-1 and z==0 and o<0x200000 and 0<i<0x100000:
            if cur and a==cur[1]: cur[1]=a+16; cur[2]+=1
            elif cur and a<cur[1]: continue
            else:
                if cur and cur[2]>5: runs.append(cur)
                cur=[a,a+16,1]
    if cur and cur[2]>5: runs.append(cur)
    return runs
