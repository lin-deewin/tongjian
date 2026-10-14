"""Propose source-bound recoveries; do not mutate canonical volume files."""
import json,re,hashlib,difflib,zipfile
from collections import defaultdict
from pathlib import Path
from lxml import html
ROOT=Path(__file__).resolve().parents[2]

def clean(text):
    text=re.sub(r'^\s*\[\d+\]\s*','',text)
    previous=None
    while text!=previous:
        previous=text;text=re.sub(r'〔[^〔〕]*〕','',text)
    return re.sub(r'[^\u4e00-\u9fff]','',text)
def grams(t):return {t[i:i+5] for i in range(max(0,len(t)-4))}
def fingerprint(group):return hashlib.sha256((group['sourceOriginal']+'\0'+group['modern']).encode()).hexdigest()
def load_books():return {v:json.loads((ROOT/f'dist/volume{v}.json').read_text()) for v in range(1,295)}
def source_pairs(books):
    pairs=[]
    for v,b in books.items():
        for y in b['years']:
            for i,g in enumerate(y['bilingual']):
                if not g['difference'] and not y['translationMissing']:continue
                pairs.append(dict(volume=v,sourceYear=y['year'],groupIndex=i,groupFingerprint=fingerprint(g),existingHuIndices=g['huIndices'],original=g['sourceOriginal'],modern=g['modern'],files=g.get('translationFiles',[]),method='existing-difference' if g['difference'] else 'extend-existing'))
    # Raw file tokens: inspect only chapters with missing originals; ancient-only
    # chapters 113 and 200 are never paired by parity.
    z=zipfile.ZipFile(ROOT/'sources/baiyang.epub')
    nums=dict(zip('零〇一二三四五六七八九', [0,0,1,2,3,4,5,6,7,8,9]))
    def cn(t):
        total=n=0
        for c in t:
            if c in nums:n=nums[c]
            elif c in '十百':total+=(n or 1)*{'十':10,'百':100}[c];n=0
        return total+n
    for f in z.namelist():
        if not re.search(r'chapter\d+\.htm$',f):continue
        root=html.fromstring(z.read(f));heads=root.xpath('//h3')
        if not heads:continue
        m=re.search(r'第+([零〇一二三四五六七八九十百]+)卷',heads[0].text_content())
        if not m:continue
        v=cn(m[1])
        if v not in books or v in (113,200) or not any(y['translationMissing'] for y in books[v]['years']):continue
        tokens=[];year=None
        for p in root.xpath('//p'):
            for t in p.text_content().split('*'):
                t=t.strip()
                h=re.match(r'^([^（）\n]{0,100}?[年载])\s*[（(]([^）)]{0,55})[）)]',t)
                if h:
                    d=re.search(r'[、，,﹑]\s*(?:公元|公年)?(前)?\s*([零〇○一二三四五六七八九\d]{1,4})',h[2])
                    if d:
                        n=int(d[2]) if d[2].isdigit() else int(''.join(str(nums.get(c,0)) for c in d[2]));year=n*(1 if d[1] else -1)
                        t=t[h.end():].strip()
                if not t or t.startswith(('【','该书籍由','--epub','---')):continue
                tokens.append((t,year))
        for i in range(len(tokens)-1):
            text,year=tokens[i];modern,myear=tokens[i+1]
            if year!=myear:continue
            pairs.append(dict(volume=v,sourceYear=year,original=text,modern=modern,files=[f],tokenIndex=i,method='raw-adjacent'))
    return pairs

