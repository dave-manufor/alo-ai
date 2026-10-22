Alo.ai is a voice-first reading game for Nigerian children in Primary 1–6. A child chats with **Auntie Kemi**, reads a story written about what they love, tells it back and answers a few questions, all out loud. Grown-ups get a plain report and a plan. The brand has to make that feel like play to a seven-year-old and feel trustworthy to their parents and teachers.

## The idea: àlọ́

The name comes from **àlọ́**, the Yoruba word for the folktales (àlọ́ àpagbè) and riddles (àlọ́ àpamọ̀) told in the evening, usually by an elder, with the household gathered and children at the front. A tale opens with a call and response: the teller calls **"Àlọ́ o!"** and everyone answers **"Ààlọ̀!"**

Everything in the brand comes from that evening circle:

- **Night sky and moonlight** give the palette: adire indigo (`night`) and moon gold (`moon`).
- **Adire resist-dye circles** give the pattern and the dots on Jàpá's shell.
- **The call and response** opens every session and is the brand's signature moment.
- **Ìjàpá the tortoise**, the best-known character in àlọ́ tales, gives us our mascot, **Jàpá**: his grandchild, who loves stories more than tricks.

**Tagline:** Stories that listen back.

## Two modes, one brand

| | Kid mode | Grown-up mode |
|---|---|---|
| Who | Children during sessions and rewards | Parents (reports, payments) and teachers (class view) |
| Feel | Bouncy, bright, big | Calm, clear, quick to scan |
| Type | `display-*`, `kid-*`, `reading-*` | `title`, `body`, `label`, `caption` |
| Buttons | `size="kid"`, at least `tap-kid` tall | `size="grown"`, at least `tap-grown` tall |
| Jàpá | Present and reacting | Small or absent |
| Motion | Springs and celebrations | Simple fades only |
| Colour of errors | Never red: `coral-soft` with Jàpá thinking | `alert` for system errors |

Never mix modes on one screen. The parent's report is grown-up mode even when it plays Auntie Kemi's voice.

## Voice and tone

**Auntie Kemi** is the voice of Alo.ai: a warm auntie who has told a thousand stories and is delighted by yours. Jàpá never speaks; he reacts.

**To children:**

- Short sentences, eight words or fewer. "You" and "I". Sentence case.
- Praise effort, never correctness: "You kept going!", "What a brave try!", "Thank you for telling me."
- Never say "wrong", "no", "incorrect" or "fail". Use "Let's try that one together" or simply move on.
- Never show a child a score, a timer, a percentage or a red mark.
- At most one exclamation mark per screen. No emoji in the product; use the brand icons.
- Yoruba and Pidgin greetings are welcome: "Àlọ́ o!", "Well done o!", "E ku ise!" Write Yoruba with its tone marks.

