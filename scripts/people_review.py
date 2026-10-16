"""Bind an explicit semantic review to identity, event fields, sources and nearby text.

This module never infers or grants a review from a matching name/title/hash.
Only records written after reading the cited text can provide review decisions.
"""
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def event_key(person, event):
    locations = [(s['volume'], s['year'], s['indices']) for s in event['sources']]
    return person['id'] + ':' + digest([event['title'], locations])[:20]


def review_basis(person, event, books):
    fields = ('title', 'summary', 'kind', 'category', 'year', 'timeLabel', 'dateNote')
    context = []
    for source in event['sources']:
        year = next(y for y in books[source['volume']]['years'] if y['year'] == source['year'])
        nearby = sorted({j for i in source['indices'] for j in (i - 1, i, i + 1)
                         if 0 <= j < len(year['paragraphs'])})
        context.append(dict(volume=source['volume'], year=source['year'], heading=year['heading'],
                            indices=source['indices'], sourceHash=source['sourceHash'],
                            nearby=[(i, year['paragraphs'][i]['runs']) for i in nearby]))
    return dict(identity={k: person[k] for k in ('id', 'name', 'aliases', 'identity')},
                event={k: event[k] for k in fields}, sources=context)


def make_record(person, event, books, note, reviewed_on, batch):
    if len(note) < 15:
        raise ValueError('A substantive source/date/identity review note is required')
    return dict(key=event_key(person, event), personId=person['id'], title=event['title'],
                status='verified-against-source', reviewedOn=reviewed_on, batch=batch,
                basisHash=digest(review_basis(person, event, books)), note=note,
                scope=['identity', 'title', 'event-date', 'category', 'source-location'],
                biographyCompletenessCertified=False, externalHistoricalAccuracyCertified=False)


def validate_record(person, event, books, record):
    if record['status'] != 'verified-against-source' or record['key'] != event_key(person, event):
        raise ValueError('Mismatched semantic review identity/key')
    if record['basisHash'] != digest(review_basis(person, event, books)):
        raise ValueError(f'Stale semantic review: {person["name"]}: {event["title"]}')
    if len(record.get('note', '')) < 15:
        raise ValueError('Missing semantic review explanation')
    return record


def candidate_basis(person, candidate, books):
    year = next(y for y in books[candidate['volume']]['years'] if y['year'] == candidate['year'])
    i = candidate['index']
    nearby = [(j, year['paragraphs'][j]['runs']) for j in (i - 1, i, i + 1)
              if 0 <= j < len(year['paragraphs'])]
    return dict(identity={k: person[k] for k in ('id', 'name', 'aliases', 'identity')},
                volume=candidate['volume'], year=candidate['year'], index=i,
                heading=year['heading'], nearby=nearby)


def validate_candidate(person, candidate, books, events):
    statuses = {'included', 'excluded-false-name-match', 'excluded-other-identity', 'unresolved-identity'}
    if candidate['status'] not in statuses or len(candidate.get('reason', '')) < 15:
        raise ValueError('Invalid candidate decision')
    if candidate.get('basisHash') != digest(candidate_basis(person, candidate, books)):
        raise ValueError(f'Stale candidate decision: {person["name"]}')
    matches = [e for e in events if any(s['volume'] == candidate['volume'] and s['year'] == candidate['year']
               and candidate['index'] in s['indices'] for s in e['sources'])]
    linked_keys = {event_key(person, e) for e in matches}
    if candidate['status'] == 'included':
        if not candidate['eventKeys'] or not set(candidate['eventKeys']) <= linked_keys:
            raise ValueError('Included candidate no longer has its reviewed event')
    elif linked_keys:
        raise ValueError('Excluded/unresolved candidate now has a conflicting event association')
    return candidate
