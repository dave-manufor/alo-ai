// The synced design-system bundle is a plain script with no exports;
// its component types come from vendor/index.d.ts (see alo.tsx).
declare module '*vendor/bundle.js' {
  const nothing: undefined;
  export default nothing;
}
