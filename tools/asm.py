"""최소 MIPS(R5900) 어셈블러 - 패치 코드용"""
import struct

R = {n: i for i, n in enumerate(
    "zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra".split())}


def r(x):
    return R[x.lstrip('$')]


def f(x):
    return int(x.lstrip('$f'))


class Asm:
    def __init__(self, base):
        self.base = base
        self.words = []
        self.labels = {}
        self.fix = []

    @property
    def pc(self):
        return self.base + 4 * len(self.words)

    def label(self, name):
        self.labels[name] = self.pc

    def w(self, v):
        self.words.append(v & 0xffffffff)

    # --- 형식 ---
    def _i(self, op, rs, rt, imm):
        self.w((op << 26) | (rs << 21) | (rt << 16) | (imm & 0xffff))

    def _r(self, rs, rt, rd, sa, fn, op=0):
        self.w((op << 26) | (rs << 21) | (rt << 16) | (rd << 11) | (sa << 6) | fn)

    # --- 명령 ---
    def nop(self): self.w(0)
    def addiu(self, rt, rs, imm): self._i(9, r(rs), r(rt), imm)
    def andi(self, rt, rs, imm): self._i(12, r(rs), r(rt), imm)
    def ori(self, rt, rs, imm): self._i(13, r(rs), r(rt), imm)
    def sltiu(self, rt, rs, imm): self._i(11, r(rs), r(rt), imm)
    def lui(self, rt, imm): self._i(15, 0, r(rt), imm)
    def lw(self, rt, off, rs): self._i(35, r(rs), r(rt), off)
    def sw(self, rt, off, rs): self._i(43, r(rs), r(rt), off)
    def lbu(self, rt, off, rs): self._i(36, r(rs), r(rt), off)
    def sb(self, rt, off, rs): self._i(40, r(rs), r(rt), off)
    def sh(self, rt, off, rs): self._i(41, r(rs), r(rt), off)
    def ld(self, rt, off, rs): self._i(55, r(rs), r(rt), off)
    def sd(self, rt, off, rs): self._i(63, r(rs), r(rt), off)
    def lwc1(self, ft, off, rs): self._i(49, r(rs), f(ft), off)
    def addu(self, rd, rs, rt): self._r(r(rs), r(rt), r(rd), 0, 0x21)
    def subu(self, rd, rs, rt): self._r(r(rs), r(rt), r(rd), 0, 0x23)
    def or_(self, rd, rs, rt): self._r(r(rs), r(rt), r(rd), 0, 0x25)
    def move(self, rd, rs): self._r(r(rs), 0, r(rd), 0, 0x2d)   # daddu
    def sll(self, rd, rt, sa): self._r(0, r(rt), r(rd), sa, 0)
    def srl(self, rd, rt, sa): self._r(0, r(rt), r(rd), sa, 2)
    def jr(self, rs): self._r(r(rs), 0, 0, 0, 8)
    def mtc1(self, rt, fs): self.w((17 << 26) | (4 << 21) | (r(rt) << 16) | (f(fs) << 11))
    def mul_s(self, fd, fs, ft): self.w((17 << 26) | (16 << 21) | (f(ft) << 16) | (f(fs) << 11) | (f(fd) << 6) | 2)
    def sub_s(self, fd, fs, ft): self.w((17 << 26) | (16 << 21) | (f(ft) << 16) | (f(fs) << 11) | (f(fd) << 6) | 1)

    def j(self, target): self._jt(2, target)
    def jal(self, target): self._jt(3, target)

    def _jt(self, op, target):
        if isinstance(target, str):
            self.fix.append((len(self.words), 'j', target, op)); self.w(op << 26)
        else:
            self.w((op << 26) | ((target >> 2) & 0x3ffffff))

    def beq(self, rs, rt, lab): self._b(4, rs, rt, lab)
    def bne(self, rs, rt, lab): self._b(5, rs, rt, lab)

    def _b(self, op, rs, rt, lab):
        self.fix.append((len(self.words), 'b', lab, op)); self._i(op, r(rs), r(rt), 0)

    def li(self, rt, v):
        v &= 0xffffffff
        if v < 0x8000:
            self.addiu(rt, 'zero', v)
        else:
            self.lui(rt, v >> 16)
            if v & 0xffff: self.ori(rt, rt, v & 0xffff)

    def la_hi_lo(self, v):
        lo = v & 0xffff
        hi = (v >> 16) + (1 if lo & 0x8000 else 0)
        return hi & 0xffff, lo if lo < 0x8000 else lo - 0x10000

    def bytes(self):
        ws = list(self.words)
        for idx, kind, lab, op in self.fix:
            t = self.labels[lab]
            if kind == 'j':
                ws[idx] = (op << 26) | ((t >> 2) & 0x3ffffff)
            else:
                off = (t - (self.base + 4 * idx + 4)) >> 2
                ws[idx] = (ws[idx] & 0xffff0000) | (off & 0xffff)
        return struct.pack('<%dI' % len(ws), *ws)
