with open('C:/work/hap_output/oh_debug_chain.cer', 'rb') as f:
    data = f.read()
lines = data.split(b'\n')
for i, line in enumerate(lines):
    stripped = line.rstrip(b'\r')
    if b' ' in stripped or b'\t' in stripped:
        print('Line %d: %r' % (i, stripped[:80]))
print('Total lines: %d' % len(lines))
print('File size: %d' % len(data))
