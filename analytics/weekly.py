#!/usr/bin/env python3
"""The weekly reading report for marrydavid.com, written as Markdown.

    python3 analytics/weekly.py                 # last 7 days against the 7 before, to stdout
    python3 analytics/weekly.py --out DIR       # also write DIR/marrydavid-YYYY-MM-DD.md, open it, and notify (macOS)
    python3 analytics/weekly.py --days 14

Runs on this Mac from launchd every Monday at 8:00 (see analytics/install-weekly.sh); auth is the
same gcloud impersonation ga.py uses, so if the report says the token failed, run `gcloud auth login`.
"""
import datetime, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ga

PID = ga.property_id()
OWN_SECTIONS = ga.PATH_TITLES + ['Transmission']


def rows(dims, mets, days, filt=None, offset=0, order=None, limit=50):
    start, end = f'{days + offset}daysAgo', f'{offset + 1}daysAgo' if offset else 'today'
    body = {'dateRanges': [{'startDate': start, 'endDate': end}], 'dimensions': [{'name': d} for d in dims],
            'metrics': [{'name': m} for m in mets], 'limit': limit}
    if filt: body['dimensionFilter'] = filt
    if order: body['orderBys'] = [{'metric': {'metricName': order}, 'desc': True}]
    r = ga.call(f'{ga.DATA}/properties/{PID}:runReport', body)
    return [[c['value'] for c in x.get('dimensionValues', [])] + [c['value'] for c in x['metricValues']] for x in r.get('rows', [])]


def md_table(head, body):
    if not body: return '_nothing recorded_\n'
    out = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    out += ['| ' + ' | '.join(str(c) for c in r) + ' |' for r in body]
    return '\n'.join(out) + '\n'


def num(x):
    try: return float(x)
    except (TypeError, ValueError): return 0.0


def mins(sec): return f'{num(sec) / 60:.0f} min'


def soft(fn, default):
    try: return fn()
    except ga.Unregistered as e:
        return default if default != 'note' else f'_waiting on GA4: register the custom {e.args[1]} `{e.args[0]}`_\n'


