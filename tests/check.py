#!/usr/bin/env python3
"""Integrity checks for marrydavid.com's single-file site.

Static checks need only python3 + node. Set CHROME_BIN (or have Chrome at the
default macOS path) to also run the rendered smoke test.
"""
import os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, 'index.html')
failures = []

def check(name, ok, detail=''):
    print(('PASS' if ok else 'FAIL'), name, ('- ' + detail if detail and not ok else ''))
    if not ok:
        failures.append(name)

s = open(HTML, encoding='utf-8').read()

# --- sections & internal links -------------------------------------------
sections = re.findall(r'<section class="topic" id="([a-z]+)" data-title="([^"]*)"', s)
ids = [i for i, _ in sections]
check('section ids unique', len(ids) == len(set(ids)))
check('every section has a title', all(t.strip() for _, t in sections))
chaptered = re.findall(r'<section class="topic" id="([a-z]+)" data-title="[^"]*" data-chapter="[^"]+"', s)
check('every section has a chapter', set(chaptered) == set(ids), f'missing: {sorted(set(ids) - set(chaptered))}')

audits_src = s.split('const AUDITS = [', 1)[1].split('\n  ];', 1)[0]
n_audits = len(re.findall(r'\n      title:', audits_src))
check('audit count sane', 10 <= n_audits <= 40, f'found {n_audits}')

valid = set(ids) | {f'audit-{i:02d}' for i in range(0, n_audits + 1)} | {'content'}  # 00 is the static meta-audit; content is the skip-link target
hrefs = set(re.findall(r'href="#([a-zA-Z0-9-]+)"', s))
bad = hrefs - valid
check('internal links resolve', not bad, f'dangling: {sorted(bad)}')

# --- cross-referenced counts ---------------------------------------------
audits_sec = re.search(r'id="audits".*?</p>', s, re.S).group(0)
nums = [int(n) for n in re.findall(r'\b(\d{1,2})\b', audits_sec)]
check('ledger subhead names the last audit', nums and max(nums) == n_audits,
      f'subhead max {max(nums) if nums else None} vs {n_audits} audits')
m = re.search(r'runs 05–(\d+)', s)
check('radius crosslink names the last audit', m and int(m.group(1)) == n_audits)

WORDS = {'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
         'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16}
TENS = {'twenty': 20, 'thirty': 30, 'forty': 40}
ONES = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9}
def word_to_int(w):
    w = w.lower()
    if w in WORDS: return WORDS[w]
    if w in TENS: return TENS[w]
    a, _, b = w.partition('-')
    return TENS.get(a, 0) + ONES.get(b, 0) if a in TENS and b in ONES else None

# "Thirty-one sections about me" counts every section except Questions for You itself
m = re.search(r'([A-Z][a-z]+(?:-[a-z]+)?) sections about me is a monologue', s)
check('questions subhead counts the other sections', m and word_to_int(m.group(1)) == len(ids) - 1,
      f'subhead says {m.group(1) if m else "?"}, sections minus itself = {len(ids) - 1}')
db_sec = re.search(r'<section class="topic" id="dealbreakers".*?</section>', s, re.S).group(0)
db_main = db_sec.split('<h3', 1)[0]
n_db = db_main.count('<span class="k">')
m = re.search(r'These (\w+) are structural', s)
check('dealbreaker count matches subhead', m and WORDS.get(m.group(1)) == n_db,
      f'{n_db} items vs "These {m.group(1) if m else "?"}"')

# --- content invariants ---------------------------------------------------
check('email never in source', 'david@marrydavid.com' not in s and 'david@datedavid.org' not in s and 'mailto:david' not in s)
style = s.split('<style>', 1)[1].split('</style>', 1)[0]
bad_css = [l.strip() for l in style.splitlines() if 'content:' in l and '\\u' in l]
check('no \\u escapes in CSS content', not bad_css, str(bad_css))

BANNED = ['load-bearing', 'load bearing', 'delve', 'testament to', 'paradigm shift',
          "isn't just", 'not just about', 'game-chang', 'double-click on']
