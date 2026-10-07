# 원본 1바이트 일본어 코드 -> 문자
ROWS={0x80:"ぁあぃいぅうぇえぉおかきくけこさ",0x90:"しすせそたちっつてとなにぬねのは",
0xa0:"ひふへほまみむめもゃやゅゆょよら",0xb0:"りるれろゎわをん、。・「」゛゜ー",
0xc0:"ァアィイゥウェエォオカキクケコサ",0xd0:"シスセソタチッツテトナニヌネノハ",
0xe0:"ヒフヘホマミムメモャヤュユョヨラ",0xf0:"リルレロヮワヲン"}
DEC={}
for b,s in ROWS.items():
    for i,c in enumerate(s): DEC[b+i]=c
import unicodedata
def decode(bs):
    out=[];i=0
    while i<len(bs):
        c=bs[i]
        if c==0xbd and out: out[-1]=unicodedata.normalize('NFC',out[-1]+'\u3099')
        elif c==0xbe and out: out[-1]=unicodedata.normalize('NFC',out[-1]+'\u309a')
        elif c in DEC: out.append(DEC[c])
        elif c==1: out.append('{01}')
        elif c<0x20 or c>=0x7f: out.append('{%02X}'%c)
        else: out.append(chr(c))
        i+=1
    return ''.join(out)
