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
    python3 analytics/ga.py path      [--days 7]    # how far the Start Here reading order carries readers

Set GA_PROPERTY to skip discovery (a number like 4xxxxxxxxx).
"""
import json, os, subprocess, sys, urllib.request

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


def call(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={'Authorization': 'Bearer ' + token(), 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f'{e.code} from {url}\n{e.read().decode()[:600]}')


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
    elif cmd == 'events':
        table(['event', 'count', 'users'], report(pid, ['eventName'], ['eventCount', 'activeUsers'], days, order='eventCount'))
    elif cmd == 'path':
        rows = report(pid, ['pageTitle'], ['screenPageViews', 'activeUsers'], days, limit=200)
        by = {r[0]: (int(r[1]), int(r[2])) for r in rows}
        table(['section', 'views', 'users'], [[t] + list(by.get(t, (0, 0))) for t in PATH_TITLES + ['Transmission']])
    else:
        sys.exit('unknown command; see --help')


if __name__ == '__main__':
    main()