hits = [b for b in BANNED if b in s.lower()]
check('no banned phrases', not hits, str(hits))
n4 = open(os.path.join(ROOT, '404.html'), encoding='utf-8').read()
check('analytics id present on both pages', 'G-GD340Z2HSF' in s and 'G-GD340Z2HSF' in n4)
check('analytics loads only after consent', 'src="https://www.googletagmanager.com' not in s and 'src="https://www.googletagmanager.com' not in n4 and "localStorage.getItem('consent')" in s)
check('fonts self-hosted, no Google Fonts requests', 'fonts.googleapis.com' not in s and 'fonts.gstatic.com' not in s and 'fonts.googleapis.com' not in n4)
fontfiles = set(re.findall(r"url\('(fonts/[^']+)'\)", s))
check('font files exist', fontfiles and all(os.path.exists(os.path.join(ROOT, f)) for f in fontfiles), str(sorted(fontfiles)))

# audit prompts may use em dashes; the visible prose keeps a budget
patent_src = s.split('<div class="body patent">', 1)[1].split('</details>', 1)[0] if '<div class="body patent">' in s else ''
n_dash = (s.count('\u2014') - audits_src.count('\u2014') - patent_src.count('\u2014')) + (s.count('\\u2014') - audits_src.count('\\u2014'))
check('em-dash budget outside audit prompts and the filing (<=16)', n_dash <= 16, f'found {n_dash}')

check('radius numbers consistent',
      '460&nbsp;miles / 740&nbsp;km' in s and '7 hours 4 minutes' in s
      and '8 hours 4 minutes' in s and '6 hours 19 minutes' in s and '370&nbsp;km/s' in s)
check('reduced motion switches every animation and transition off', 'prefers-reduced-motion: reduce' in s and 'animation-duration: 0.001ms !important' in s and 'transition-duration: 0.001ms !important' in s)
check('no stale pre-EV time budget', '5 hours 19 minutes' not in s and '7-hour clock' not in s and 'seven-hour travel budget' not in s)
check('no stale one-second radius', '370 km <span>' not in s and '≈370' not in s and 'radius is 230' not in s and '≈230&nbsp;mi' not in s)
check('birthdate constant in both tickers', s.count('Date.UTC(1986, 2, 31') == 2)

# --- assets & accessibility ----------------------------------------------
imgs = re.findall(r'<img\b[^>]*>', s)
check('all images have alt text', all('alt="' in i for i in imgs))
srcs = re.findall(r'<img[^>]*src="(photos/[^"]+)"', s)
missing = [p for p in srcs if not os.path.exists(os.path.join(ROOT, p))]
check('image files exist', not missing, str(missing))
for sld in ('sldDelay', 'sldKids'):
    tag = re.search(r'<input[^>]*id="%s"[^>]*>' % sld, s)
    check(f'{sld} has aria-label', tag and 'aria-label' in tag.group(0))

# --- no-JS fallback and 404 ----------------------------------------------
check('noscript fallback shows sections', '<noscript>' in s and 'section.topic { display: block' in s)
nf = os.path.join(ROOT, '404.html')
check('404 page exists', os.path.exists(nf))
if os.path.exists(nf):
    n4 = open(nf, encoding='utf-8').read()
    check('404 links home', 'href="/"' in n4)
    check('404 is noindex', 'name="robots" content="noindex"' in n4)
    check('404 email never in source', 'david@' not in n4 and 'mailto:' not in n4)

check('robots.txt allows crawling and names the sitemap', os.path.exists(os.path.join(ROOT, 'robots.txt')) and 'Sitemap: https://marrydavid.com/sitemap.xml' in open(os.path.join(ROOT, 'robots.txt')).read())
check('sitemap.xml lists the canonical URL', os.path.exists(os.path.join(ROOT, 'sitemap.xml')) and '<loc>https://marrydavid.com/</loc>' in open(os.path.join(ROOT, 'sitemap.xml')).read())

