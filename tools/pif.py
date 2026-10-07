import struct
from PIL import Image
def unsw(i): return (i&0xe7)|((i&8)<<1)|((i&16)>>1)
def parse(d,o):
    assert d[o:o+4]==b'2FIP'
    w,h,psm=struct.unpack_from('<III',d,o+8)
    return w,h,psm
def render(d,o,bg=(0,0,0)):
    w,h,psm=parse(d,o)
    pal=d[o+0x20:o+0x420];pix=d[o+0x420:o+0x420+w*h]
    cols=[tuple(pal[4*unsw(i):4*unsw(i)+4]) for i in range(256)]
    im=Image.new('RGBA',(w,h));im.putdata([(c[0],c[1],c[2],min(255,c[3]*2)) for c in (cols[p] for p in pix)])
    b=Image.new('RGBA',(w,h),bg+(255,));b.alpha_composite(im);return b
def render_alpha(d,o):
    w,h,psm=parse(d,o)
    pal=d[o+0x20:o+0x420];pix=d[o+0x420:o+0x420+w*h]
    al=[min(255,pal[4*unsw(i)+3]*2) for i in range(256)]
    im=Image.new('L',(w,h));im.putdata([al[p] for p in pix]);return im
