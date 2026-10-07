import capstone,struct
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import paths
D=open(os.path.join(paths.WORK,'SCPS_150.37'),'rb').read()
BASE=0x100080-0x1000  # vaddr = file offset + BASE  (seg off 0x1000 -> 0x100080)
def rd(va,n): return D[va-BASE:va-BASE+n]
md=capstone.Cs(capstone.CS_ARCH_MIPS,capstone.CS_MODE_MIPS64+capstone.CS_MODE_LITTLE_ENDIAN)
def dis(va,n):
    return list(md.disasm(rd(va,n*4),va))
md.skipdata=True
def alltext():
    return dis(0x112380,0x1d1f8//4)+dis(0x1e9400,0x55e10//4)
