/* @ds-bundle: {"format": 4, "namespace": "Alo", "components": [{"name": "Button"}, {"name": "MicButton"}, {"name": "SpeechBubble"}, {"name": "ReadingPanel"}, {"name": "MoonProgress"}, {"name": "RewardBadge"}, {"name": "LanternStreak"}, {"name": "Japa"}, {"name": "ParentReportCard"}, {"name": "ProfilePill"}, {"name": "RoundButton"}, {"name": "Paper"}, {"name": "Eyebrow"}, {"name": "Field"}, {"name": "ToggleGroup"}, {"name": "Banner"}]} */
(function () {
  var React = window.React, h = React.createElement;
  var JAPA = {"happy": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 248 180\" role=\"img\" aria-label=\"Jàpá, happy\"><title>Jàpá, happy</title><ellipse cx=\"108\" cy=\"166\" rx=\"84\" ry=\"8\" fill=\"#221A4D\" opacity=\".12\"/><path d=\"M30 128c-12 3-17-2-17-9\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linecap=\"round\" fill=\"none\"/><rect x=\"44\" y=\"126\" width=\"28\" height=\"36\" rx=\"14\" fill=\"#3FB98A\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><rect x=\"132\" y=\"126\" width=\"28\" height=\"36\" rx=\"14\" fill=\"#3FB98A\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><rect x=\"96\" y=\"130\" width=\"26\" height=\"32\" rx=\"13\" fill=\"#3FB98A\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><rect x=\"20\" y=\"112\" width=\"170\" height=\"26\" rx=\"13\" fill=\"#FFC83D\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><path d=\"M28 118C28 56 68 30 105 30s77 26 77 88z\" fill=\"#4B3BD1\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><circle cx=\"105\" cy=\"68\" r=\"13\" fill=\"none\" stroke=\"#FFC83D\" stroke-width=\"4\"/><circle cx=\"105\" cy=\"68\" r=\"4\" fill=\"#FFC83D\"/><circle cx=\"66\" cy=\"96\" r=\"9\" fill=\"none\" stroke=\"#FFC83D\" stroke-width=\"4\"/><circle cx=\"144\" cy=\"96\" r=\"9\" fill=\"none\" stroke=\"#FFC83D\" stroke-width=\"4\"/><circle cx=\"84\" cy=\"104\" r=\"3\" fill=\"#FFC83D\"/><circle cx=\"126\" cy=\"104\" r=\"3\" fill=\"#FFC83D\"/><circle cx=\"80\" cy=\"56\" r=\"3\" fill=\"#FFC83D\"/><circle cx=\"130\" cy=\"56\" r=\"3\" fill=\"#FFC83D\"/><g><circle cx=\"180\" cy=\"96\" r=\"30\" fill=\"#3FB98A\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><circle cx=\"168\" cy=\"88\" r=\"9.5\" fill=\"#FFFFFF\" stroke=\"#221A4D\" stroke-width=\"3\"/><circle cx=\"169\" cy=\"89\" r=\"4.8\" fill=\"#221A4D\"/><circle cx=\"170.8\" cy=\"87\" r=\"1.5\" fill=\"#FFFFFF\"/><circle cx=\"192\" cy=\"88\" r=\"9.5\" fill=\"#FFFFFF\" stroke=\"#221A4D\" stroke-width=\"3\"/><circle cx=\"193\" cy=\"89\" r=\"4.8\" fill=\"#221A4D\"/><circle cx=\"194.8\" cy=\"87\" r=\"1.5\" fill=\"#FFFFFF\"/><circle cx=\"160\" cy=\"106\" r=\"5\" fill=\"#FF9A82\"/><circle cx=\"200\" cy=\"106\" r=\"5\" fill=\"#FF9A82\"/><path d=\"M171 107q9 9 18 0\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linecap=\"round\" fill=\"none\"/></g></svg>", "cheer": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 248 180\" role=\"img\" aria-label=\"Jàpá, cheering\"><title>Jàpá, cheering</title><ellipse cx=\"108\" cy=\"166\" rx=\"84\" ry=\"8\" fill=\"#221A4D\" opacity=\".12\"/><path d=\"M30 128c-12 3-17-2-17-9\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linecap=\"round\" fill=\"none\"/><rect x=\"44\" y=\"126\" width=\"28\" height=\"36\" rx=\"14\" fill=\"#3FB98A\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><rect x=\"132\" y=\"126\" width=\"28\" height=\"36\" rx=\"14\" fill=\"#3FB98A\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><rect x=\"20\" y=\"112\" width=\"170\" height=\"26\" rx=\"13\" fill=\"#FFC83D\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><path d=\"M28 118C28 56 68 30 105 30s77 26 77 88z\" fill=\"#4B3BD1\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><circle cx=\"105\" cy=\"68\" r=\"13\" fill=\"none\" stroke=\"#FFC83D\" stroke-width=\"4\"/><circle cx=\"105\" cy=\"68\" r=\"4\" fill=\"#FFC83D\"/><circle cx=\"66\" cy=\"96\" r=\"9\" fill=\"none\" stroke=\"#FFC83D\" stroke-width=\"4\"/><circle cx=\"144\" cy=\"96\" r=\"9\" fill=\"none\" stroke=\"#FFC83D\" stroke-width=\"4\"/><circle cx=\"84\" cy=\"104\" r=\"3\" fill=\"#FFC83D\"/><circle cx=\"126\" cy=\"104\" r=\"3\" fill=\"#FFC83D\"/><circle cx=\"80\" cy=\"56\" r=\"3\" fill=\"#FFC83D\"/><circle cx=\"130\" cy=\"56\" r=\"3\" fill=\"#FFC83D\"/><g><circle cx=\"180\" cy=\"96\" r=\"30\" fill=\"#3FB98A\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><circle cx=\"168\" cy=\"88\" r=\"9.5\" fill=\"#FFFFFF\" stroke=\"#221A4D\" stroke-width=\"3\"/><circle cx=\"168\" cy=\"88\" r=\"4.8\" fill=\"#221A4D\"/><circle cx=\"169.8\" cy=\"86\" r=\"1.5\" fill=\"#FFFFFF\"/><circle cx=\"192\" cy=\"88\" r=\"9.5\" fill=\"#FFFFFF\" stroke=\"#221A4D\" stroke-width=\"3\"/><circle cx=\"192\" cy=\"88\" r=\"4.8\" fill=\"#221A4D\"/><circle cx=\"193.8\" cy=\"86\" r=\"1.5\" fill=\"#FFFFFF\"/><circle cx=\"160\" cy=\"106\" r=\"5\" fill=\"#FF9A82\"/><circle cx=\"200\" cy=\"106\" r=\"5\" fill=\"#FF9A82\"/><path d=\"M169 105q11 17 22 0z\" fill=\"#221A4D\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><path d=\"M174 111q6 4 12 0\" stroke=\"#FF6B4A\" stroke-width=\"3\" stroke-linecap=\"round\" fill=\"none\"/></g><rect x=\"140\" y=\"44\" width=\"26\" height=\"44\" rx=\"13\" fill=\"#3FB98A\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\" transform=\"rotate(-28 153 66)\"/><path d=\"M40 24q2.0 8.0 10 10q-8.0 2.0-10 10q-2.0-8.0-10-10q8.0-2.0 10-10z\" fill=\"#FFC83D\" stroke=\"#221A4D\" stroke-width=\"2.5\" stroke-linejoin=\"round\"/><path d=\"M196 22q1.6 6.4 8 8q-6.4 1.6-8 8q-1.6-6.4-8-8q6.4-1.6 8-8z\" fill=\"#FFC83D\" stroke=\"#221A4D\" stroke-width=\"2.5\" stroke-linejoin=\"round\"/><path d=\"M20 70q1.2000000000000002 4.800000000000001 6 6q-4.800000000000001 1.2000000000000002-6 6q-1.2000000000000002-4.800000000000001-6-6q4.800000000000001-1.2000000000000002 6-6z\" fill=\"#FFC83D\" stroke=\"#221A4D\" stroke-width=\"2.5\" stroke-linejoin=\"round\"/></svg>", "listen": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 248 180\" role=\"img\" aria-label=\"Jàpá, listening\"><title>Jàpá, listening</title><ellipse cx=\"108\" cy=\"166\" rx=\"84\" ry=\"8\" fill=\"#221A4D\" opacity=\".12\"/><path d=\"M30 128c-12 3-17-2-17-9\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linecap=\"round\" fill=\"none\"/><rect x=\"44\" y=\"126\" width=\"28\" height=\"36\" rx=\"14\" fill=\"#3FB98A\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><rect x=\"132\" y=\"126\" width=\"28\" height=\"36\" rx=\"14\" fill=\"#3FB98A\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><rect x=\"96\" y=\"130\" width=\"26\" height=\"32\" rx=\"13\" fill=\"#3FB98A\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><rect x=\"20\" y=\"112\" width=\"170\" height=\"26\" rx=\"13\" fill=\"#FFC83D\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><path d=\"M28 118C28 56 68 30 105 30s77 26 77 88z\" fill=\"#4B3BD1\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><circle cx=\"105\" cy=\"68\" r=\"13\" fill=\"none\" stroke=\"#FFC83D\" stroke-width=\"4\"/><circle cx=\"105\" cy=\"68\" r=\"4\" fill=\"#FFC83D\"/><circle cx=\"66\" cy=\"96\" r=\"9\" fill=\"none\" stroke=\"#FFC83D\" stroke-width=\"4\"/><circle cx=\"144\" cy=\"96\" r=\"9\" fill=\"none\" stroke=\"#FFC83D\" stroke-width=\"4\"/><circle cx=\"84\" cy=\"104\" r=\"3\" fill=\"#FFC83D\"/><circle cx=\"126\" cy=\"104\" r=\"3\" fill=\"#FFC83D\"/><circle cx=\"80\" cy=\"56\" r=\"3\" fill=\"#FFC83D\"/><circle cx=\"130\" cy=\"56\" r=\"3\" fill=\"#FFC83D\"/><g transform=\"rotate(-10 180 96)\"><circle cx=\"180\" cy=\"96\" r=\"30\" fill=\"#3FB98A\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><circle cx=\"168\" cy=\"88\" r=\"9.5\" fill=\"#FFFFFF\" stroke=\"#221A4D\" stroke-width=\"3\"/><circle cx=\"170\" cy=\"85\" r=\"4.8\" fill=\"#221A4D\"/><circle cx=\"171.8\" cy=\"83\" r=\"1.5\" fill=\"#FFFFFF\"/><circle cx=\"192\" cy=\"88\" r=\"9.5\" fill=\"#FFFFFF\" stroke=\"#221A4D\" stroke-width=\"3\"/><circle cx=\"194\" cy=\"85\" r=\"4.8\" fill=\"#221A4D\"/><circle cx=\"195.8\" cy=\"83\" r=\"1.5\" fill=\"#FFFFFF\"/><circle cx=\"160\" cy=\"106\" r=\"5\" fill=\"#FF9A82\"/><circle cx=\"200\" cy=\"106\" r=\"5\" fill=\"#FF9A82\"/><circle cx=\"180\" cy=\"109\" r=\"4.5\" fill=\"#221A4D\"/></g><path d=\"M222 80q9 16 0 32\" stroke=\"#38A6EE\" stroke-width=\"5\" stroke-linecap=\"round\" fill=\"none\"/><path d=\"M234 70q15 26 0 52\" stroke=\"#38A6EE\" stroke-width=\"5\" stroke-linecap=\"round\" fill=\"none\"/></svg>", "think": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 248 180\" role=\"img\" aria-label=\"Jàpá, thinking\"><title>Jàpá, thinking</title><ellipse cx=\"108\" cy=\"166\" rx=\"84\" ry=\"8\" fill=\"#221A4D\" opacity=\".12\"/><path d=\"M30 128c-12 3-17-2-17-9\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linecap=\"round\" fill=\"none\"/><rect x=\"44\" y=\"126\" width=\"28\" height=\"36\" rx=\"14\" fill=\"#3FB98A\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><rect x=\"132\" y=\"126\" width=\"28\" height=\"36\" rx=\"14\" fill=\"#3FB98A\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><rect x=\"96\" y=\"130\" width=\"26\" height=\"32\" rx=\"13\" fill=\"#3FB98A\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><rect x=\"20\" y=\"112\" width=\"170\" height=\"26\" rx=\"13\" fill=\"#FFC83D\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><path d=\"M28 118C28 56 68 30 105 30s77 26 77 88z\" fill=\"#4B3BD1\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><circle cx=\"105\" cy=\"68\" r=\"13\" fill=\"none\" stroke=\"#FFC83D\" stroke-width=\"4\"/><circle cx=\"105\" cy=\"68\" r=\"4\" fill=\"#FFC83D\"/><circle cx=\"66\" cy=\"96\" r=\"9\" fill=\"none\" stroke=\"#FFC83D\" stroke-width=\"4\"/><circle cx=\"144\" cy=\"96\" r=\"9\" fill=\"none\" stroke=\"#FFC83D\" stroke-width=\"4\"/><circle cx=\"84\" cy=\"104\" r=\"3\" fill=\"#FFC83D\"/><circle cx=\"126\" cy=\"104\" r=\"3\" fill=\"#FFC83D\"/><circle cx=\"80\" cy=\"56\" r=\"3\" fill=\"#FFC83D\"/><circle cx=\"130\" cy=\"56\" r=\"3\" fill=\"#FFC83D\"/><g><circle cx=\"180\" cy=\"96\" r=\"30\" fill=\"#3FB98A\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linejoin=\"round\"/><circle cx=\"168\" cy=\"88\" r=\"9.5\" fill=\"#FFFFFF\" stroke=\"#221A4D\" stroke-width=\"3\"/><circle cx=\"165\" cy=\"84\" r=\"4.8\" fill=\"#221A4D\"/><circle cx=\"166.8\" cy=\"82\" r=\"1.5\" fill=\"#FFFFFF\"/><circle cx=\"192\" cy=\"88\" r=\"9.5\" fill=\"#FFFFFF\" stroke=\"#221A4D\" stroke-width=\"3\"/><circle cx=\"189\" cy=\"84\" r=\"4.8\" fill=\"#221A4D\"/><circle cx=\"190.8\" cy=\"82\" r=\"1.5\" fill=\"#FFFFFF\"/><circle cx=\"160\" cy=\"106\" r=\"5\" fill=\"#FF9A82\"/><circle cx=\"200\" cy=\"106\" r=\"5\" fill=\"#FF9A82\"/><path d=\"M172 109h14\" stroke=\"#221A4D\" stroke-width=\"4\" stroke-linecap=\"round\"/></g><circle cx=\"168\" cy=\"50\" r=\"4\" fill=\"#FFFFFF\" stroke=\"#221A4D\" stroke-width=\"3\"/><circle cx=\"184\" cy=\"38\" r=\"5.5\" fill=\"#FFFFFF\" stroke=\"#221A4D\" stroke-width=\"3\"/><circle cx=\"204\" cy=\"28\" r=\"7\" fill=\"#FFFFFF\" stroke=\"#221A4D\" stroke-width=\"3\"/></svg>"};
  var MARK = "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 64 64\" role=\"img\" aria-label=\"Alo.ai mark\"><title>Alo.ai mark</title><circle cx=\"32\" cy=\"26\" r=\"16\" stroke=\"#4B3BD1\" stroke-width=\"10\" fill=\"none\"/><circle cx=\"32\" cy=\"55\" r=\"6.5\" fill=\"#FF6B4A\"/></svg>";
  var G = {"mic": "<svg viewBox=\"0 0 24 24\" aria-hidden=\"true\"><rect x=\"8.5\" y=\"2.5\" width=\"7\" height=\"12\" rx=\"3.5\" fill=\"currentColor\"/><path d=\"M5 11a7 7 0 0 0 14 0M12 18v3.5M8.5 21.5h7\" stroke=\"currentColor\" stroke-width=\"2.5\" stroke-linecap=\"round\" fill=\"none\"/></svg>", "replay": "<svg viewBox=\"0 0 24 24\" aria-hidden=\"true\"><path d=\"M4.5 12a7.5 7.5 0 1 0 2.2-5.3L4 9.4M4 4.5v4.9h4.9\" stroke=\"currentColor\" stroke-width=\"2.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\" fill=\"none\"/></svg>", "star": "<svg viewBox=\"0 0 24 24\" aria-hidden=\"true\"><path d=\"M12 3l2.7 5.6 6.1.8-4.5 4.2 1.1 6.1L12 16.8l-5.4 2.9 1.1-6.1-4.5-4.2 6.1-.8z\" fill=\"currentColor\" stroke=\"currentColor\" stroke-width=\"1.5\" stroke-linejoin=\"round\"/></svg>", "lantern": "<svg viewBox=\"0 0 24 24\" aria-hidden=\"true\"><path d=\"M9 4.5a3 3 0 0 1 6 0M9 22h6\" stroke=\"currentColor\" stroke-width=\"2.5\" stroke-linecap=\"round\" fill=\"none\"/><rect x=\"6\" y=\"5.5\" width=\"12\" height=\"14\" rx=\"4\" fill=\"currentColor\"/></svg>", "book": "<svg viewBox=\"0 0 24 24\" aria-hidden=\"true\"><path d=\"M3 5.5c2.8-1.2 5.8-1 9 1 3.2-2 6.2-2.2 9-1v13c-2.8-1.2-5.8-1-9 1-3.2-2-6.2-2.2-9-1zM12 6.5v13\" stroke=\"currentColor\" stroke-width=\"2.5\" stroke-linejoin=\"round\" fill=\"none\"/></svg>", "check": "<svg viewBox=\"0 0 24 24\" aria-hidden=\"true\"><path d=\"M5.5 12.5l4.2 4.2L18.5 7.5\" stroke=\"currentColor\" stroke-width=\"3\" stroke-linecap=\"round\" stroke-linejoin=\"round\" fill=\"none\"/></svg>", "ear": "<svg viewBox=\"0 0 24 24\" aria-hidden=\"true\"><path d=\"M7 9a5 5 0 0 1 10 0c0 3-3 4-3 7a3 3 0 0 1-6 .5M10 9.5a2 2 0 0 1 4 0\" stroke=\"currentColor\" stroke-width=\"2.5\" stroke-linecap=\"round\" fill=\"none\"/></svg>"};
  G.next = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  G.play = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l11-6.5z" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>';
  G.info = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2.5"/><path d="M12 11v5M12 7.5v.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg>';
  G.good = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2.5"/><path d="M8 12l3 3 5-6" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  function cx() { return Array.prototype.filter.call(arguments, Boolean).join(' '); }
  function omit(p, keys) { var o = {}; for (var k in p) { if (keys.indexOf(k) < 0) o[k] = p[k]; } return o; }
  function glyph(name, cls) { return h('span', { className: cx('alo-glyph', cls), dangerouslySetInnerHTML: { __html: G[name] || '' } }); }

  function Button(p) {
    var variant = p.variant || 'primary', size = p.size || 'kid';
    return h('button', Object.assign({ type: 'button' }, omit(p, ['variant', 'size', 'icon', 'className', 'children']), {
      className: cx('alo-btn', 'alo-btn--' + variant, 'alo-btn--' + size, p.className)
    }), p.icon ? glyph(p.icon) : null, h('span', null, p.children));
  }

  function MicButton(p) {
    var state = p.state || 'idle';
    var label = p.label || (state === 'listening' ? 'Listening…' : state === 'thinking' ? 'One moment' : 'Tap to talk');
    return h('div', { className: 'alo-mic-wrap' },
      h('button', Object.assign({ type: 'button', 'aria-label': label }, omit(p, ['state', 'label', 'className']), {
        className: cx('alo-mic', 'alo-mic--' + state, p.className)
      }), state === 'thinking' ? h('span', { className: 'alo-dots' }, h('i'), h('i'), h('i')) : glyph('mic', 'alo-mic-glyph')),
      h('span', { className: 'alo-mic-label' }, label));
  }

  function SpeechBubble(p) {
    var tone = p.tone || 'say';
    return h('div', { className: cx('alo-bubble-row', p.className) },
      h('span', { className: 'alo-avatar', dangerouslySetInnerHTML: { __html: MARK } }),
      h('div', { className: cx('alo-bubble', 'alo-bubble--' + tone) },
        h('span', { className: 'alo-bubble-who' }, p.speaker || 'Auntie Kemi'),
        h('div', { className: tone === 'call' ? 'alo-bubble-call' : 'alo-bubble-text' }, p.children)));
  }

  function ReadingPanel(p) {
    var level = p.level || 'p3';
    var sentences = Array.isArray(p.text) ? p.text : [p.text];
    return h('article', { className: cx('alo-reading', p.className), lang: p.lang || 'en-NG' },
      p.title ? h('h2', { className: 'alo-reading-title display-m' }, p.title) : null,
      h('p', { className: cx('alo-reading-text', 'reading-' + level) }, sentences.join(' ')));
  }

  function MoonProgress(p) {
    var steps = p.steps || ['Chat', 'Read', 'Tell', 'Questions', 'Listen'];
    var current = p.current == null ? 0 : p.current;
    return h('ol', { className: cx('alo-moons', p.className), 'aria-label': 'Session progress' },
      steps.map(function (s, i) {
        var st = i < current ? 'done' : i === current ? 'now' : 'next';
        return h('li', { key: s, className: 'alo-moon alo-moon--' + st, 'aria-current': st === 'now' ? 'step' : undefined },
          h('span', { className: 'alo-moon-disc' }, st === 'done' ? glyph('check') : null),
          h('span', { className: 'alo-moon-label' }, s),
          h('span', { className: 'alo-sr' }, st === 'done' ? ' (done)' : st === 'now' ? ' (now)' : ''));
      }));
  }

  var BADGES = {
    brave: { icon: 'star', title: 'Brave reader', note: 'Kept going after a tricky word' },
    teller: { icon: 'book', title: 'Great teller', note: 'Told a story back' },
    collector: { icon: 'lantern', title: 'Story collector', note: 'Read about 5 different things' },
    listener: { icon: 'ear', title: 'Good listener', note: 'Finished a listening story' }
  };
  function RewardBadge(p) {
    var b = BADGES[p.kind || 'brave'];
    var earned = p.earned !== false;
    return h('figure', { className: cx('alo-badge', earned ? 'alo-badge--earned' : 'alo-badge--locked', p.className) },
      h('span', { className: 'alo-badge-medal' }, glyph(b.icon)),
      h('figcaption', null, h('strong', null, b.title), h('span', null, earned ? b.note : 'Keep reading to unlock')));
  }

  function LanternStreak(p) {
    var weeks = p.weeks || [true, true, false, true, true, true];
    var run = 0; for (var i = weeks.length - 1; i >= 0 && weeks[i]; i--) run++;
    return h('div', { className: cx('alo-streak', p.className) },
      h('div', { className: 'alo-lanterns', role: 'list' }, weeks.map(function (lit, i) {
        return h('span', { key: i, role: 'listitem', className: 'alo-lantern ' + (lit ? 'alo-lantern--lit' : 'alo-lantern--rest'),
          'aria-label': 'Week ' + (i + 1) + (lit ? ': read' : ': resting') }, glyph('lantern'));
      })),
      h('p', { className: 'alo-streak-text' }, run > 0 ? run + ' story ' + (run === 1 ? 'week' : 'weeks') + ' in a row' : 'Your lanterns are resting. Light one this week!'));
  }

  function Japa(p) {
    var pose = p.pose || 'happy';
    var key = pose === 'listening' ? 'listen' : pose === 'thinking' ? 'think' : pose;
    return h('span', { className: cx('alo-japa', p.className), style: p.size ? { width: p.size } : undefined,
      dangerouslySetInnerHTML: { __html: JAPA[key] || JAPA.happy } });
  }

  function ParentReportCard(p) {
    return h('section', { className: cx('alo-report', p.className) },
      h('header', { className: 'alo-report-head' },
        h('h3', { className: 'title' }, p.title || "Chidi's reading"),
        h('span', { className: 'caption alo-muted' }, p.date || 'Short check · 14 Oct')),
      p.summary ? h('p', { className: 'body' }, p.summary) : null,
      h('dl', { className: 'alo-report-stats' }, (p.stats || []).map(function (s) {
        return h('div', { key: s.label, className: 'alo-report-stat' }, h('dt', { className: 'label' }, s.label), h('dd', null, s.value));
      })),
      p.workingOn ? h('p', { className: 'alo-report-focus body' }, h('span', { className: 'label' }, 'Working on'), ' ', p.workingOn) : null,
      p.tip ? h('p', { className: 'alo-report-tip body' }, h('strong', null, 'Try this week: '), p.tip) : null,
      p.action ? h(Button, { variant: 'primary', size: 'grown', onClick: p.onAction }, p.action) : null);
  }

  var PROFILES = {
    ON_TRACK: ['On track', 'leaf', 'check'],
    UNDERSTANDS_BUILDING_WORD_READING: ['Understands, building word reading', 'sky', 'book'],
    DECODING_LIMITED: ['Understands when listening; words are the barrier', 'sky', 'book'],
    FLUENT_NEEDS_LANGUAGE_SUPPORT: ['Reads fluently, needs help understanding', 'coral', 'ear'],
    NEEDS_SUPPORT_IN_BOTH: ['Needs support in both', 'night', 'star'],
    COMPREHENSION_STRATEGY_GAP: ['Understands listening, not yet reading', 'moon', 'lantern'],
    INSUFFICIENT_EVIDENCE: ['Check again', 'none', 'replay']
  };
  function ProfilePill(p) {
    var d = PROFILES[p.profile] || PROFILES.INSUFFICIENT_EVIDENCE;
    return h('span', { className: cx('alo-pill', 'alo-pill--' + d[1], p.className) }, glyph(d[2]), h('span', null, p.label || d[0]),
      p.provisional ? h('span', { className: 'alo-pill-prov' }, 'provisional') : null);
  }

  // Round play / next button. `label` is required: the glyph is not enough for a screen reader.
  function RoundButton(p) {
    var icon = p.kind === 'play' ? 'play' : 'next';
    return h('button', Object.assign({ type: 'button' }, omit(p, ['kind', 'label', 'className']), { className: cx('alo-round', p.className), 'aria-label': p.label }), glyph(icon));
  }
  // A light card that may sit inside a night screen: it carries its own light token scope.
  function Paper(p) {
    return h(p.as || 'div', Object.assign({}, omit(p, ['as', 'className', 'children']), { 'data-theme': 'light', className: cx('alo-paper', p.className) }), p.children);
  }
  function Eyebrow(p) {
    return h(p.as || 'span', Object.assign({}, omit(p, ['as', 'className', 'children']), { className: cx('alo-eyebrow', p.className) }), p.children);
  }
  // Label + text input, or a select when `options` is given. `hint` is linked with aria-describedby.
  function Field(p) {
    var hintId = p.hint ? p.id + '-hint' : undefined;
    var control = p.options
      ? h('select', Object.assign({}, omit(p, ['label', 'hint', 'options', 'className', 'children']), { className: 'alo-field-control', 'aria-describedby': hintId }),
          p.options.map(function (o) { return h('option', { key: o.value, value: o.value }, o.label); }))
      : h('input', Object.assign({ type: 'text' }, omit(p, ['label', 'hint', 'options', 'className', 'children']), { className: 'alo-field-control', 'aria-describedby': hintId }));
    return h('div', { className: cx('alo-field', p.className) }, h('label', { htmlFor: p.id, className: 'alo-eyebrow' }, p.label), control,
      p.hint ? h('span', { id: hintId, className: 'alo-field-hint' }, p.hint) : null);
  }
  // One choice from a few, as aria-pressed buttons (P1 to P6, for example).
  function ToggleGroup(p) {
    var labelId = p.id + '-label';
    return h('div', { className: cx('alo-toggle-group', p.className) }, h('span', { id: labelId, className: 'alo-eyebrow' }, p.label),
      h('div', { role: 'group', 'aria-labelledby': labelId, className: 'alo-toggle-options', style: { '--alo-toggle-cols': p.options.length } },
        p.options.map(function (o) {
          return h('button', { key: o.value, type: 'button', className: 'alo-toggle', 'aria-pressed': String(o.value === p.value), onClick: function () { if (p.onChange) p.onChange(o.value); } }, o.label);
        })));
  }
  // A calm status line for grown-up screens. Never red: use `notice` or `info`.
  function Banner(p) {
    var tone = p.tone || 'info';
    return h('div', { role: 'status', className: cx('alo-banner', 'alo-banner--' + tone, p.className) }, glyph(tone === 'good' ? 'good' : 'info'), h('span', null, p.children));
  }

  window.Alo = { Button: Button, MicButton: MicButton, SpeechBubble: SpeechBubble, ReadingPanel: ReadingPanel,
    MoonProgress: MoonProgress, RewardBadge: RewardBadge, LanternStreak: LanternStreak, Japa: Japa,
    ParentReportCard: ParentReportCard, ProfilePill: ProfilePill,
    RoundButton: RoundButton, Paper: Paper, Eyebrow: Eyebrow, Field: Field, ToggleGroup: ToggleGroup, Banner: Banner };
})();
