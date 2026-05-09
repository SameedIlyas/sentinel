/**
 * Public surface of the walkthrough package.
 *
 * Mount `<WalkthroughProvider>` somewhere inside your <Router> (so it can
 * navigate between pages), then render `<WalkthroughOverlay>` at the layout
 * root. Use `useWalkthrough()` from any component (e.g. the user menu) to
 * trigger `restart()` on demand.
 */
export { WalkthroughProvider, useWalkthrough } from './WalkthroughContext';
export { WalkthroughOverlay } from './WalkthroughOverlay';
export type { WalkthroughStep, WalkthroughContextValue } from './types';
export { STEPS, TOUR_VERSION } from './steps';
