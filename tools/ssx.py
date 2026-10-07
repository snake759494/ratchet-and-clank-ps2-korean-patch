import zipfile,zstandard,struct,sys
def extract(p,names,outdir):
    f=open(p,'rb').read();z=zipfile.ZipFile(p)
    for i in z.infolist():
        if i.filename in names:
            off=i.header_offset;nl,el=struct.unpack_from('<HH',f,off+26)
            data=f[off+30+nl+el:off+30+nl+el+i.compress_size]
            out=data if i.compress_type==0 else zstandard.ZstdDecompressor().decompressobj().decompress(data)
            open(outdir+'/'+i.filename,'wb').write(out)
if __name__=='__main__': extract(sys.argv[1],sys.argv[2:],'ss')
