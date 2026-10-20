"""Rebind famine review only when every original source field is unchanged.

The reference commit must reproduce the review's existing full-volume SHA256.
This handles translation/markup-only JSON edits without accepting new evidence.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(__file__).with_name('famine-review.json')


def source(book):
    fields = ('year', 'calendarYear', 'king', 'eraName', 'reign', 'reignLabel',
              'dynasty', 'heading', 'headingRuns', 'after', 'paragraphs', 'recorded')
    return dict(volume=book['volume'], intro=book['intro'], sourceFile=book.get('sourceFile'), source=book.get('source'),
                years=[{key: y.get(key) for key in fields} for y in book['years']])


def rebind(reference):
    review = json.loads(REVIEW.read_text())
    previous, current, originals = (hashlib.sha256() for _ in range(3))
    revision = subprocess.check_output(['git', 'rev-parse', reference], cwd=ROOT, text=True).strip()
    for v in range(1, 295):
        name = f'dist/volume{v}.json'
        old = subprocess.check_output(['git', 'show', f'{revision}:{name}'], cwd=ROOT)
        new = (ROOT / name).read_bytes()
        previous.update(old); current.update(new)
        old_source, new_source = source(json.loads(old)), source(json.loads(new))
        assert old_source == new_source, f'Original source changed in volume {v}; re-review required'
        originals.update(json.dumps(new_source, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())
    if review['corpusSHA256'] == current.hexdigest():
        print('Famine review already bound to current volume bytes.'); return
    assert review['corpusSHA256'] == previous.hexdigest(), 'Reference does not reproduce reviewed corpus'
    review['sourceRebinding'] = dict(referenceCommit=revision, previousCorpusSHA256=previous.hexdigest(),
                                    currentCorpusSHA256=current.hexdigest(), originalSourceSHA256=originals.hexdigest(),
                                    verifiedVolumes=294, method='Exact equality of original runs, paragraph order, source IDs, year fields and headings; translation-only changes; decisions unchanged')
    review['corpusSHA256'] = current.hexdigest()
    REVIEW.write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(review['sourceRebinding'], ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', required=True)
    rebind(parser.parse_args().reference)
