"""ELF/오버레이 패치: 한글 2바이트 출력 + 확장 폰트 세그먼트

레벨마다 0x165580 이후(.data, lvl 코드)가 디스크의 오버레이로 바뀌므로,
오버레이(변형)마다 전용 훅 코드를 0xA0000 세그먼트에 생성한다.
"""
import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asm import Asm
from build_font import TRAIL, LEADS, SINGLES, single_cell, HROWS

SEG = 0xA0000
STATE = 0xA4000          # 리드 바이트 보관
FONT = 0xA5000           # 팔레트(0x400) + 픽셀(256x1024)
ELF_BASE = 0x100080 - 0x1000   # vaddr = fileoff + ELF_BASE (기존 세그먼트)

# ELF 기준 주소
E_TEX, E_Q, E_S, E_BRA, E_BRS = 0x1F4DC8, 0x1F5D60, 0x1F6118, 0x1F6D40, 0x1F73C8
GLYPH_TBL = 0x1DFCB0
BR_OFF = 0x14            # brA/brS 함수 시작 → sltiu 0x28 위치
JAL_Q_IN_BRA = 0x1F6D94 - E_BRA   # drawA 안의 jal q (VA 역산용)


def hi_lo(v):
    lo = v & 0xffff
    hi = ((v >> 16) + (1 if lo & 0x8000 else 0)) & 0xffff
    return hi, (lo - 0x10000 if lo & 0x8000 else lo)


def u32(b, o=0):
    return struct.unpack_from('<I', b, o)[0]


def variant_from(read, tex, q, s):
    """read(addr,n)->bytes (addr: tex/q/s 와 같은 좌표계). tex,q,s = VA"""
    w = {}
    for k, va in (('tex', tex), ('q', q), ('s', s)):
        w[k] = (u32(read(va, 4)), u32(read(va + 4, 4)))
    lui = u32(read(tex, 4)); add = u32(read(tex + 0x10, 4))
    assert lui >> 16 == 0x3c02 and add >> 16 == 0x2442, (hex(lui), hex(add))
    lo = add & 0xffff
    slot = ((lui & 0xffff) << 16) + (lo - 0x10000 if lo & 0x8000 else lo)
    # 텍스처 기준 포인터: tex+0xD8 'lui a3,HI' / tex+0xDC 'lw a3,LO(a3)'
    l2 = u32(read(tex + 0xd8, 4)); lw = u32(read(tex + 0xdc, 4))
    assert l2 >> 16 == 0x3c07 and lw >> 16 == 0x8ce7, (hex(l2), hex(lw))
    lo = lw & 0xffff
    basep = ((l2 & 0xffff) << 16) + (lo - 0x10000 if lo & 0x8000 else lo)
    return dict(tex=tex, q=q, s=s, w=w, slot1=slot + 0x10, basep=basep)