def report(days):
    L = []
    today = datetime.date.today()
    L.append(f'# marrydavid.com, the week to {today.isoformat()}\n')
    L.append(f'Last {days} days, with the {days} before in brackets. Your own visits are filtered out from the day the filter went active.\n')

    # totals
    now = rows([], ['activeUsers', 'sessions', 'engagedSessions', 'screenPageViews', 'userEngagementDuration'], days)
    was = rows([], ['activeUsers', 'sessions', 'engagedSessions', 'screenPageViews', 'userEngagementDuration'], days, offset=days)
    n = now[0] if now else ['0'] * 5; w = was[0] if was else ['0'] * 5
    L.append('## Readers\n')
    L.append(md_table(['users', 'sessions', 'engaged sessions', 'section views', 'hours read'],
                      [[f'{n[0]} ({w[0]})', f'{n[1]} ({w[1]})', f'{n[2]} ({w[2]})', f'{n[3]} ({w[3]})', f'{num(n[4]) / 3600:.1f} ({num(w[4]) / 3600:.1f})']]))

    # where from, real readers only
    L.append('## Where they read from\n')
    c = rows(['country', 'region'], ['activeUsers', 'engagedSessions', 'userEngagementDuration'], days, order='userEngagementDuration', limit=15)
    L.append(md_table(['country', 'region', 'users', 'engaged sessions', 'time'], [[a, b, u, e, mins(t)] for a, b, u, e, t in c if num(t) > 0]))
    bots = sum(1 for r in rows(['country'], ['sessions', 'userEngagementDuration'], days, limit=200) if num(r[2]) == 0)
    L.append(f'{bots} countries sent sessions with zero engagement, which is crawler traffic.\n')

    # what they read
    L.append('## What they read\n')
    s = rows(['pageTitle'], ['activeUsers', 'screenPageViews', 'userEngagementDuration'], days, ga.eq('eventName', 'page_view'), order='activeUsers', limit=15)
    L.append(md_table(['section', 'users', 'views', 'time'], [[t, u, v, mins(x)] for t, u, v, x in s]))

    # the reading order
    L.append('## The reading order\n')
    by = {r[0]: (int(r[1]), int(r[2])) for r in rows(['pageTitle'], ['screenPageViews', 'activeUsers'], days, ga.eq('eventName', 'page_view'), limit=200)}
    secs = soft(lambda: {r[0]: num(r[1]) for r in rows(['customEvent:section'], ['customEvent:seconds'], days, ga.eq('eventName', 'section_leave'), limit=200)}, {})
    base = by.get(ga.PATH_TITLES[0], (0, 0))[1] or 1
    L.append(md_table(['section', 'users', 'share of Start Here', 'min per user'],
                      [[t, by.get(t, (0, 0))[1], f'{100 * by.get(t, (0, 0))[1] / base:.0f}%', f'{secs.get(t, 0) / 60 / max(1, by.get(t, (0, 0))[1]):.1f}'] for t in OWN_SECTIONS]))
    try:
        steps = [{'name': t, 'filterExpression': {'funnelFieldFilter': {'fieldName': 'pageTitle', 'stringFilter': {'matchType': 'EXACT', 'value': t}}}} for t in ga.PATH_TITLES]
        body = {'dateRanges': [{'startDate': f'{days}daysAgo', 'endDate': 'today'}], 'funnel': {'isOpenFunnel': True, 'steps': steps}}
        f = ga.call(f'https://analyticsdata.googleapis.com/v1alpha/properties/{PID}:runFunnelReport', body).get('funnelTable', {})
        fr = [[c['value'] for c in x.get('dimensionValues', [])] + [c['value'] for c in x.get('metricValues', [])] for x in f.get('rows', [])]
        if fr:
            first, last = num(fr[0][1]), num(fr[-1][1])
            L.append(f'In order, Start Here to Age Range: {int(first)} readers began, {int(last)} finished, {100 * last / max(1, first):.0f}%.\n')
            L.append(md_table(['step', 'users', 'went on'], [[r[0], r[1], f'{100 * num(r[2]):.0f}%'] for r in fr]))
    except SystemExit:
        pass
    L.append('### How they got to each section\n')
    L.append(soft(lambda: md_table(['via', 'views'], rows(['customEvent:via'], ['screenPageViews'], days, ga.eq('eventName', 'page_view'), order='screenPageViews')), 'note'))

    # depth
    L.append('## How far they read\n')
    def depth_table():
        views = {r[0]: int(r[1]) for r in rows(['pageTitle'], ['screenPageViews'], days, ga.eq('eventName', 'page_view'), limit=200)}
        full = {r[0]: int(r[2]) for r in rows(['customEvent:section', 'customEvent:depth'], ['eventCount'], days, ga.eq('eventName', 'section_scroll'), limit=400) if r[1] == '100'}
        left = {r[0]: (num(r[1]), int(r[2])) for r in rows(['customEvent:section'], ['customEvent:seconds', 'eventCount'], days, ga.eq('eventName', 'section_leave'), limit=200)}
        body = []
        for sec, v in sorted(views.items(), key=lambda kv: -kv[1])[:15]:
            body.append([sec, v, f'{100 * full.get(sec, 0) / v:.0f}%' if v else '', f'{left.get(sec, (0, 0))[0] / max(1, v):.0f} s'])
        return md_table(['section', 'views', 'read to the end', 'avg on screen'], body)
    L.append(soft(depth_table, 'note'))

    # cards and audits
    L.append('## Cards opened\n')
    L.append(soft(lambda: md_table(['card', 'section', 'opens', 'users'], rows(['customEvent:card', 'customEvent:section'], ['eventCount', 'activeUsers'], days, ga.eq('eventName', 'card_open'), order='eventCount', limit=15)), 'note'))
    L.append('### Audits copied\n')
    L.append(soft(lambda: md_table(['audit', 'copies'], rows(['customEvent:audit'], ['eventCount'], days, ga.eq('eventName', 'audit_copy'), order='eventCount')), 'note'))

    # actions
    L.append('## Actions\n')
    acts = {'book_call': 'booking clicks', 'call_request': 'call requests sent', 'email_click': 'email clicks', 'form_start': 'forms started',
            'seal_click': 'matchmaker seal clicks', 'seal2_click': 'third-date seal clicks', 'referral_click': 'referral emails', 'nudge_shown': 'two-minute reminders shown', 'nudge_click': 'reminder clicks'}
    ev = {r[0]: (r[1], r[2]) for r in rows(['eventName'], ['eventCount', 'activeUsers'], days, limit=100)}
    ev_was = {r[0]: r[1] for r in rows(['eventName'], ['eventCount'], days, offset=days, limit=100)}
    L.append(md_table(['action', 'count', 'users'], [[label, f'{ev.get(k, ("0", "0"))[0]} ({ev_was.get(k, "0")})', ev.get(k, ('0', '0'))[1]] for k, label in acts.items()]))
    L.append(f'\n_Generated {datetime.datetime.now():%Y-%m-%d %H:%M} by analytics/weekly.py. Reports: `python3 analytics/ga.py --help`._\n')
    return '\n'.join(L)


def main():
    args = sys.argv[1:]
    days = int(args[args.index('--days') + 1]) if '--days' in args else 7
    out = args[args.index('--out') + 1] if '--out' in args else None
    try:
        text = report(days)
    except SystemExit as e:
        text = f'# marrydavid.com weekly report failed\n\n```\n{e}\n```\n\nIf the token failed, run `gcloud auth login` as the property owner and rerun `python3 analytics/weekly.py --out DIR`.\n'
    if not out:
        print(text); return
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, f'marrydavid-{datetime.date.today().isoformat()}.md')
    open(path, 'w', encoding='utf-8').write(text)
    print(path)
    if sys.platform == 'darwin':
        subprocess.run(['open', path])
        ok = 'failed' not in text.split('\n', 1)[0]
        msg = 'The weekly reading report is open.' if ok else 'The weekly report failed; run gcloud auth login.'
        subprocess.run(['osascript', '-e', f'display notification "{msg}" with title "marrydavid.com analytics"'])


if __name__ == '__main__':
    main()
