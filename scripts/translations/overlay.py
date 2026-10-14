"""Apply audited translation overlays while preserving canonical source bytes."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def fingerprint(group):return hashlib.sha256((group['sourceOriginal']+'\0'+group['modern']).encode()).hexdigest()
def apply(book,overlay):
    result=copy.deepcopy(book);years={y['year']:y for y in result['years']}
    seen={(y['year'],i) for y in result['years'] for p in y['bilingual'] for i in p['huIndices']}
    for entry in overlay['entries']:
        y=years[entry['year']];indices=entry['huIndices']
        assert len(indices)==len(entry['sourceTexts']) and indices
        for i,text in zip(indices,entry['sourceTexts']):
            assert y['paragraphs'][i]['plain']==text,('Changed translation source',book['volume'],y['year'],i)
            assert (y['year'],i) not in seen,('Duplicate translation mapping',book['volume'],y['year'],i)
            seen.add((y['year'],i))
        if entry['action']=='extend':
            source=years[entry['sourceYear']]
            pair=next(g for g in source['bilingual'] if fingerprint(g)==entry['groupFingerprint'])
            assert source is y and not pair['difference']
            pair['huIndices']=sorted(pair['huIndices']+indices);pair['recoverySource']=entry['provenance'];continue
        if entry.get('removeDifference'):
            source=years[entry['sourceYear']]
            old=next(g for g in source['bilingual'] if fingerprint(g)==entry['groupFingerprint'])
            assert old['difference'];source['bilingual'].remove(old)
        pair=dict(huIndices=indices,sourceOriginal=entry['sourceOriginal'],modern=entry['modern'],score=entry['score'],kind=entry['kind'],difference=False,reviewStatus=entry['reviewStatus'],provenance=entry['provenance'],translationFiles=entry.get('files',[]))
        if entry.get('sourceYear')!=y['year'] and entry['provenance']=='uploaded-recovery':
            pair['sourceYear']=entry['sourceYear'];pair['dateWarning']='上传译本此段记年与胡注本当前位置不同，按原文定位保留对照，年份待校对。'
        y['bilingual'].append(pair)
    for y in result['years']:
        covered={i for p in y['bilingual'] for i in p['huIndices']}
        y['translationMissing']=sorted(set(range(len(y['paragraphs'])))-covered)
        y['translationSupplemented']=sum(len(p['huIndices']) for p in y['bilingual'] if p.get('provenance')=='ai-supplement')
        y['translationRecovered']=sum(len(p['huIndices']) for p in y['bilingual'] if p.get('provenance')=='uploaded-recovery')
        if book['volume']==28:y['translationWarning']='上传本卷混有白话和仅古文部分；已恢复可核对的白话，古文不当作白话。'
    return result

def load_overlay(volume):
    path=ROOT/f'dist/translation-supplements/volume{volume}.json'
    if not path.exists():return None
    overlay=json.loads(path.read_text())
    raw=(ROOT/f'dist/volume{volume}.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==overlay['baseSHA256'],('Canonical volume changed',volume)
    return overlay