def gen_code(variants):
    a = Asm(SEG)
    sh, sl = hi_lo(STATE)
    cnt = [0]

    def calc_cell(u_reg, v_reg):
        """t8 = 리드, u_reg = 트레일 → u_reg=u, v_reg=v (t9/at 사용)"""
        cnt[0] += 1
        k = cnt[0]
        a.addiu('t9', u_reg, -0xA8)
        a.sltiu('at', u_reg, 0xBF)
        a.bne('at', 'zero', 'c%d' % k); a.nop()
        a.addiu('t9', 't9', -2)
        a.label('c%d' % k)
        a.addiu('t8', 't8', -0xF0)
        a.sll('at', 't8', 6); a.addu('t9', 't9', 'at')
        a.sll('at', 't8', 2); a.addu('t9', 't9', 'at')
        a.sll('at', 't8', 1); a.addu('t9', 't9', 'at')
        a.andi(u_reg, 't9', 15); a.sll(u_reg, u_reg, 4)
        a.srl('t8', 't9', 4)
        a.sltiu('at', 't8', HROWS)
        a.beq('at', 'zero', 'e%d' % k)
        a.sll(v_reg, 't8', 4)
        a.beq('zero', 'zero', 'd%d' % k)
        a.addiu(v_reg, v_reg, 256)
        a.label('e%d' % k)
        a.addiu(v_reg, v_reg, 16 - HROWS * 16)
        a.label('d%d' % k)

    for n, v in enumerate(variants):
        p = 'v%d_' % n
        t0, t1 = v['w']['tex']
        # ---------- 텍스처 슬롯 1(폰트) ----------
        a.label(p + 'tex')
        a.addiu('t9', 'zero', 1)
        a.bne('a0', 't9', p + 'tex_orig'); a.nop()
        a.addiu('sp', 'sp', -16)
        a.sd('ra', 0, 'sp')
        a.sd('s0', 8, 'sp')
        bh, bl = hi_lo(v['basep'])
        a.lui('t9', bh)
        a.lw('s0', bl, 't9')
        a.li('t8', FONT)
        a.sw('t8', bl, 't9')
        a.li('t8', v['slot1'])
        a.addiu('t9', 'zero', 0x40); a.sh('t9', 8, 't8')   # 픽셀 = FONT+0x400
        a.sh('zero', 0xa, 't8')                            # 팔레트 = FONT
        a.addiu('t9', 'zero', 8); a.sh('t9', 0xc, 't8')
        a.addiu('t9', 'zero', 10); a.sh('t9', 0xe, 't8')
        a.w(t0)
        a.jal(v['tex'] + 8)
        a.w(t1)
        a.lui('t9', bh)
        a.sw('s0', bl, 't9')
        a.ld('ra', 0, 'sp')
        a.ld('s0', 8, 'sp')
        a.jr('ra')
        a.addiu('sp', 'sp', 16)
        a.label(p + 'tex_orig')
        a.w(t0)
        a.j(v['tex'] + 8)
        a.w(t1)

        # ---------- 글리프 사각형 (정수 좌표) ----------
        q0, q1 = v['w']['q']
        a.label(p + 'q')
        a.addiu('t9', 'zero', 0x10)
        a.bne('t3', 't9', p + 'q_orig'); a.nop()
        a.sltiu('t9', 't0', 0xA8)
        a.bne('t9', 'zero', p + 'q_orig'); a.nop()
        a.andi('t8', 't1', 0xff)
        a.addiu('t9', 'zero', 0xff)
        a.beq('t8', 't9', p + 'q_lead'); a.nop()
        a.addiu('t9', 'zero', 0xfe)
        a.bne('t8', 't9', p + 'q_orig'); a.nop()
        a.lui('t9', sh); a.lbu('t8', sl, 't9')
        calc_cell('t0', 't1')
        a.addiu('a0', 'a0', -7)
        a.label(p + 'q_orig')
        a.w(q0)
        a.j(v['q'] + 8)
        a.w(q1)
        a.label(p + 'q_lead')
        a.lui('t9', sh)
        a.jr('ra')
        a.sb('t0', sl, 't9')

        # ---------- 글리프 사각형 (실수 좌표, 확대) ----------
        s0, s1 = v['w']['s']
        a.label(p + 's')
        a.addiu('t9', 'zero', 0x10)
        a.bne('a3', 't9', p + 's_orig'); a.nop()
        a.sltiu('t9', 'a0', 0xA8)
        a.bne('t9', 'zero', p + 's_orig'); a.nop()
        a.andi('t8', 'a1', 0xff)
        a.addiu('t9', 'zero', 0xff)
        a.beq('t8', 't9', p + 's_lead'); a.nop()
        a.addiu('t9', 'zero', 0xfe)
        a.bne('t8', 't9', p + 's_orig'); a.nop()
        a.lui('t9', sh); a.lbu('t8', sl, 't9')
        calc_cell('a0', 'a1')
        a.lui('at', 0x3ee0)          # 0.4375 = 7/16
        a.mtc1('at', 'f18')
        a.mul_s('f19', 'f14', 'f18')
        a.sub_s('f12', 'f12', 'f19')
        a.label(p + 's_orig')
        a.w(s0)
        a.j(v['s'] + 8)
        a.w(s1)
        a.label(p + 's_lead')
        a.lui('t9', sh)
        a.jr('ra')
        a.sb('a0', sl, 't9')
    return a


def jword(t):
    return struct.pack('<II', (2 << 26) | ((t >> 2) & 0x3ffffff), 0)


def table_patches():
    """[(테이블 내 오프셋, bytes)]"""
    out = []
    for b in TRAIL:
        out.append((4 * b, bytes([b, 0xFE, 0, 7])))
    for b in LEADS:
        out.append((4 * b, bytes([b, 0xFF, 0, 7])))
    for i, b in enumerate(SINGLES):
        u, v = single_cell(i)
        out.append((4 * b, bytes([u, v, 0, 14])))
    return out


