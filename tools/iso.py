"""ISO 직접 수정 도구 (원본 복사본에 덮어쓰기)"""
import struct

SEC = 2048


class Iso:
    def __init__(self, path):
        self.f = open(path, 'r+b')
        self.f.seek(0, 2)
        self.size = self.f.tell()

    def read(self, lba, n):
        self.f.seek(lba * SEC)
        return self.f.read(n)

    def write(self, lba, data):
        self.f.seek(lba * SEC)
        self.f.write(data)
        pad = (-len(data)) % SEC
        if pad:
            self.f.write(b'\0' * pad)
        end = (lba * SEC + len(data) + pad)
        if end > self.size:
            self.size = end

    def pread(self, off, n):
        self.f.seek(off)
        return self.f.read(n)

    def pwrite(self, off, data):
        self.f.seek(off)
        self.f.write(data)

    def append(self, data):
        lba = (self.size + SEC - 1) // SEC
        self.write(lba, data)
        return lba

    def root_records(self):
        pvd = self.read(16, SEC)
        assert pvd[1:6] == b'CD001'
        root = pvd[156:156 + 34]
        lba = struct.unpack_from('<I', root, 2)[0]
        size = struct.unpack_from('<I', root, 10)[0]
        out = []
        data = self.read(lba, size)
        pos = 0
        while pos < len(data):
            ln = data[pos]
            if ln == 0:
                pos = (pos // SEC + 1) * SEC
                continue
            name = data[pos + 33:pos + 33 + data[pos + 32]]
            out.append((name, lba * SEC + pos, struct.unpack_from('<I', data, pos + 2)[0],
                        struct.unpack_from('<I', data, pos + 10)[0]))
            pos += ln
        return out

    def set_file(self, name, lba, size):
        for n, off, _, _ in self.root_records():
            if n == name:
                self.f.seek(off + 2)
                self.f.write(struct.pack('<I', lba) + struct.pack('>I', lba) +
                             struct.pack('<I', size) + struct.pack('>I', size))
                return
        raise KeyError(name)

    def fix_volume_size(self):
        n = (self.size + SEC - 1) // SEC
        self.f.seek(16 * SEC + 80)
        self.f.write(struct.pack('<I', n) + struct.pack('>I', n))

    def close(self):
        self.f.close()