**To parents:** warm and plain. Lead with a strength, then one thing to work on, then one thing to do. Use screening words, never diagnosis words. Never use "dyslexia", "disorder", "behind", "failing", "slow learner", "hyperlexic" or "word caller" (the Reading Coach's validator enforces this list).

**To teachers:** precise and brief. Numbers with their source. Plain profile names ("Reads fluently, needs help understanding"), never codes.

| Moment | Kid mode | Grown-up mode |
|---|---|---|
| Session opens | "Àlọ́ o!" (child answers "Ààlọ̀!") | — |
| Child is stuck | "That word is *chased*. Keep going!" | — |
| Wrong answer | "Thank you! Let's go to the next one." | "Found 'why' questions hard." |
| Session ends | "You did a great job today!" | "Chidi's report is ready." |
| Connection lost | "Hold on, I'm still listening." | "Connection lost. Recording is saved on this phone." |

## Colour

Colours are semantic tokens with a **Day** (light) and **Night** (dark) theme. The first theme is the fallback.

- `night` is the brand. Use it for primary actions, the mic button and selected states. Text on a `night` fill is `on-night`.
- `moon` means **reward**. Stars, lit lanterns, earned badges and the "continue" button after a story. Never use it for warnings.
- `coral` is energy and the call. The "Àlọ́ o!" bubble, secondary game buttons, and gentle "try again" states in `coral-soft`.
- `leaf` means done and success. `sky` means listening and information.
- Text on `moon`, `coral`, `leaf` and `sky` is always `on-bright`, never white.
- Kid mode never shows red. `alert` is for grown-up system errors only.
- Never tell states apart by colour alone: profile pills, steps and badges each carry a word and a shape too.
- Every text token's note names the grounds it's legible on. All of them meet 4.5:1 in both themes; `line-strong`, `focus-ring` and icons meet 3:1.

## Typography

Three Google families, each with one job:

- **Fredoka** (`--font-display`): rounded and joyful. Titles and celebrations only: `display-xl`, `display-l`, `display-m`.
- **Nunito** (`--font-ui`): rounded and legible at small sizes. All interface text: `kid-*` in kid mode; `title`, `body`, `label` and `caption` in grown-up mode.
- **Andika** (`--font-reading`): made by SIL for beginning readers, with single-storey *a* and *g* and clearly different *I*, *l* and *1*. **Every story a child reads is set in Andika**: `reading-p1` (ARL 1–2), `reading-p3` (ARL 3–6), `reading-p5` (ARL 7–12), at most `measure-reading` wide.
- **Set Yoruba with tone marks in Andika** (àlọ́, Ìjàpá, Ààlọ̀), whatever the surrounding text. Fredoka and Nunito may lack ọ, ẹ and ṣ with tone marks; test before using them for Yoruba.
- Never italicise story text, never justify it, and never animate it.

## Shape, space and depth

- Spacing runs on 4px: `space-1` to `space-8`. Kid cards pad `space-5`; grown-up cards pad `space-4`.
- Everything is round. Kid buttons and bubbles use `radius-l`, grown-up ones `radius-m`, pills and the mic `radius-pill`.
- Depth is a solid **press edge**, not a blur. A button sits on its own darker edge (`press-night`, `press-moon`, `press-coral`, `press-leaf`, `press-neutral`) and drops 4px onto it when tapped. Cards sit on `lift`.
- Anything a child taps is at least `tap-kid` (64px) tall. Grown-up controls are at least `tap-grown` (44px).

## The game layer: the story circle

Alo.ai rewards **taking part**, never being right. Scores belong to grown-ups.

- **Stars:** up to three per session, one each for reading, telling the story back and answering. A child who tries earns all three.
- **Lanterns:** one lantern per week with at least one session (`LanternStreak`). A missed week **rests** the lantern; it never goes out, and the streak never resets to zero with a sad face. Weekly, not daily, so no child is pushed to play every day.
- **Badges:** milestones for effort and curiosity (`RewardBadge`): *Brave reader* (kept going after a told word), *Great teller* (told a story back), *Story collector* (read about 5 different topics), *Good listener* (finished a listening story).
- **Story path:** new stories unlock as a journey through a village (market, river, farm, school). Children see places, never level numbers.
- **Celebrations:** Jàpá cheers, stars burst in `moon`, and the call "Àlọ́ o!" plays on a talking-drum sound.

**Never:** leaderboards, timers, lives or hearts that run out, "you'll lose your streak" warnings, paid boosts, or ads.

## Jàpá, the mascot

Four poses (assets in **Mascot**; the `Japa` component):

- `happy`: default, on start screens.
- `listening`: while the child speaks (with `sky` sound waves).
- `thinking`: when a child is stuck or an answer missed. Never sad.
- `cheer`: rewards and the end of a session.

Rules: Jàpá never mocks, frowns, cries or looks disappointed. He never appears on grown-up report data. Keep him at `mascot-m` or larger on kid screens, never cropped, never recoloured, and give him clear space of half his height.

## Motion and sound

- **Kid mode:** springy and short. Buttons drop onto their edge in 120ms. Screens slide in over 250ms with a slight overshoot. Celebrations last at most 1.2s.
- **Grown-up mode:** fades of 150ms; nothing bounces.
- **Respect `prefers-reduced-motion`:** swap every movement for a fade.
- **Sound:** a talking-drum (gángan) hit for "Àlọ́ o!", a soft chime for each star, and a gentle wood-block for "your turn". Sounds are short, never punish, and can be muted by a grown-up.

## Iconography

Rounded 2.5px strokes on a 24px grid, `ink` outlines with one fill colour from the palette (duotone). The set is in **Icons**: `mic`, `replay` ("say it again"), `star`, `lantern`, `book` and `check`. Components draw single-colour versions in `currentColor`. No emoji anywhere in the product.

## Logo

- The wordmark is **alo.ai** in rounded geometric letters. The **o** carries a coral dot beneath it, the dot of the Yoruba **ọ** in àlọ́.
- Use `wordmark-on-light.svg` on `surface` and `surface-raised`, and `wordmark-on-dark.svg` on `night` or the dark theme.
- The **mark** is that ọ alone: an indigo ring with its coral dot. It's used for Auntie Kemi's avatar in speech bubbles and for small spaces. The **app icon** puts the ring in `moon` on a `night` tile.
- Clear space is the height of the dot ring's centre gap on every side. Minimum widths: wordmark 80px, mark 24px.
- Never stretch, recolour, outline or add effects to the logo, or set "alo.ai" in another typeface as a logo.

## Pattern

`adire-circles.svg` is a tile inspired by adire resist-dye circles: rings with gold centres and small dotted crosses on `night`. Use it on celebration backgrounds, empty states and marketing. Never behind story text or report data.

## Accessibility

- All text meets 4.5:1 contrast, and large text, icons and control borders meet 3:1, in both themes.
- Keyboard focus is a solid 3px `focus-ring` with a 3px offset.
- Everything Auntie Kemi says is available as text to assistive technology, in a visually hidden `aria-live="polite"` region, so a grown-up using a screen reader can follow along. The child's screen shows no subtitles: the only words on it are the call ("Àlọ́ o!"), the story and the hand-back to a grown-up. (Changed from "also appears in the speech bubble", following the "Àlọ́ Night Session V" design.)
- Children never need to read an instruction to use the product: every step is spoken, and every button has an icon and a word.
