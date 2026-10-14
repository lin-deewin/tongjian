"""Verify uploaded-only overlays, exact source binding, coverage and search parity."""
import copy, hashlib, json, re, sys, zipfile
from pathlib import Path
from lxml import html
from translations.overlay import apply
from validate_volume import check
ROOT=Path(__file__).resolve().parents[1]
def compact(s):return re.sub(r'\s+','',s)
def main():
    catalog=json.loads((ROOT/'dist/catalog.json').read_text())
    coverage=json.loads((ROOT/'dist/coverage.json').read_text())
    report=json.loads((ROOT/'dist/translation-supplement-report.json').read_text())
    uploaded=zipfile.ZipFile(ROOT/'sources/baiyang.epub');file_text={}
    missing=recovered=baseline=0;corpus=hashlib.sha256();boundaries=0
    for meta in catalog['volumes']:
        v=meta['volume'];raw=(ROOT/f'dist/volume{v}.json').read_bytes();corpus.update(raw)
        base=json.loads(raw);book=base
        baseline+=sum(len(y['translationMissing']) for y in base['years'])
        if meta.get('translationSupplement'):
            overlay=json.loads((ROOT/'dist'/meta['translationSupplement']).read_text())
            assert overlay['baseSHA256']==hashlib.sha256(raw).hexdigest()
            assert overlay['translationEpubSHA256']==hashlib.sha256((ROOT/'sources/baiyang.epub').read_bytes()).hexdigest()
            for entry in overlay['entries']:
                assert entry['provenance']=='uploaded-recovery' and v not in (113,200)
                assert entry['score']>=.90
                texts=[]
                for f in entry['files']:
                    if f not in file_text:file_text[f]=compact(html.fromstring(uploaded.read(f)).text_content())
                    texts.append(file_text[f])
                assert any(compact(entry['modern']) in t for t in texts),('Modern is not an exact uploaded excerpt',v,entry['year'],entry['huIndices'])
                recovered+=len(entry['huIndices']);boundaries+=bool(entry.get('boundaryReview'))
            book=apply(base,overlay)
            # Mutation guards must reject stale or duplicate source bindings.
            bad=copy.deepcopy(overlay);bad['entries'][0]['sourceTexts'][0]+='变'
            try:apply(base,bad)
            except AssertionError:pass
            else:raise AssertionError('Stale overlay accepted')
            assert book['intro']==base['intro']
            for before,after in zip(base['years'],book['years']):
                for key in ('paragraphs','heading','after','titles','anchors'):assert before.get(key)==after.get(key),(v,key)
        check(book)
        n=sum(len(y['translationMissing']) for y in book['years']);missing+=n
        assert meta['translationMissing']==n
        search=json.loads((ROOT/f'dist/search{v}.json').read_text())
        for row,y in zip(search,book['years']):
            assert row['pairCount']==sum(not p['difference'] for p in y['bilingual'])
            for p in y['bilingual']:assert p['modern'] in row['text']
    assert baseline==2012 and missing+recovered==baseline
    assert report['recovered']==coverage['uploadedRecoveredOriginal']==recovered
    assert report['remainingMissing']==coverage['unmatchedOriginal']==missing
    assert report['aiSupplemented']==coverage['aiSupplementedOriginal']==0
    assert coverage['matchedOriginal']==30584-missing
    page=(ROOT/'dist/index.html').read_text();assert f'仍有{missing}段' in page and f'{coverage["matchedOriginal"]:,}<small>段' in page
    # All canonical volume bytes remain identical to the existing famine audit.
    assert corpus.hexdigest()=='1c89cac43aa6cfe534eabc5516cee74794fa69f5cf8c9005e63a0a31ea740356'
    print(json.dumps(dict(recovered=recovered,remainingMissing=missing,uploadedOnly=True,sourceBinding='exact',boundarySplits=boundaries,canonicalCorpus='unchanged'),ensure_ascii=False))
if __name__=='__main__':main()
