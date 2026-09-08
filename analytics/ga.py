#!/usr/bin/env python3
"""Read-only GA4 reports for marrydavid.com, from the terminal.

Auth: no key file. gcloud (logged in as the property owner) impersonates the
read-only service account and borrows a short-lived token with the
analytics.readonly scope. The service account must be a Viewer on the GA4
property (Admin > Property access management).

    python3 analytics/ga.py properties              # find the property id
    python3 analytics/ga.py summary   [--days 7]    # users, sessions, top countries and sources
    python3 analytics/ga.py sections  [--days 7]    # page views per section (the hash router sends /#id)
    python3 analytics/ga.py country IR [--days 30]  # everything about one country's sessions
    python3 analytics/ga.py events    [--days 7]    # audit_copy, seal_click, and friends
    python3 analytics/ga.py layout    [--days 7]    # sidebar vs rail, and window widths (once the custom dimensions exist)
    python3 analytics/ga.py cards     [--days 7]    # which collapsed cards get opened, and audits opened vs copied
    python3 analytics/ga.py path      [--days 7]    # how far the Start Here reading order carries readers, and how long it takes
    python3 analytics/ga.py via       [--days 7]    # how readers reach sections: rail, sidebar, contents, path, crosslink, ...
    python3 analytics/ga.py order     [--days 7]    # what is usually read first, second, third
    python3 analytics/ga.py depth     [--days 7]    # per section: views, read halfway, read to the end, seconds on screen

Set GA_PROPERTY to skip discovery (a number like 4xxxxxxxxx).
"""
import json, os, re, subprocess, sys, urllib.request

SA = 'ga-reader@marrydavid-analytics.iam.gserviceaccount.com'
SCOPE = 'https://www.googleapis.com/auth/analytics.readonly'
DATA = 'https://analyticsdata.googleapis.com/v1beta'
ADMIN = 'https://analyticsadmin.googleapis.com/v1beta'
PATH_TITLES = ['Start Here', 'What You Get', 'Family', 'Dealbreakers', 'Age Range']  # the data-title of each section on the reading order