def elf_variant(d):
    def rd(va, n):
        o = va - ELF_BASE
        return bytes(d[o:o + n])
    return variant_from(rd, E_TEX, E_Q, E_S)


def overlay_variant(iso_read, f):
    """f: overlays.find_all 의 found dict (ISO 오프셋). VA 는 drawA 안의 jal q 로 역산"""
    tex, q, s, bra = f['tex'][0], f['q'][0], f['s'][0], f['brA'][0]
    jal = u32(iso_read(bra + JAL_Q_IN_BRA, 4))
    assert jal >> 26 == 3
    va_q = (jal & 0x3ffffff) << 2
    delta = va_q - q            # VA = ISO + delta
    v = variant_from(lambda va, n: iso_read(va - delta, n), tex + delta, q + delta, s + delta)
    v['delta'] = delta
    return v


def patch_overlay(iso_read, iso_write, tbl_off, f, labels, n):
    """디스크 오버레이 사본 패치"""
    p = 'v%d_' % n
    for k in ('tex', 'q', 's'):
        iso_write(f[k][0], jword(labels[p + k]))
    for off, b in table_patches():
        iso_write(tbl_off + off, b)
    for k in ('brA', 'brS'):
        a = f[k][0] + BR_OFF
        assert iso_read(a, 4) == bytes.fromhex('2800422c'), k
        iso_write(a, bytes.fromhex('0000422c'))


def patch(elf_in, elf_out, font_blob, overlay_variants):
    """overlay_variants: [variant] (오버레이 순서). 반환: labels"""
    d = bytearray(open(elf_in, 'rb').read())

    def put(va, b):
        off = va - ELF_BASE
        d[off:off + len(b)] = b

    def get(va, n):
        off = va - ELF_BASE
        return bytes(d[off:off + n])

    ev = elf_variant(d)
    variants = [ev] + list(overlay_variants)
    code = gen_code(variants)
    blob = code.bytes()
    assert SEG + len(blob) <= STATE, hex(len(blob))
    L = code.labels
    put(E_TEX, jword(L['v0_tex']))
    put(E_Q, jword(L['v0_q']))
    put(E_S, jword(L['v0_s']))
    for off, b in table_patches():
        put(GLYPH_TBL + off, b)
    for va in (E_BRA + BR_OFF, E_BRS + BR_OFF):
        assert get(va, 4) == bytes.fromhex('2800422c')
        put(va, bytes.fromhex('0000422c'))

    for off, b in subtitle_patch_blob(bytes(d)):
        d[off:off + len(b)] = b
    seg = bytearray(FONT - SEG + len(font_blob))
    seg[0:len(blob)] = blob
    seg[FONT - SEG:] = font_blob
    while len(d) % 0x1000:
        d.append(0)
    seg_off = len(d)
    d += seg
    phoff = struct.unpack_from('<I', d, 0x1c)[0]
    phnum = struct.unpack_from('<H', d, 0x2c)[0]
    assert phnum == 1 and phoff == 0x34
    assert d[0x54:0x74] == b'\0' * 32
    struct.pack_into('<8I', d, 0x54, 1, seg_off, SEG, SEG, len(seg), len(seg), 7, 0x10)
    struct.pack_into('<H', d, 0x2c, 2)
    open(elf_out, 'wb').write(d)
    return L


# ---------- 자막 기본 켜기: 판정 반전(값 0 = 표시) + 메뉴 끔/켬 라벨 교환 ----------
import re as _re
SUB_BR = _re.compile(b'\x40\xef[\x40-\x5f]\x90..\x40\x50', _re.S)   # lbu v0,-0x10c0 ; beql v0,zero
SUB_LAB = bytes.fromhex('244f000040ef15005b4f00005c4f0000')
SUB_LAB_NEW = bytes.fromhex('244f000040ef15005c4f00005b4f0000')


def subtitle_patch_blob(buf, base=0):
    """buf 안의 판정 분기·라벨을 찾아 [(오프셋, bytes)] 반환"""
    br = [x.start() for x in SUB_BR.finditer(buf)]
    lab = [x.start() for x in _re.finditer(_re.escape(SUB_LAB), buf)]
    assert len(br) == 1 and len(lab) == 1, (br, lab)
    o = br[0] + 4
    w = bytearray(buf[o:o + 4]); assert w[3] == 0x50; w[3] = 0x54   # beql -> bnel
    return [(base + o, bytes(w)), (base + lab[0], SUB_LAB_NEW)]
