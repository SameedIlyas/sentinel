/**
 * First-run walkthrough — type definitions.
 *
 * One step describes:
 *   - what page to be on (`path`)
 *   - what UI element to spotlight (`target` — CSS selector, or null for a centred modal)
 *   - what to say (`title`, `body`)
 *   - what to ask the user to do next (`action`, `actionHint`)
 *
 * Steps are processed sequentially. The walkthrough engine handles route
 * navigation, scroll-into-view, target measurement, and advance-on-action.
 */

export type StepPlacement = 'top' | 'bottom' | 'left' | 'right' | 'center';

export type StepAction =
  | 'next'        // user clicks Next to advance
  | 'click'       // user must click the spotlit element to advance
  | 'navigate';   // wait for a route change before advancing

export interface WalkthroughStep {
  id: string;
  title: string;
  body: string;
  /** CSS selector or `null` for a centred modal (used for welcome / wrap-up). */
  target: string | null;
  /** Route to navigate to before showing this step. */
  path?: string;
  /** Tooltip placement relative to the target. */
  placement?: StepPlacement;
  /** What ends this step. Defaults to 'next'. */
  action?: StepAction;
  /** Friendly call-to-action shown beside the Next button (e.g. "Click the icon to expand"). */
  actionHint?: string;
  /** Optional: a hex/MUI palette key to colour the spotlight border for accent. */
  accent?: 'primary' | 'success' | 'warning' | 'info';
  /** When true, the user can't advance until they actually perform the action. */
  blocking?: boolean;
}

export interface WalkthroughContextValue {
  /** True while the tour is active and visible. */
  isActive: boolean;
  /** True when the user has finished or skipped the tour previously. */
  hasCompleted: boolean;
  /** Current step index, or -1 when inactive. */
  currentIndex: number;
  /** Full list of steps in the active tour. */
  steps: WalkthroughStep[];

  start: () => void;
  next: () => void;
  back: () => void;
  skip: () => void;
  finish: () => void;
  /** Force-restart the tour from the user menu. */
  restart: () => void;
}
