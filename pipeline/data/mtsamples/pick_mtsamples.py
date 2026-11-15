"""T43: pick 12 MTSamples notes by a fixed rule (written before anyone read them).
Usage: python pick_mtsamples.py <path to mtsamples.csv> <output folder>
Source CSV: Kaggle tboyle10/medicaltranscriptions (CC0), copy at github.com/salgadev/medical-nlp data/mtsamples.csv
"""
import csv, random, re, sys, pathlib
csv.field_size_limit(10**9)
SPECIALTIES = {"Discharge Summary", "Consult - History and Phy.", "General Medicine", "Emergency Room Reports"}
SEED = 20261115

def readable(t):
    # The Kaggle scrape turned line breaks into commas; put them back without changing words.
    t = re.sub(r'(?<=[.:]),\s*', '\n', t)
    t = re.sub(r':\s*:', ':', t)
    t = re.sub(r':\s*,\s*', ': ', t)
    t = re.sub(r'[ \t]+', ' ', t)
    return '\n'.join(l.strip() for l in t.split('\n'))

rows = list(csv.DictReader(open(sys.argv[1], encoding='utf-8')))
out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
seen, pool = set(), []
for r in rows:
    t = (r['transcription'] or '').strip()
    if not t or t in seen:
        continue
    seen.add(t)
    up = t.upper()
    if (r['medical_specialty'].strip() in SPECIALTIES and 'ALLERG' in up
            and 'MEDICATION' in up and 1500 <= len(t) <= 4000):
        pool.append(r)
random.Random(SEED).shuffle(pool)
with open(out / 'picked.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['note_id', 'kaggle_row', 'specialty', 'sample_name'])
    for i, r in enumerate(pool[:12], 1):
        nid = f"M{i:03d}"
        (out / f"{nid}.txt").write_text(readable(r['transcription'].strip()) + '\n')
        w.writerow([nid, r[''], r['medical_specialty'].strip(), r['sample_name'].strip()])
print(f"pool {len(pool)}, wrote 12 notes to {out}")