def propose():
    books=load_books();pairs=source_pairs(books);byvol=defaultdict(list)
    for p in pairs:byvol[p['volume']].append(p)
    proposals=[];unresolved=[]
    rejected={'v164-y-552-p59','v171-y-574-p25'} # Adjacent token belongs to the next record, not this source.
    for v,b in books.items():
        if not any(y['translationMissing'] for y in b['years']):continue
        refs=[(y['year'],a,p,clean(p['plain'])) for y in b['years'] for a,p in enumerate(y['paragraphs'])]
        missing_keys={(y['year'],a) for y in b['years'] for a in y['translationMissing']}
        index=defaultdict(set); all_index=defaultdict(set)
        for i,(year,a,p,n) in enumerate(refs):
            for gram in grams(n):all_index[gram].add(i)
            if (year,a) not in missing_keys:continue
            for gram in grams(n):index[gram].add(i)
        candidates=[]
        seen=set()
        for pair in byvol[v]:
            # Mixed chapter 28 is admitted only by explicit reviewed pairs below.
            if v==28:continue
            original=clean(pair['original']);modern=clean(pair['modern'])
            key=(original,modern)
            if key in seen or len(original)<4:continue
            seen.add(key)
            votes=defaultdict(int)
            for gram in grams(original):
                for i in index.get(gram,[]):votes[i]+=1
            if len(original)<5:
                ranks=[i for i,r in enumerate(refs) if r[3]==original and r[0]==pair['sourceYear'] and (r[0],r[1]) in missing_keys]
            else:ranks=sorted(votes,key=votes.get,reverse=True)[:5]
            if not ranks:continue
            score=0;best=[]
            for anchor in ranks:
                for start in range(max(0,anchor-3),anchor+1):
                    for end in range(anchor+1,min(len(refs),start+14)+1):
                        if pair['method']!='extend-existing' and any((refs[j][0],refs[j][1]) not in missing_keys for j in range(start,end)):continue
                        s=''.join(r[3] for r in refs[start:end])
                        if not s:continue
                        ratio=min(len(s),len(original))/max(len(s),len(original))
                        if ratio<.80:continue
                        if s==original:similarity=1
                        elif (len(s)<30 or len(original)<30) and sum(r[3]==s for r in refs)!=1:continue
                        else:similarity=difflib.SequenceMatcher(None,original,s,autojunk=False).ratio()
                        if similarity>score:score=similarity;best=list(range(start,end))
            if score<.90 or not best:continue
            # Reject a supposed modern token if it actually reproduces ancient
            # text. Check both this record and other source paragraphs.
            if pair['method']=='raw-adjacent':
                if not modern or difflib.SequenceMatcher(None,original,modern,autojunk=False).ratio()>.82:continue
                exact_ancient=any(modern==r[3] or (len(modern)>35 and modern in r[3]) for r in refs)
                if exact_ancient:continue
                left=re.match(r'^\s*(?:\[(\d+)\]|(\d+))',pair['original'])
                right=re.match(r'^\s*(?:\[(\d+)\]|(\d+))',pair['modern'])
                if left and right and (left[1] or left[2]) != (right[1] or right[2]):continue
                if not re.search(r'的|了|他们|她们|我们|你们|自己|说|任命|皇帝|春季|夏季|秋季|冬季|发生|当时|于是|因为|所以|担任|率领|公元',pair['modern']):continue
                modern_votes=defaultdict(int)
                for gram in grams(modern):
                    for i in all_index.get(gram,[]):modern_votes[i]+=1
                is_ancient=False
                for anchor in sorted(modern_votes,key=modern_votes.get,reverse=True)[:3]:
                    for start in range(max(0,anchor-2),anchor+1):
                        for end in range(anchor+1,min(len(refs),start+10)+1):
                            text=''.join(r[3] for r in refs[start:end])
                            if not text or min(len(text),len(modern))/max(len(text),len(modern))<.8:continue
                            if difflib.SequenceMatcher(None,text,modern,autojunk=False).ratio()>=.93:is_ancient=True;break
                        if is_ancient:break
                    if is_ancient:break
                if is_ancient:continue
            targets=[i for i in best if refs[i][1] in next(y for y in b['years'] if y['year']==refs[i][0])['translationMissing']]
            if not targets:continue
            # Do not take only half a group already assigned elsewhere, nor
            # present the whole translation for an unrelated isolated fragment.
            if targets!=best:
                if pair['method']!='extend-existing':continue
                if any(refs[i][0]!=pair['sourceYear'] for i in best):continue
                already={refs[i][1] for i in best if i not in targets}
                if already!=set(pair['existingHuIndices']):continue
            if len({refs[i][0] for i in best})!=1:continue
            target_year=refs[best[0]][0]
            if pair['method']=='extend-existing':
                if target_year!=pair['sourceYear']:continue
                if {refs[i][1] for i in best if i not in targets} != set(pair['existingHuIndices']):continue
            if len(original)<25 and target_year!=pair['sourceYear'] and sum(r[3]==original for r in refs)!=1:continue
            candidates.append(dict(**pair,year=target_year,huIndices=[refs[i][1] for i in targets],score=round(score,4),sourceIds=[f'v{v}-y{refs[i][0]}-p{refs[i][1]}' for i in targets],sourceTexts=[refs[i][2]['plain'] for i in targets]))
        # Highest source similarity wins; never map a target twice.
        assigned=set()
        for p in sorted(candidates,key=lambda p:(-p['score'],p['method']!='existing-difference')):
            keys=set(p['sourceIds'])
            if keys&rejected:continue
            if keys&assigned:continue
            if p['method']=='existing-difference' and '\n' in p['modern'] and p['sourceIds']!=['v96-y-338-p39']:
                # Existing parser glued subsequent ancient/modern records into
                # this field. Only the first uploaded white paragraph belongs here.
                p['sourceGroupModern']=p['modern']
                p['modern']=p['modern'].split('\n',1)[0]
                p['boundaryReview']='已核对上传段落边界，移除粘连的后续古文与译文；保留原字句。'
            assigned |= keys;proposals.append(p)
        if v==28:
            # This upload is mixed: these thirteen adjacent pairs are modern
            # Chinese; the intervening paragraphs are ancient text only.
            z=zipfile.ZipFile(ROOT/'sources/baiyang.epub')
            ps=[p.text_content().strip() for p in html.fromstring(z.read('OPS/chapter29.htm')).xpath('//p')]
            for token in (2,4,6,8,10,12,14,72,74,76,78,80,82):
                original,modern=ps[token],ps[token+1]
                year=48 if token<16 else 42
                rank=sorted([(difflib.SequenceMatcher(None,clean(original),r[3],autojunk=False).ratio(),i) for i,r in enumerate(refs) if r[0]==year],reverse=True)
                assert rank and rank[0][0]>=.9, ('Manual uploaded pair changed',token)
                score,i=rank[0];ref=refs[i];id=f'v28-y{year}-p{ref[1]}'
                if id in assigned:continue
                assigned.add(id)
                proposals.append(dict(volume=28,sourceYear=year,year=year,huIndices=[ref[1]],score=round(score,4),sourceIds=[id],sourceTexts=[ref[2]['plain']],original=original,modern=modern,files=['OPS/chapter29.htm'],tokenIndex=token,method='manual-upload-pair',sourceRoleReview='逐项核对混合章节，白话与古文明确区分'))
        for year,a,p,n in refs:
            id=f'v{v}-y{year}-p{a}'
            if a in next(y for y in b['years'] if y['year']==year)['translationMissing'] and id not in assigned:
                unresolved.append(dict(id=id,volume=v,year=year,anchor=a,text=p['plain'],runs=p['runs'],structural=p.get('structural',False)))
    result=dict(proposals=proposals,unresolved=unresolved,matchedParagraphs=sum(len(p['huIndices']) for p in proposals),unresolvedParagraphs=len(unresolved))
    out=ROOT/'artifacts/translations';out.mkdir(exist_ok=True)
    (out/'recovery-proposals.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(recovered=result['matchedParagraphs'],unresolved=len(unresolved),groups=len(proposals),methods={m:sum(len(p['huIndices']) for p in proposals if p['method']==m) for m in ('existing-difference','raw-adjacent','extend-existing')})))
if __name__=='__main__':propose()
