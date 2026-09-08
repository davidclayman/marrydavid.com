# marrydavid.com

The source for [marrydavid.com](https://marrydavid.com/), a single-page, radically
transparent dating site. If you arrived here from the site's FAQ, this repository
is the receipts: every position on the page, every revision to it, and every
number behind it, timestamped in the commit log.

## The premise

The dating radius is two astronomical seconds: two seconds of the Sun's motion
relative to the cosmic microwave background, about 460 miles or 740 km. An
"travel reach" rule converts that distance into a wall-clock travel budget (about
eight hours, benchmarked on the author's EV with its charging stops) so any US
or Canadian city reachable nonstop inside the same clock also qualifies. Around that
frame sits a full disclosure of the life plan: family size, the marriage
timeline, money, geography, health, dealbreakers, and an age range stated as a
function of family feasibility rather than taste.

Every factual claim is paired with an audit prompt the reader can paste into
any AI assistant. Nothing on the site asks to be taken on faith, and the site
says so.

## How it works

**One static file.** Everything is `index.html`: hand-written CSS, vanilla
JavaScript, no framework, no build step. The three typefaces are self-hosted
from `fonts/`. Google Analytics is the only third party. It loads by default
(sections are sent as page views, calls to action as events) and stays off for
anyone who flipped the switch on the Privacy section or whose browser sends
Global Privacy Control; there is no consent banner. The Privacy section
documents the rest.
`404.html` redirects `/family`-style paths to `/#family` and otherwise links
home. A few unlisted follow-up pages (each in its own folder, `noindex`, never
linked from the main page or the sitemap) exist for people met in person or
matched on an app, and `/safeword/` holds the intimacy chapter, shared after a
first kiss rather than published; they take `?for=Name` to personalize the
greeting and carry no state beyond an optional reading checklist kept in the
visitor's browser. One follow-up page is public and linked: `/play/`, reached
from Proposal 05, holds a criss-cross crossword whose every answer appears on
the main page (the tests check that) and a sort of the Dealbreakers and Don't
Care filters, each verdict deep-linked to the paragraph that decides it.

**Two layers.** The first section, Start Here, is the profile: hook, photo,
introduction, what dating him is like, what he's looking for, the essential
filters, and a low-stakes invitation. Every other section is the laboratory
behind it. Long arguments inside a section (the family-property math, the
optimal-stopping models, the full Shelf) sit in collapsed cards so the page
reads short first and deep on request.

**A reading order, with times.** The site runs to about forty thousand words
of prose, so Start Here names the four sections worth reading next (What You
Get, Family, Dealbreakers, Age Range) and the minutes the five take together.
The Contents page shows a reading time beside every entry and every chapter.
The times are computed in the browser from each section's rendered text at
250 words a minute (`WPM` in the script; `[data-mins]`, `[data-mins-sum]`,
`[data-mins-n]`, `#pathMins`, `#pathRest` are the fill points), after the
ledger renders, so they stay honest as the copy changes. Reference material
(Verify Me, the Audit Ledger, Revisions, Acknowledgments, the Glossary) sits
in a final chapter, "The appendix", after the last essay.

**The prior-art page.** `/prior-art/datelocket/` holds the full provisional
application for Date Locket, verbatim, published as prior art and dedicated
under CC0 instead of filed. Unlike the follow-up pages above it is listed in
the sitemap and indexable; the Date Locket section carries the plain-language
version and links to it. The first path segment has a hyphen on purpose, so
`404.html`'s section redirect never sees it.

**Sections and navigation.** Each topic is a
`<section class="topic" id="..." data-title="..." data-chapter="...">`. A hash
router shows one section per `#id` and builds the nav rail from DOM order. The
Contents page groups the sections into chapters from the `data-chapter`
attribute. Add a section, tag its chapter, and both update themselves, reading
time included. The chapters run Start here, The strategy, The plan, The
filters, Trust, but verify, Your turn, and The appendix; the tests insist the
appendix stays last.

**Recheck cadence.** The Audit Ledger states when every prompt was last run in
full and when the next full recheck is due (quarterly). The test suite prints a
warning, not a failure, once that date passes. Notes Received publishes
anonymized reader feedback; the Glossary defines the Jewish and technical terms
the site uses.

**Accessibility.** A skip link (`#content`) jumps past the navigation and focuses
`main`; every interactive element has a visible focus style; the active nav link
carries `aria-current`; sliders and the map carry labels; motion respects
`prefers-reduced-motion`.

**The Audit Ledger.** Claims map to numbered `{ title, claim, prompt }` entries in
the `AUDITS` array in the inline script. Cards render automatically and
`#audit-NN` deep links open and scroll to a card. Audit 00 is a static meta-audit
of the whole site. The placeholder `{{AGE}}` inside any prompt is replaced with
the author's live fractional age at the moment the prompt is copied, so the
copied text carries the age without the page stating a birthdate.

**Live widgets.** The cosmic odometer, the ticking fractional age, the grandparent
clock with adjustable assumption sliders, the age-range ceiling, the nine-month
chuppah date, and the Travel Reach map are all inline JavaScript. The map is
generated SVG over a simplified lower-48 outline.

**Relationship status.** The line at the foot of every page is static markup:
the current stage lit and marked by `aria-current="step"`, the future steps in a
`<details>` pulldown, and `data-stage` and `data-since` on the
`<aside class="status">`. Only the notes behind the stages are scripted.

**Contact.** The email address is assembled at view time and never appears in the
page source. "Request a video call" buttons (`a.bookcall`) open a Google Calendar
appointment schedule (`BOOK_URL` in the script); the three-times email fallback
(`a.bookmail`) is a prefilled `mailto:` built the same way.

**No JavaScript.** A `<noscript>` block shows every section as one long scroll,
hides the empty nav rail, and explains that the clocks, the ledger, and the
contact address need scripting.

## Editing

The copy has house rules, and the test suite enforces most of them:

- Claims stay auditable. A new factual claim gets an audit card or a step in an
  existing one.
- Sparing em dashes in visible prose (a budget of sixteen outside the audit
  prompts), and none of the usual AI-writing tics; see `BANNED` in the tests.
- Counts written in prose must match the page: the number of dealbreakers, the
  number of sections named on the Questions page, the last audit number named
  in the Radius crosslink and the ledger subhead.
- Every section has a title and a chapter. Every internal link resolves. Every
  image has alt text and its file exists.
- Every subtopic is deep-linkable: list items, `h3.head-sm` sub-headings,
  collapsed cards, and `<p><strong>Label.</strong>` paragraphs carry ids
  (`section-slug`, or `db-*` / `dc-*` / `faq-NN`), with the title as an
  `a.deep` link or a hover `#` mark. `#budget-promise` opens Budget and scrolls
  to the paragraph; a target inside a collapsed card opens the card. New items
  need the same id and link; the tests fail on any without.
- The contact address never appears in the source of either page.
- To change the relationship status, move the new stage's `<li>` from the
  pulldown into `ol.now` (and the old one back, with `class="past"`), keep
  `aria-current="step"` on the current button, update `data-stage`,
  `data-since`, and the `<time>`, update the one-line status on the three
  unlisted pages, and add a dated Revisions entry. The tests fail if any of
  those disagree.

Photos live in `photos/` and are dated in their captions. Metadata in `<head>`
assumes the canonical URL `https://marrydavid.com/`.

## Tests

```
python3 tests/check.py
```

Static checks need only Python 3 and Node. If Chrome is installed (or
`CHROME_BIN` points at one), the suite also renders the page headless and
checks that the router, the tickers, and the audit deep links work with no
JavaScript errors. The same script runs in GitHub Actions on every push.

## Deploying

Push to `main`. GitHub Pages serves the repository root as static files at the
`CNAME` domain.
