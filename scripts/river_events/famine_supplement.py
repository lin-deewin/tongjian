"""Apply source-bound famine decisions without rewriting earlier audit batches."""
from collections import Counter
import json
from pathlib import Path
try:
    from .prepare_famine import scan
except ImportError:
    from prepare_famine import scan
ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(__file__).with_name('famine-review.json')


def apply(rows, corpus_hash, review_document=None):
    if review_document is None and not REVIEW.exists():
        return None, set()
    review = review_document if review_document is not None else json.loads(REVIEW.read_text())
    scanned = scan()
    assert review['corpusSHA256'] == corpus_hash == scanned['corpusSHA256'], 'Famine review corpus changed; re-review before rebuilding'
    paragraphs = {p['id']: p for p in scanned['paragraphs']}
    decisions = {d['candidateId']: d for d in review['decisions']}
    assert len(decisions) == len(review['decisions']), 'Duplicate famine decision'
    assert set(decisions) == set(paragraphs), 'Famine scan changed; update decisions'
    full = set(review['coverage']['fullTextReviewedParagraphIds'])
    assert set(review['coverage']['excerptScreenedParagraphIds']) == set(paragraphs)
    original = {e['id']: e for row in rows.values() for e in row['events']}
    base = [e for e in original.values() if 'famine' in e['categories']]
    assert len(base) == review['baselineFamineCount']
    assert set(review['coverage']['baselineCitationCheckedEventIds']) == {e['id'] for e in base}
    before = json.loads(json.dumps(base))
    changes = []

    def check_source(s, event_year):
        cid = f'v{s["volume"]}-y{s["year"]}-p{s["anchor"]}'
        assert s['candidateId'] == cid and cid in full
        # Some original source paragraphs do not match a clue; read from books.
        book = json.loads((ROOT / f'dist/volume{s["volume"]}.json').read_text())
        year = next(y for y in book['years'] if y['year'] == s['year'])
        paragraph = year['paragraphs'][s['anchor']]
        assert not paragraph.get('structural')
        assert s['quote'].strip() and s['quote'] in paragraph['plain'], ('Famine quote mismatch', cid)
        if event_year != s['year']:
            previous = 1 if s['year'] == -1 else s['year'] + 1
            assert event_year == previous and any(w in s['quote'] for w in ('去岁', '去歲', '去年', '去冬')), ('Famine date mismatch', cid)

    for e in review['additions']:
        assert e['id'] not in original and e['year'] in rows and e['year'] != 0
        assert e['categories'] == ['famine'] and e['status'] == 'modelReviewed'
        for s in e['sources']:
            check_source(s, e['year'])
        item = dict(e, volume=e['sources'][0]['volume'], anchor=e['sources'][0]['anchor'])
        rows[e['year']]['events'].append(item)
        original[item['id']] = item
        changes.append(dict(action='add', event=item, reason=e['reason']))
    category_removals = 0
    category_merges = 0
    for change in review['amendments']:
        event = original[change['eventId']]
        action = change['action']
        snapshot = json.loads(json.dumps(event))
        if action == 'support':
            for s in change['sources']:
                check_source(s, event['year'])
                if s not in event['sources']:
                    event['sources'].append(s)
        elif action == 'rename':
            assert change['title'].strip()
            event['title'] = change['title']
        elif action == 'mergeCategory':
            target = original[change['targetId']]
            assert target['year'] == event['year'] and 'famine' in target['categories']
            for s in event['sources']:
                # Source evidence checked against the original corpus by the
                # base builder; full paragraph read is required for merging.
                assert s['candidateId'] in full
                if s not in target['sources']:
                    target['sources'].append(s)
            assert 'famine' in event['categories']
            event['categories'].remove('famine')
            category_merges += 1
        elif action == 'removeCategory':
            assert 'famine' in event['categories']
            assert all(s['candidateId'] in full for s in event['sources'])
            event['categories'].remove('famine')
            category_removals += 1
        else:
            raise AssertionError(('Unknown famine amendment', action))
        event['famineReview'] = dict(action=action, reason=change['reason'])
        changes.append(dict(**change, before=snapshot))
    for row in rows.values():
        row['events'] = [e for e in row['events'] if e['categories']]
    after = [e for row in rows.values() for e in row['events'] if 'famine' in e['categories']]
    assert len(after) == len(before) + len(review['additions']) - category_merges - category_removals
    resolved = {cid for cid,d in decisions.items() if d['disposition'] in {'added','mergedSource'}}
    detail = dict(schemaVersion=1, corpusSHA256=corpus_hash,
                  baselineFamineCount=len(before), famineCount=len(after),
                  famineYearCount=len({e['year'] for e in after}),
                  addedEvents=len(review['additions']), mergedFamineEntries=category_merges,
                  removedFamineClassifications=category_removals,
                  expandedClueParagraphs=len(paragraphs),
                  excerptScreenedParagraphs=len(paragraphs),
                  fullTextReviewedParagraphs=len(full),
                  baselineCitationCheckedEvents=len(base),
                  decisionCounts=dict(Counter(d['disposition'] for d in decisions.values())),
                  reviewer=review['reviewer'], unit=review['unit'],
                  policy=review['policy'], limitations=review['limitations'],
                  changes=changes, decisions=review['decisions'], coverage=review['coverage'])
    if review.get('sourceRebinding'):
        detail['sourceRebinding'] = review['sourceRebinding']
    (ROOT/'dist/famine-audit-report.json').write_text(json.dumps(detail, ensure_ascii=False, separators=(',', ':'))+'\n')
    write_report(detail)
    return {k:v for k,v in detail.items() if k not in {'changes','decisions','coverage'}}, resolved


