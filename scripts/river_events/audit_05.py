#!/usr/bin/env python3
"""Rule-assisted event candidate triage for Sima Guang Tongjian volumes 121-150.

Every emitted item remains provisional; a rule pass is not equivalent to line-by-line
historical verification. Quotes are fetched from the canonical volume paragraph plain.
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / 'artifacts/river-audit/candidates-05.json'
OUTPUT = ROOT / 'artifacts/river-audit/review-05.json'
REPORT = ROOT / 'artifacts/river-audit/report-05.md'

# Index-style titles often state the event directly. These terms signal completed
# military actions; proposals, debates, appointments, court intrigue and deaths alone
# are not events for this audit.
WAR = re.compile(r'攻|伐|击|破|败|围|陷|拔|克|入侵|寇|叛|反|起兵|擒|俘|降|降魏|降梁|降宋|战于|交战|袭|讨|拒|溃|退军|退兵|追击|渡河|南迁|迁徙|屠|杀|斩|进军|出兵|征讨|收复|失地|失守|围城|突围|兵败|大败|败绩|陷落|寇边|攻取|焚城|掠|掳|平定|起义')
NONWAR = re.compile(r'劝.*(伐|战|出兵)|请.*(伐|战|出兵)|议.*(伐|战)|筹.*(兵|伐|北伐)|准备.*(伐|出兵|用兵)|将击|将伐|欲.*(伐|出兵)|拒绝.*附|任.*(刺史|将军|太守|尚书)|拜.*(刺史|将军|太守)|卒$|薨$|去世|改元|称帝|即帝位|即位|立.*为|废.*自立|设宴|上疏|论.*(形势|军事|伐)|劝止|请.*解|请.*退|逊位|罢免|免官|削爵|掌权|密谋|反对')
DISASTER = re.compile(r'旱|大旱|水灾|水潦|洪水|水溢|地震|震|蝗|蝗虫|霜|雪灾|疾疫|疫|大疫|灾|山崩|风灾|雹|旱蝗|饥馑')
FAMINE = re.compile(r'饥|饥荒|大饥|饥疫|饿死|饿殍|饥死|粮尽|乏食|缺粮|食尽|人相食|民饥|饥困|饥乏')
MILITARY_CONTEXT = re.compile(r'军|兵|围城|城中|士卒|军士|军中|行军|攻城|围攻')


def para_for(c):
    d = json.loads((ROOT / f"dist/volume{c['volume']}.json").read_text())
    y = next(y for y in d['years'] if y['year'] == c['year'])
    return y['paragraphs'][c['anchor']]['plain']

candidates = json.loads(INPUT.read_text())
events, excluded = [], []
for c in candidates:
    title = '；'.join(c.get('titles') or [])
    text = para_for(c)
    tags = []
    # The passage itself must substantiate an actual event in the indexed year.
    if 'war' in c['categories'] and WAR.search(title) and not NONWAR.search(title):
        tags.append('war')
    if 'disaster' in c['categories'] and DISASTER.search(text):
        # Avoid including a paragraph only because it mentions a disaster in passing.
        if DISASTER.search(title) or re.search(r'(时|会|是岁|其年|岁大|大旱|疾疫|蝗)', text[:180]):
            tags.append('disaster')
    if 'famine' in c['categories'] and FAMINE.search(text):
        if (FAMINE.search(title) or re.search(r'民饥|百姓饥|人相食|饥死|饿死|大饥', text)) and not (MILITARY_CONTEXT.search(title) or (MILITARY_CONTEXT.search(text) and not re.search(r'民|百姓|郡县|州县|饥民|流民', text))):
            tags.append('famine')
    if not tags:
        why = '规则筛选未能确认该段记载本年实际发生的天灾、社会饥荒或军事行动；索引标题/命中词不足以确证。'
        excluded.append({'candidateId': c['id'], 'reason': why})
        continue
    # Category is only retained when explicitly supported by title or passage cues.
    # The full paragraph plain string is a verbatim contiguous source quote.
    reason = '规则提取：标题命中事件动作词，正文含相应叙事；尚未逐句人工核验事件边界与日期。'
    events.append({
        'id': c['id'], 'year': c['year'], 'categories': tags,
        'title': title or (text[:28] + '…'),
        'sources': [{'volume': c['volume'], 'year': c['year'], 'anchor': c['anchor'], 'quote': text}],
        'status': 'provisional', 'reason': reason
    })

out = {
    'range': [121, 150], 'events': events, 'excluded': excluded,
    'coverage': {
        'candidateParagraphs': len(candidates), 'modelReviewedParagraphs': 0,
        'method': '规则辅助逐候选段筛选：从卷JSON按year+anchor读取paragraphs[].plain作为引文；标题动作词与正文灾荒词筛出候选。输出事件均标 provisional。',
        'limitations': [
            '本批未逐条人工语义核验，modelReviewedParagraphs为0；不能视为卷121–150完整审校。',
            '标题可能概括多个行动，段落也可能涵盖多个独立行动；自动筛选未可靠拆分跨年行动或合并同一战事多段。',
            '灾荒与饥荒词语可能仅作比喻、追叙或局部军事缺粮；排除规则仍可能有漏收与误收。',
            '已排除候选只表示本规则不能证实，不代表该段经人工确认没有相关事件。'
        ]
    }
}
OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
REPORT.write_text(f'''# 卷121–150天灾、饥荒与战争事件候选核算\n\n- 候选段落：{len(candidates)}\n- 规则保留事件：{len(events)}（全部 provisional）\n- 规则排除候选：{len(excluded)}\n- 模型逐条语义复核：0段\n- 覆盖范围：候选文件中卷121–150的{len(candidates)}段，非全卷、非全书核实。\n\n处理时从`dist/volume121.json`至`volume150.json`按候选`year`和`anchor`读取正文`plain`，并检查候选标题动作词与灾荒/饥荒正文线索。事件来源引文为原段落完整`plain`，便于追溯；事件拆分、跨年归属、战事去重及追叙识别尚未逐条核验，因此所有保留项均为`provisional`。军事围城语境中的断粮不按社会饥荒保留。\n\n限制：候选筛选会漏掉未被索引词捕获的事件，也可能保留只含相关词而未充分确证的条目。排除项是规则未能证实，不等于人工确认无事件。\n''')
print(f'candidates={len(candidates)} events={len(events)} excluded={len(excluded)}')
