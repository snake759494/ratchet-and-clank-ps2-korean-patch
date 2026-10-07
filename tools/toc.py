import struct
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import paths
ISO=paths.ISO
def toc():
    f=open(ISO,'rb');f.seek(1500*2048);return struct.unpack('<%dI'%(0x1800//4),f.read(0x1800))
def read(lba,sz):
    f=open(ISO,'rb');f.seek(lba*2048);return f.read(sz*2048)
