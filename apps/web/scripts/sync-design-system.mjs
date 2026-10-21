// Sync the design system into the web app, verbatim, and generate tokens.css.
//
// W1's consumption decision (see src/design-system/README.md):
// `docs/Alo.ai_Design_System/` stays the source of truth and is never edited
// or forked here. This script is the ONE place the app consumes it:
//   - components/bundle.js, bundle.css, index.d.ts -> src/design-system/vendor/
//   - tokens.json -> src/design-system/vendor/tokens.css (generated CSS vars)
//   - assets/ (logos, Japa, icons, pattern) -> public/design-system/assets/
// Everything it writes is generated and git-ignored; run via npm scripts
// (dev / build / test) so a fresh checkout always matches the source system.
import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const dsRoot = resolve(webRoot, '../../docs/Alo.ai_Design_System');
const vendorDir = resolve(webRoot, 'src/design-system/vendor');
const publicAssetsDir = resolve(webRoot, 'public/design-system/assets');

const alias = (value) =>
  typeof value === 'string' && /^\{(.+)\}$/.test(value)
    ? `var(--${value.slice(1, -1)})`
    : value;

function themedVars(tokens) {
  const light = [];
  const dark = [];
  for (const token of tokens) {
    if (token.value && typeof token.value === 'object') {
      light.push(`  --${token.name}: ${alias(token.value.light)};`);
      dark.push(`  --${token.name}: ${alias(token.value.dark)};`);
    } else {
      light.push(`  --${token.name}: ${alias(token.value)};`);
    }
  }
  return { light, dark };
}

function generateTokensCss(tokens) {
  const color = themedVars(tokens.color.tokens);
  const shadow = themedVars(tokens.shadow.tokens);
  const flat = (list) => list.map((t) => `  --${t.name}: ${alias(t.value)};`);
  const families = Object.entries(tokens.type.families).map(
    ([name, value]) => `  --font-${name}: ${value};`,
  );
  const familyForGroup = {
    Display: 'display',
    'Kid UI': 'ui',
    Reading: 'reading',
    'Grown-up': 'ui',
  };
  const typeClasses = tokens.type.groups.flatMap((group) =>
    group.styles.map((style) => {
      const lines = [
        `  font-family: var(--font-${familyForGroup[group.name]});`,
        `  font-size: ${style.fontSize};`,
        `  line-height: ${style.lineHeight};`,
        `  font-weight: ${style.fontWeight};`,
      ];
      if (style.letterSpacing) lines.push(`  letter-spacing: ${style.letterSpacing};`);
      return `.${style.name} {\n${lines.join('\n')}\n}`;
    }),
  );

  return `/* GENERATED from docs/Alo.ai_Design_System/tokens.json by
   scripts/sync-design-system.mjs. Do not edit by hand. */
:root {
${[...color.light, ...shadow.light, ...flat(tokens.spacing.tokens),
  ...flat(tokens.radius.tokens), ...flat(tokens.size.tokens), ...families].join('\n')}
  color-scheme: light;
}
[data-theme="dark"] {
${[...color.dark, ...shadow.dark].join('\n')}
  color-scheme: dark;
}
${typeClasses.join('\n')}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
`;
}

await mkdir(vendorDir, { recursive: true });
await mkdir(publicAssetsDir, { recursive: true });

for (const file of ['bundle.js', 'bundle.css', 'index.d.ts']) {
  await cp(resolve(dsRoot, 'components', file), resolve(vendorDir, file));
}
await cp(resolve(dsRoot, 'assets'), publicAssetsDir, { recursive: true });

const tokens = JSON.parse(await readFile(resolve(dsRoot, 'tokens.json'), 'utf8'));
await writeFile(resolve(vendorDir, 'tokens.json'), `${JSON.stringify(tokens, null, 2)}\n`);
await writeFile(resolve(vendorDir, 'tokens.css'), generateTokensCss(tokens));

console.log('Design system synced from docs/Alo.ai_Design_System/');