# --- relationship status bar ---------------------------------------------
import datetime
STAGES = ['Square 1: Not Past First Date', 'Hopeful: Exclusively Dating', 'Getting Close: Engagement Approaching', 'Tada! Engaged!!']
bar = re.search(r'<aside class="status" id="status"[^>]*>.*?</aside>', s, re.S)
check('status bar present, after main', bool(bar) and bar.start() > s.index('</main>'))
stage = 0
if bar:
    b = bar.group(0)
    m = re.search(r'data-stage="(\d)"', b)
    stage = int(m.group(1)) if m else 0
    check('status bar data-stage is 1..4', 1 <= stage <= 4, f'data-stage={m.group(1) if m else None}')
    m2 = re.search(r'data-since="(\d{4}-\d{2}-\d{2})"', b)
    check('status bar data-since is a past or present date', bool(m2) and datetime.date.fromisoformat(m2.group(1)) <= datetime.date.today())
    check('status bar since line matches data-since', bool(m2) and f'<time datetime="{m2.group(1)}">{m2.group(1)}</time>' in b)
    lis = re.findall(r'<li data-n="(\d)">(.*?)</li>', b, re.S)
    check('status bar has four stages, numbered 1 to 4', [int(n) for n, _ in lis] and sorted(int(n) for n, _ in lis) == [1, 2, 3, 4], str([n for n, _ in lis]))
    now = re.search(r'<ol class="now" role="list">(.*?)</ol>', b, re.S)
    now_lis = re.findall(r'<li data-n="(\d)">(.*?)</li>', now.group(1), re.S) if now else []
    check('exactly one stage sits in the current slot, matching data-stage', len(now_lis) == 1 and int(now_lis[0][0]) == stage, str([n for n, _ in now_lis]))
    cur = [int(n) for n, li in lis if 'aria-current="step"' in li]
    check('aria-current marks the current stage only', cur == [stage], f'aria-current on {cur}, data-stage {stage}')
    check('the pulldown holds the other stages', '<details class="next">' in b and all(int(n) != stage for n, _ in re.findall(r'<li data-n="(\d)">(.*?)</li>', b[b.index('<details class="next">'):], re.S)))
    btns = re.findall(r'<button[^>]*>.*?</button>', b, re.S)
    check('stages are buttons with no links inside', len(btns) == 4 and all('type="button"' in x and '<a ' not in x for x in btns))
    names = {int(n): re.sub(r'<[^>]+>', '', re.search(r'<span class="t">(.*?)</span></button>', li, re.S).group(1)) for n, li in lis}
    check('stage names are the four agreed labels', [names.get(i) for i in range(1, 5)] == STAGES, str(names))
    check('every stage has a note that links to a section', all(re.search(r'<p class="why" hidden>.*?href="#[a-z]+".*?</p>', li, re.S) for _, li in lis))
check('nav rail is empty in the source', '<div class="rail" id="navRail"></div>' in s)

# --- unlisted pages ------------------------------------------------------
# reachable only by direct link: noindex, no email in source, never linked from the main page or the sitemap
sm = open(os.path.join(ROOT, 'sitemap.xml')).read() if os.path.exists(os.path.join(ROOT, 'sitemap.xml')) else ''
for slug in ('coronacrush', 'shabbat', 'justmatched'):
    pg = os.path.join(ROOT, slug, 'index.html')
    check(f'{slug} page exists', os.path.exists(pg))
    if not os.path.exists(pg):
        continue
    src = open(pg, encoding='utf-8').read()
    check(f'{slug} is noindex', 'content="noindex' in src)
    check(f'{slug} email never in source', 'david@' not in src and 'mailto:' not in src)
    check(f'{slug} is unlisted', f'href="/{slug}' not in s and f'href="{slug}' not in s and f'/{slug}' not in sm)
    check(f'{slug} analytics loads only after consent', 'src="https://www.googletagmanager.com' not in src and "localStorage.getItem('consent')" in src)
    check(f'{slug} greeting is sanitized', "get('for')" in src and 'replace(/[^A-Za-z' in src)
    check(f'{slug} states the current status', stage and (STAGES[stage - 1].upper() in src) and ('SINCE ' + (re.search(r'data-since="([^"]+)"', s).group(1)) in src))
    deep = set(re.findall(r'href="\.\./#([^"]+)"', src))
    bad = [i for i in deep if i not in valid]
    check(f'{slug} links into the main page resolve', not bad, str(bad))

