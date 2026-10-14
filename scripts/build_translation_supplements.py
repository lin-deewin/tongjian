"""Publish recoveries and individually authored AI drafts as separate overlays."""
import hashlib,json,re
from collections import defaultdict
from pathlib import Path
from translations.overlay import apply
ROOT=Path(__file__).resolve().parents[1]

def build():
    recovery=json.loads((ROOT/'artifacts/translations/recovery-proposals.json').read_text())
    entries=defaultdict(list)
    for p in recovery['proposals']:
        e=dict(action='extend' if p['method']=='extend-existing' else 'add',year=p['year'],sourceYear=p['sourceYear'],huIndices=p['huIndices'],sourceTexts=p['sourceTexts'],sourceOriginal=p['original'],modern=p['modern'],score=p['score'],kind='commentary' if re.match(r'^(臣光曰|太史公曰|荀悦论曰)',re.sub(r'^\[\d+\]','',p['original'])) else 'record',reviewStatus='recovered-source',provenance='uploaded-recovery',files=p['files'],recoveryMethod=p['method'])
        if 'groupFingerprint' in p:e.update(groupFingerprint=p['groupFingerprint'],removeDifference=p['method']=='existing-difference')
        if 'sourceGroupModern' in p:e['sourceGroupModern']=p['sourceGroupModern'];e['boundaryReview']=p['boundaryReview']
        entries[p['volume']].append(e)
    # User scope: recover uploaded white text only; never publish AI drafts.
    superseded=[]
    catalog=json.loads((ROOT/'dist/catalog.json').read_text())
    total_missing=uploaded=generated=recovered=0;health=[];counts=[]
    out=ROOT/'dist/translation-supplements';out.mkdir(exist_ok=True)
    epub_hash=hashlib.sha256((ROOT/'sources/baiyang.epub').read_bytes()).hexdigest()
    for v,meta in enumerate(catalog['volumes'],1):
        raw=(ROOT/f'dist/volume{v}.json').read_bytes();base=json.loads(raw)
        if entries[v]:
            overlay=dict(schemaVersion=1,volume=v,baseSHA256=hashlib.sha256(raw).hexdigest(),translationEpubSHA256=epub_hash,entries=entries[v])
            book=apply(base,overlay)
            (out/f'volume{v}.json').write_text(json.dumps(overlay,ensure_ascii=False,separators=(',',':'))+'\n')
            meta['translationSupplement']=f'translation-supplements/volume{v}.json'
        else:
            book=base;meta.pop('translationSupplement',None)
            (out/f'volume{v}.json').unlink(missing_ok=True)
        base_missing=sum(len(y['translationMissing']) for y in base['years'])
        missing=sum(len(y['translationMissing']) for y in book['years'])
        r=sum(len(e['huIndices']) for e in entries[v] if e['provenance']=='uploaded-recovery');g=sum(len(e['huIndices']) for e in entries[v] if e['provenance']=='ai-supplement')
        recovered+=r;generated+=g;total_missing+=missing;uploaded+=meta['bodyParagraphs']-base_missing+r
        meta.update(translationMissing=missing,translationRecovered=r,translationGenerated=g)
        if missing:health.append(dict(volume=v,title=meta['title'],missing=missing,body=meta['bodyParagraphs'],reason='上传译本缺卷、缺页、古文无白话或边界待校对；未擅配'))
        if r or g:counts.append(dict(volume=v,recovered=r,generated=g,remaining=missing))
        # Search indexing uses the same overlaid groups as reading. Preserve
        # event titles and anchors, including all independent title reviews.
        path=ROOT/f'dist/search{v}.json';search=json.loads(path.read_text())
        for row,y in zip(search,book['years']):
            row['pairCount']=sum(not p['difference'] for p in y['bilingual'])
            row['text']=' '.join([''.join(r['text'] for r in p['runs']) for p in y['paragraphs']]+[p['modern'] for p in y['bilingual']]+y.get('translationBlocks',[]))
        path.write_text(json.dumps(search,ensure_ascii=False,separators=(',',':')))
    summary=dict(volumes=294,uniqueYears=len(catalog['yearVolumes']),sourceBody=sum(m['bodyParagraphs'] for m in catalog['volumes']),matchedOriginal=uploaded+generated,uploadedMatchedOriginal=uploaded,uploadedRecoveredOriginal=recovered,aiSupplementedOriginal=generated,unmatchedOriginal=total_missing,ancientOnlyVolumes=[113,200],mixedTranslationVolumes=[28],volumesWithMissing=health)
    assert summary['matchedOriginal']+total_missing==summary['sourceBody']
    (ROOT/'dist/catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,separators=(',',':')))
    (ROOT/'dist/coverage.json').write_text(json.dumps(summary,ensure_ascii=False,separators=(',',':')))
    report=dict(schemaVersion=1,baselineMissing=2012,recovered=recovered,aiSupplemented=generated,remainingMissing=total_missing,supersededDrafts=superseded,sourceVolumesChanged=False,volumes=counts,limitations=['仅恢复上传译本中的白话，不发布生成译文。','恢复译文来自上传文件；原上传译文字句原样保留。','胡注本部分年份边界有异常，保留原定位并显示译本记年差异。','原文、事件锚点及历史河流原文绑定不改变。'])
    (ROOT/'dist/translation-supplement-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    index=ROOT/'dist/index.html';page=index.read_text()
    page=re.sub(r'<strong>[\d,]+<small>段</small></strong><p>有上传白话对应</p>',f'<strong>{uploaded:,}<small>段</small></strong><p>有上传白话对应</p>',page)
    about=f'原文取自上传的胡三省注本，白话仅来自上传译本。本次恢复{recovered}段此前漏配的上传白话，目前仍有{total_missing}段正文缺译或待核对，阅读时保留原文并明确提示。未使用生成译文。事件标题用于定位；追叙和史家评论另作标识。'
    page=re.sub(r'原文取自上传的胡三省注本，白话[^<]*',about,page)
    index.write_text(page)
    print(json.dumps({k:v for k,v in report.items() if k not in ('volumes','limitations')},ensure_ascii=False))
    return report
if __name__=='__main__':build()