def token():
    r = subprocess.run(['gcloud', 'auth', 'print-access-token', '--impersonate-service-account=' + SA, '--scopes=' + SCOPE],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit('could not mint a token; run `gcloud auth login` as the property owner first\n' + r.stderr[-400:])
    return r.stdout.strip()


class Unregistered(Exception):
    """A custom dimension or metric the page sends but GA4 hasn't been told about yet."""


def call(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={'Authorization': 'Bearer ' + token(), 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        m = re.search(r'Field (customEvent:\w+) is not a valid (dimension|metric)', text)
        if e.code == 400 and m:
            raise Unregistered(m.group(1).split(':')[1], m.group(2))
        sys.exit(f'{e.code} from {url}\n{text[:600]}')


def soft(fn, default):
    """Run a report that needs a custom definition; explain and carry on if GA4 doesn't have it yet."""
    try:
        return fn()
    except Unregistered as e:
        print(f'  (waiting on GA4: register the event-scoped custom {e.args[1]} "{e.args[0]}" under Admin > Custom definitions; data shows from then on)')
        return default


def properties():
    out = []
    for acct in call(ADMIN + '/accountSummaries').get('accountSummaries', []):
        for p in acct.get('propertySummaries', []):
            out.append((p['property'].split('/')[-1], p.get('displayName', ''), acct.get('displayName', '')))
    return out


def property_id():
    if os.environ.get('GA_PROPERTY'):
        return os.environ['GA_PROPERTY']
    props = properties()
    if not props:
        sys.exit(f'the service account sees no properties yet: add {SA} as a Viewer on the GA4 property')
    for pid, name, _ in props:
        if 'marry' in name.lower() or 'date' in name.lower():
            return pid
    return props[0][0]


def report(pid, dims, mets, days, filt=None, limit=50, order=None):
    body = {'dateRanges': [{'startDate': f'{days}daysAgo', 'endDate': 'today'}],
            'dimensions': [{'name': d} for d in dims], 'metrics': [{'name': m} for m in mets], 'limit': limit}
    if filt:
        body['dimensionFilter'] = filt
    if order:
        body['orderBys'] = [{'metric': {'metricName': order}, 'desc': True}]
    r = call(f'{DATA}/properties/{pid}:runReport', body)
    rows = []
    for row in r.get('rows', []):
        rows.append([c['value'] for c in row.get('dimensionValues', [])] + [c['value'] for c in row['metricValues']])
    return rows


def table(head, rows):
    if not rows:
        print('  (no rows)'); return
    w = [max(len(str(x)) for x in col) for col in zip(head, *rows)]
    print('  ' + '  '.join(str(h).ljust(n) for h, n in zip(head, w)))
    for r in rows:
        print('  ' + '  '.join(str(x).ljust(n) for x, n in zip(r, w)))


def eq(dim, value):
    return {'filter': {'fieldName': dim, 'stringFilter': {'value': value}}}


def funnel(pid, days):
    """The reading order as a GA4 funnel (Data API v1alpha): Start Here, then the four named sections."""
    steps = [{'name': t, 'filterExpression': {'funnelFieldFilter': {'fieldName': 'pageTitle', 'stringFilter': {'matchType': 'EXACT', 'value': t}}}} for t in PATH_TITLES]
    body = {'dateRanges': [{'startDate': f'{days}daysAgo', 'endDate': 'today'}], 'funnel': {'isOpenFunnel': True, 'steps': steps}}
    req = urllib.request.Request(f'https://analyticsdata.googleapis.com/v1alpha/properties/{pid}:runFunnelReport', data=json.dumps(body).encode(),
                                 headers={'Authorization': 'Bearer ' + token(), 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as resp:
            r = json.load(resp)
    except urllib.error.HTTPError as e:
        print('  funnel unavailable:', e.read().decode()[:200]); return
    t = r.get('funnelTable', {})
    head = [h['name'] for h in t.get('dimensionHeaders', [])] + [h['name'] for h in t.get('metricHeaders', [])]
    rows = [[c['value'] for c in row.get('dimensionValues', [])] + [c['value'] for c in row.get('metricValues', [])] for row in t.get('rows', [])]
    table(head, rows)


def main():
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return
    cmd = args[0]
    days = int(args[args.index('--days') + 1]) if '--days' in args else 7
    if cmd == 'properties':
        table(['property', 'name', 'account'], properties()); return
    pid = property_id()
    print(f'property {pid}, last {days} days\n')
    if cmd == 'summary':
        print('totals'); table(['users', 'sessions', 'views', 'avg engagement s'],
                               report(pid, [], ['activeUsers', 'sessions', 'screenPageViews', 'averageSessionDuration'], days))
        print('\ncountries'); table(['country', 'users', 'sessions', 'engaged', 'avg s'],
                                    report(pid, ['country'], ['activeUsers', 'sessions', 'engagedSessions', 'averageSessionDuration'], days, order='sessions'))
        print('\nsources'); table(['source / medium', 'sessions'],
                                  report(pid, ['sessionSourceMedium'], ['sessions'], days, order='sessions', limit=20))
        print('\ndevices'); table(['device', 'sessions'], report(pid, ['deviceCategory'], ['sessions'], days))
    elif cmd == 'sections':
        # GA4's pagePath drops the #fragment, so every section is "/"; the section's title is the page_title the router sends
        table(['section', 'views', 'users'],
              report(pid, ['pageTitle'], ['screenPageViews', 'activeUsers'], days, order='screenPageViews', limit=80))
    elif cmd == 'country':
        code = args[1].upper()
        f = eq('countryId', code)
        print('sessions by day'); table(['date', 'sessions', 'users', 'avg s', 'engaged'],
                                        report(pid, ['date'], ['sessions', 'activeUsers', 'averageSessionDuration', 'engagedSessions'], days, f, order='sessions'))
        print('\ncity, source, device, browser'); table(['city', 'source / medium', 'device', 'browser', 'sessions', 'avg s'],
                                                        report(pid, ['city', 'sessionSourceMedium', 'deviceCategory', 'browser'], ['sessions', 'averageSessionDuration'], days, f))
        print('\nsections'); table(['section', 'views'], report(pid, ['pageTitle'], ['screenPageViews'], days, f, order='screenPageViews'))
        print('\nevents'); table(['event', 'count'], report(pid, ['eventName'], ['eventCount'], days, f, order='eventCount'))
    elif cmd == 'layout':
        # needs the event-scoped custom dimensions layout and viewport_width registered in GA4 Admin > Custom definitions
        print('layout by country and device'); table(['layout', 'country', 'device', 'sessions', 'views'],
              report(pid, ['customEvent:layout', 'country', 'deviceCategory'], ['sessions', 'screenPageViews'], days, order='sessions'))
        print('\nviewport widths'); table(['width', 'device', 'views'],
              report(pid, ['customEvent:viewport_width', 'deviceCategory'], ['screenPageViews'], days, order='screenPageViews', limit=40))
    elif cmd == 'cards':
        # needs the event-scoped custom dimensions card and audit registered in GA4 Admin > Custom definitions
        print('cards opened'); table(['card', 'section', 'opens', 'users'],
              report(pid, ['customEvent:card', 'customEvent:section'], ['eventCount', 'activeUsers'], days,
                     eq('eventName', 'card_open'), order='eventCount', limit=60))
        print('\naudits: opened vs copied')
        opened = {r[0]: int(r[1]) for r in report(pid, ['customEvent:card'], ['eventCount'], days, eq('eventName', 'card_open'), limit=100) if r[0].startswith('audit-')}
        copied = {'audit-' + r[0]: int(r[1]) for r in report(pid, ['customEvent:audit'], ['eventCount'], days, eq('eventName', 'audit_copy'), limit=100)}
        table(['audit', 'opened', 'copied'], [[a, opened.get(a, 0), copied.get(a, 0)] for a in sorted(set(opened) | set(copied))])
    elif cmd == 'events':
        table(['event', 'count', 'users'], report(pid, ['eventName'], ['eventCount', 'activeUsers'], days, order='eventCount'))
    elif cmd == 'path':
        rows = report(pid, ['pageTitle'], ['screenPageViews', 'activeUsers'], days, limit=200)
        by = {r[0]: (int(r[1]), int(r[2])) for r in rows}
        secs = soft(lambda: {r[0]: float(r[1]) for r in report(pid, ['customEvent:section'], ['customEvent:seconds'], days, eq('eventName', 'section_leave'), limit=200)}, {})
        base = by.get(PATH_TITLES[0], (0, 0))[1] or 1
        print('reach: users per section, as a share of Start Here users; seconds on screen per user')
        table(['section', 'views', 'users', 'share', 'min per user'],
              [[t, by.get(t, (0, 0))[0], by.get(t, (0, 0))[1], f'{100 * by.get(t, (0, 0))[1] / base:.0f}%',
                f'{secs.get(t, 0) / 60 / max(1, by.get(t, (0, 0))[1]):.1f}'] for t in PATH_TITLES + ['Transmission']])
        print(f'\nreading order total: {sum(secs.get(t, 0) for t in PATH_TITLES) / 60 / base:.1f} min per Start Here user, against the page\'s promise')
        print('\narrivals through the read-this-first list')
        table(['section', 'views'], soft(lambda: report(pid, ['pageTitle'], ['screenPageViews'], days, eq('customEvent:via', 'path'), limit=50), []))
        print('\nfunnel: users who reached each step in order (open funnel, so a step counts whenever it follows the last)')
        funnel(pid, days)
    elif cmd == 'via':
        print('by source'); table(['via', 'views', 'users'], report(pid, ['customEvent:via'], ['screenPageViews', 'activeUsers'], days, eq('eventName', 'page_view'), order='screenPageViews'))
        print('\nby source and section'); table(['via', 'section', 'views'],
              report(pid, ['customEvent:via', 'pageTitle'], ['screenPageViews'], days, eq('eventName', 'page_view'), order='screenPageViews', limit=60))
    elif cmd == 'order':
        rows = report(pid, ['customEvent:view_index', 'pageTitle'], ['screenPageViews'], days, eq('eventName', 'page_view'), limit=2000)
        by = {}
        for idx, title, n in rows:
            if idx.isdigit(): by.setdefault(int(idx), []).append((int(n), title))
        out = []
        for i in sorted(by)[:10]:
            top = sorted(by[i], reverse=True)[:3]; total = sum(n for n, _ in by[i])
            out.append([i, total, ', '.join(f'{t} ({n})' for n, t in top)])
        table(['position', 'views', 'most common sections'], out)
    elif cmd == 'depth':
        views = {r[0]: int(r[1]) for r in report(pid, ['pageTitle'], ['screenPageViews'], days, eq('eventName', 'page_view'), limit=200)}
        half, full = {}, {}
        for sec, d, n in report(pid, ['customEvent:section', 'customEvent:depth'], ['eventCount'], days, eq('eventName', 'section_scroll'), limit=400):
            (half if d == '50' else full)[sec] = int(n)
        left = {r[0]: (float(r[1]), int(r[2])) for r in report(pid, ['customEvent:section'], ['customEvent:seconds', 'eventCount'], days, eq('eventName', 'section_leave'), limit=200)}
        out = []
        for sec, v in sorted(views.items(), key=lambda kv: -kv[1]):
            s, c = left.get(sec, (0.0, 0))
            out.append([sec, v, half.get(sec, 0), full.get(sec, 0), f'{100 * full.get(sec, 0) / v:.0f}%' if v else '', f'{s / max(1, v):.0f}'])
        table(['section', 'views', 'halfway', 'to the end', 'finish rate', 'avg s on screen'], out)
    else:
        sys.exit('unknown command; see --help')


if __name__ == '__main__':
    try:
        main()
    except Unregistered as e:
        sys.exit(f'waiting on GA4: register the event-scoped custom {e.args[1]} "{e.args[0]}" under Admin > Custom definitions; data shows from then on')