# --- audit recheck schedule (warns, never fails) --------------------------
m = re.search(r'Next full recheck due <strong>(\d{4}-\d{2}-\d{2})</strong>', s)
check('ledger states a recheck date', bool(m))
if m and datetime.date.fromisoformat(m.group(1)) < datetime.date.today():
    print('WARN  the audit recheck date has passed: rerun the ledger and update the dates on the Audit Ledger page')
check('skip link and focusable main', 'class="skip" href="#content"' in s and 'id="content" tabindex="-1"' in s)

# --- metadata -------------------------------------------------------------
for needle, name in [('property="og:image"', 'og:image'), ('property="og:title"', 'og:title'),
                     ('rel="canonical"', 'canonical'), ('name="description"', 'meta description'),
                     ('rel="icon"', 'favicon'), ('<title>', 'title tag')]:
    check(f'metadata: {name}', needle in s)

# --- javascript parses ----------------------------------------------------
js = s.rsplit('<script>', 1)[1].rsplit('</script>', 1)[0]  # the site's own script is the last one
with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
    f.write(js); jspath = f.name
r = subprocess.run(['node', '--check', jspath], capture_output=True, text=True)
check('javascript parses', r.returncode == 0, r.stderr[:300])
os.unlink(jspath)

# --- rendered smoke test (needs Chrome) ----------------------------------
chrome = os.environ.get('CHROME_BIN') or '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
if os.path.exists(chrome) or os.environ.get('CHROME_BIN'):
    probe = s.replace('</body>', """<script>
window.__errs=[];window.onerror=(m)=>{__errs.push(String(m))};
window.addEventListener('load',()=>setTimeout(()=>{
  document.title=(__errs.length?('JSERR:'+__errs[0]):'JSOK')
    +'|tabs='+document.querySelectorAll('#navRail a').length
    +'|age='+(document.getElementById('age')||{}).textContent
    +'|a07='+(document.getElementById('audit-07')||{}).open
    +'|st='+document.querySelectorAll('#status [aria-current="step"]').length
    +'|stn='+(function(){var b=document.querySelectorAll('#status details.next button.stage')[0];if(!b)return 'none';b.click();var n=document.getElementById('statusNote');return (n&&!n.hidden&&n.querySelector('a'))?'open':'closed';})();},400));
</script></body>""")
    with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, dir=ROOT, encoding='utf-8') as f:
        f.write(probe); ppath = f.name
    try:
        r = subprocess.run([chrome, '--headless=new', '--disable-gpu', '--no-sandbox',
                            '--virtual-time-budget=4000', '--window-size=900,900',
                            '--dump-dom', 'file://' + ppath + '#audit-07'],
                           capture_output=True, text=True, timeout=90)
        title = re.search(r'<title>([^<]*)</title>', r.stdout)
        t = title.group(1) if title else ''
        check('smoke: no JS errors', t.startswith('JSOK'), t[:200])
        check('smoke: nav tab count matches sections', f'tabs={len(ids)}' in t, t[:200])
        check('smoke: age ticker runs', re.search(r'age=4\d\.\d{6}', t) is not None, t[:200])
        check('smoke: audit deep link opens card', 'a07=true' in t, t[:200])
        check('smoke: status bar marks one current stage', '|st=1|' in t, t[:200])
        check('smoke: clicking an inactive stage opens its note', 'stn=open' in t, t[:200])
    finally:
        os.unlink(ppath)
else:
    print('SKIP rendered smoke test (no Chrome found; set CHROME_BIN)')

print()
if failures:
    print(f'{len(failures)} FAILURE(S):', ', '.join(failures)); sys.exit(1)
print(f'all checks passed ({n_audits} audits, {len(ids)} sections, {n_db} dealbreakers)')
