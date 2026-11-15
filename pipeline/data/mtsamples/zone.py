"""T43 labelling zone: keep only sections whose heading is about medicines, allergies,
the story of the illness, past history, assessment, plan or ER course. Fixed heading rule,
same for every note. Prints kept text per note."""
import re, sys, pathlib, json
HEAD = re.compile(r"^([A-Z][A-Za-z /&'.\-]{1,60}?)\s*(:|,(?=\d))")
KEEP = re.compile(r"MEDICATION|ALLERG|PRESENT(ING)? (ILLNESS|COMPLAINT)|^HISTORY$|PAST MEDICAL HISTORY|ASSESSMENT|PLAN|IMPRESSION|COURSE", re.I)
def zone(text):
    out, keep = [], True  # text before any heading is kept
    for line in text.split('\n'):
        m = HEAD.match(line)
        if m:
            keep = bool(KEEP.search(m.group(1).strip()))
        if keep:
            out.append(line)
    return '\n'.join(out)
src = pathlib.Path(sys.argv[1]); dst = pathlib.Path(sys.argv[2]); dst.mkdir(exist_ok=True)
res = {}
for f in sorted(src.glob('M0*.txt')):
    z = zone(f.read_text().rstrip('\n'))
    (dst / f.name.replace('.txt', '_zone.txt')).write_text(z + '\n')
    full = len(f.read_text()); res[f.stem] = (full, len(z))
print(json.dumps(res))
