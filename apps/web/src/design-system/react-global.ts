import React from 'react';

// The design-system bundle (vendor/bundle.js) is a classic script that reads
// React from `window.React` and publishes components on `window.Alo`.
// It must see the app's own React instance, so this module runs first.
(window as unknown as { React: typeof React }).React = React;