def write_report(report):
    def year(y):
        return f'前{y}年' if y > 0 else f'公元{-y}年'
    lines = ['# 饥荒专项补漏报告', '',
             f'正式饥荒记录：{report["baselineFamineCount"]} → **{report["famineCount"]}条**；涉及 **{report["famineYearCount"]}个年份**。', '',
             f'- 补收 {report["addedEvents"]} 条；同年同地合并 {report["mergedFamineEntries"]} 条重复分类；{report["removedFamineClassifications"]} 条饥荒分类转待核。',
             '- 保留战争、天灾等其他分类。原文、白话与阅读路由未修改。',
             f'- 扩展检索命中 {report["expandedClueParagraphs"]} 段；全部查看线索摘录；全文核读 {report["fullTextReviewedParagraphs"]} 个不同原段（含已有事件复核与疑难项）。',
             f'- 原有 {report["baselineCitationCheckedEvents"]} 条饥荒核对出处引文，不声称这190条全部重新全文审读。',
             '- 本轮由当前主代理审读，没有独立第二审；不是全书通读或史学终审。', '',
             '## 计数口径', '', *['- '+p for p in report['policy']], '',
             '“条数”按年记灾情，不是跨年连续饥荒的独立过程数。关键词命中不是事件；screenedOnly只完成摘录初筛，不算完整排除。', '',
             '## 补收事件', '', '| 年份 | 事件 | 来源 |', '|---|---|---|']
    for c in report['changes']:
        if c['action'] != 'add':
            continue
        e=c['event'];refs='、'.join(f'卷{s["volume"]}／{year(s["year"])}／段{s["anchor"]}' for s in e['sources'])
        lines.append(f'| {year(e["year"])} | {e["title"]} | {refs} |')
    lines += ['', '## 合并、撤回分类与标题修正', '']
    for c in report['changes']:
        if c['action'] in {'mergeCategory','removeCategory','rename'}:
            lines.append(f'- {year(c["before"]["year"])}「{c["before"]["title"]}」：{c["reason"]}')
    lines += ['', '## 待核与初筛', '',
              f'- 已全文核读但尚待判断：{report["decisionCounts"].get("pending",0)} 个候选段。另有撤回分类的5条旧事件，见完整审计记录。',
              f'- 仅线索摘录初筛：{report["decisionCounts"].get("screenedOnly",0)} 个候选段，保留复查队列。',
              '- 时间不明追叙、居民与守军范围不清、仅赈济或物价异常的记载不强行加入正式点。',
              '- 典型时间待核：晋阳围城人马相食（卷1卷首追叙）、汲黯赈河南（卷17旧事）、河渭饥疫（卷249考异明言并置本年）、950年收葬旧饿殍。', '',
              '## 重建与证据', '',
              '- 扫描：`python scripts/river_events/prepare_famine.py`。',
              '- 汇总：`python scripts/build_river.py`；自动加载 `scripts/river_events/famine-review.json`。',
              '- 完整决策、准确引文、来源与修改前记录：`dist/famine-audit-report.json`。',
              '- 全文校验和绑定294卷；原文变化后构建拒绝套用旧决定。', '']
    (ROOT/'scripts/river_events/famine-report.md').write_text('\n'.join(lines))
