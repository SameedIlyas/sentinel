/**
 * Walkthrough overlay — the visible part of the tour.
 *
 * Renders three layers, top to bottom:
 *   1. A full-screen dimmed backdrop with a hole punched out around the
 *      target element (the "spotlight").
 *   2. A glowing border around the target so it stands out even on cards
 *      that already have shadows.
 *   3. A floating tooltip with title, body, progress, and Next/Back/Skip.
 *
 * Centred steps (target=null) skip the spotlight and render the tooltip
 * as a centred modal — used for the welcome and wrap-up.
 *
 * The component re-measures the target on resize, scroll, and route
 * change. If the target hasn't rendered yet (e.g. nav still loading), we
 * fall back to a centred modal until it appears.
 */
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Box, Button, IconButton, LinearProgress, Stack, Typography, useTheme } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import CheckIcon from '@mui/icons-material/Check';

import { useWalkthrough } from './WalkthroughContext';
import type { StepPlacement, WalkthroughStep } from './types';

const TOOLTIP_WIDTH = 360;
const TOOLTIP_GAP = 16;        // px gap between target and tooltip
const SPOTLIGHT_PADDING = 8;   // px padding around the target rect

interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

function readRect(selector: string | null): Rect | null {
  if (!selector) return null;
  const el = document.querySelector(selector) as HTMLElement | null;
  if (!el) return null;
  const r = el.getBoundingClientRect();
  if (r.width === 0 && r.height === 0) return null;
  return { top: r.top, left: r.left, width: r.width, height: r.height };
}

/**
 * Compute tooltip top/left in viewport coordinates given the target rect
 * and the desired placement. Falls back to whatever fits on the screen.
 */
function computeTooltipPosition(
  rect: Rect | null,
  placement: StepPlacement,
  tooltipHeight: number,
  viewportWidth: number,
  viewportHeight: number,
): { top: number; left: number; effectivePlacement: StepPlacement } {
  // Centred placement (no target) — middle of viewport
  if (!rect || placement === 'center') {
    return {
      top: Math.max(24, (viewportHeight - tooltipHeight) / 2),
      left: Math.max(24, (viewportWidth - TOOLTIP_WIDTH) / 2),
      effectivePlacement: 'center',
    };
  }

  const tryPlacement = (p: StepPlacement) => {
    let top = 0;
    let left = 0;
    switch (p) {
      case 'top':
        top = rect.top - tooltipHeight - TOOLTIP_GAP;
        left = rect.left + rect.width / 2 - TOOLTIP_WIDTH / 2;
        break;
      case 'bottom':
        top = rect.top + rect.height + TOOLTIP_GAP;
        left = rect.left + rect.width / 2 - TOOLTIP_WIDTH / 2;
        break;
      case 'left':
        top = rect.top + rect.height / 2 - tooltipHeight / 2;
        left = rect.left - TOOLTIP_WIDTH - TOOLTIP_GAP;
        break;
      case 'right':
        top = rect.top + rect.height / 2 - tooltipHeight / 2;
        left = rect.left + rect.width + TOOLTIP_GAP;
        break;
      default:
        return null;
    }
    const fits =
      top >= 16 &&
      left >= 16 &&
      top + tooltipHeight <= viewportHeight - 16 &&
      left + TOOLTIP_WIDTH <= viewportWidth - 16;
    return fits ? { top, left, effectivePlacement: p } : null;
  };

  // Try the requested placement first, then fall back to alternatives
  const order: StepPlacement[] = [
    placement,
    'right',
    'bottom',
    'left',
    'top',
  ];
  for (const p of order) {
    const result = tryPlacement(p);
    if (result) return result;
  }

  // Final fallback: clamp to the viewport
  return {
    top: Math.min(viewportHeight - tooltipHeight - 16, Math.max(16, rect.top)),
    left: Math.min(viewportWidth - TOOLTIP_WIDTH - 16, Math.max(16, rect.left + rect.width + TOOLTIP_GAP)),
    effectivePlacement: placement,
  };
}

/** SVG mask spotlight — a dim rectangle covering the viewport with a hole at the target. */
function Spotlight({ rect }: { rect: Rect | null }) {
  if (!rect) return null;
  const padded = {
    top: Math.max(0, rect.top - SPOTLIGHT_PADDING),
    left: Math.max(0, rect.left - SPOTLIGHT_PADDING),
    width: rect.width + SPOTLIGHT_PADDING * 2,
    height: rect.height + SPOTLIGHT_PADDING * 2,
  };
  return (
    <svg
      width="100%"
      height="100%"
      style={{
        position: 'fixed',
        inset: 0,
        pointerEvents: 'none',
      }}
    >
      <defs>
        <mask id="walkthrough-spotlight-mask">
          <rect width="100%" height="100%" fill="white" />
          <rect
            x={padded.left}
            y={padded.top}
            width={padded.width}
            height={padded.height}
            rx={10}
            ry={10}
            fill="black"
          />
        </mask>
      </defs>
      <rect
        width="100%"
        height="100%"
        fill="rgba(0, 0, 0, 0.6)"
        mask="url(#walkthrough-spotlight-mask)"
      />
    </svg>
  );
}

/** A glowing border around the target so it stands out against the dim. */
function SpotlightBorder({ rect, accentColor }: { rect: Rect | null; accentColor: string }) {
  if (!rect) return null;
  return (
    <Box
      role="presentation"
      sx={{
        position: 'fixed',
        top: rect.top - SPOTLIGHT_PADDING,
        left: rect.left - SPOTLIGHT_PADDING,
        width: rect.width + SPOTLIGHT_PADDING * 2,
        height: rect.height + SPOTLIGHT_PADDING * 2,
        borderRadius: '10px',
        boxShadow: `0 0 0 2px ${accentColor}, 0 0 20px ${accentColor}80`,
        pointerEvents: 'none',
        animation: 'walkthrough-pulse 2s ease-in-out infinite',
        '@keyframes walkthrough-pulse': {
          '0%, 100%': { boxShadow: `0 0 0 2px ${accentColor}, 0 0 20px ${accentColor}40` },
          '50%':      { boxShadow: `0 0 0 2px ${accentColor}, 0 0 28px ${accentColor}90` },
        },
      }}
    />
  );
}

interface TooltipProps {
  step: WalkthroughStep;
  rect: Rect | null;
  index: number;
  total: number;
  onNext: () => void;
  onBack: () => void;
  onSkip: () => void;
  onFinish: () => void;
}

function Tooltip({ step, rect, index, total, onNext, onBack, onSkip, onFinish }: TooltipProps) {
  const theme = useTheme();
  const accent =
    step.accent === 'success' ? theme.palette.success.main :
    step.accent === 'warning' ? theme.palette.warning.main :
    step.accent === 'info'    ? theme.palette.info.main :
                                theme.palette.primary.main;
  const isLast = index === total - 1;
  const isFirst = index === 0;
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number; effectivePlacement: StepPlacement }>({
    top: 0,
    left: 0,
    effectivePlacement: step.placement ?? 'center',
  });

  // Re-measure on every render — cheap enough for one element.
  useLayoutEffect(() => {
    const tooltipHeight = ref.current?.getBoundingClientRect().height ?? 220;
    const placement = step.placement ?? (rect ? 'right' : 'center');
    setPos(computeTooltipPosition(
      rect,
      placement,
      tooltipHeight,
      window.innerWidth,
      window.innerHeight,
    ));
  }, [rect, step.placement, step.id]);

  return (
    <Box
      ref={ref}
      role="dialog"
      aria-modal="true"
      aria-labelledby="walkthrough-title"
      aria-describedby="walkthrough-body"
      sx={{
        position: 'fixed',
        top: pos.top,
        left: pos.left,
        width: TOOLTIP_WIDTH,
        bgcolor: 'background.paper',
        border: `1px solid ${theme.palette.divider}`,
        borderTop: `3px solid ${accent}`,
        borderRadius: 2,
        boxShadow: theme.shadows[24],
        p: 2.5,
        zIndex: 10001,
        display: 'flex',
        flexDirection: 'column',
        gap: 1.5,
        outline: 'none',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
        <Box sx={{ flex: 1 }}>
          <Typography
            sx={{
              fontSize: '0.6875rem',
              fontWeight: 700,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: accent,
            }}
          >
            Step {index + 1} of {total}
          </Typography>
          <Typography
            id="walkthrough-title"
            variant="h5"
            sx={{ fontWeight: 700, mt: 0.25, color: 'text.primary' }}
          >
            {step.title}
          </Typography>
        </Box>
        <IconButton
          onClick={onSkip}
          size="small"
          aria-label="Skip walkthrough"
          sx={{ color: 'text.secondary', mt: -0.5, mr: -0.5 }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      <Typography
        id="walkthrough-body"
        sx={{ color: 'text.secondary', fontSize: '0.875rem', lineHeight: 1.55 }}
      >
        {step.body}
      </Typography>

      {step.actionHint && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            px: 1.5,
            py: 1,
            bgcolor: theme.palette.mode === 'dark' ? 'rgba(99,91,255,0.08)' : 'rgba(99,91,255,0.05)',
            border: `1px dashed ${accent}80`,
            borderRadius: 1,
          }}
        >
          <Typography sx={{ fontSize: '0.75rem', color: accent, fontWeight: 500 }}>
            👉 {step.actionHint}
          </Typography>
        </Box>
      )}

      <LinearProgress
        variant="determinate"
        value={((index + 1) / total) * 100}
        sx={{
          height: 4,
          borderRadius: 2,
          bgcolor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
          '& .MuiLinearProgress-bar': { bgcolor: accent },
        }}
      />

      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mt: 0.5 }}>
        <Button
          size="small"
          onClick={onSkip}
          sx={{ color: 'text.secondary', fontSize: '0.75rem' }}
        >
          Skip tour
        </Button>
        <Box sx={{ flex: 1 }} />
        <Button
          size="small"
          onClick={onBack}
          disabled={isFirst}
          startIcon={<ArrowBackIcon sx={{ fontSize: 14 }} />}
          sx={{ color: 'text.secondary', fontSize: '0.75rem' }}
        >
          Back
        </Button>
        {isLast ? (
          <Button
            variant="contained"
            size="small"
            onClick={onFinish}
            startIcon={<CheckIcon sx={{ fontSize: 16 }} />}
            sx={{ bgcolor: accent, '&:hover': { bgcolor: accent }, fontSize: '0.75rem' }}
          >
            Finish
          </Button>
        ) : (
          <Button
            variant="contained"
            size="small"
            onClick={onNext}
            endIcon={<ArrowForwardIcon sx={{ fontSize: 16 }} />}
            sx={{ bgcolor: accent, '&:hover': { bgcolor: accent }, fontSize: '0.75rem' }}
          >
            Next
          </Button>
        )}
      </Stack>
    </Box>
  );
}

export function WalkthroughOverlay() {
  const { isActive, currentIndex, steps, next, back, skip, finish } = useWalkthrough();
  const step = isActive ? steps[currentIndex] : null;
  const [rect, setRect] = useState<Rect | null>(null);

  // Re-measure target on resize / scroll / step change. Poll briefly while
  // the new page mounts (the nav item we want to spotlight may not exist yet).
  const measure = useCallback(() => {
    if (!step) return;
    const next = readRect(step.target);
    setRect(next);
  }, [step]);

  useEffect(() => {
    if (!step) {
      setRect(null);
      return;
    }
    setRect(readRect(step.target));

    // Poll while target may still be mounting.
    let attempts = 0;
    const interval = window.setInterval(() => {
      attempts += 1;
      const r = readRect(step.target);
      if (r || attempts > 12) {
        if (r) setRect(r);
        window.clearInterval(interval);
      }
    }, 120);

    const onResize = () => measure();
    const onScroll = () => measure();
    window.addEventListener('resize', onResize);
    window.addEventListener('scroll', onScroll, true);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener('resize', onResize);
      window.removeEventListener('scroll', onScroll, true);
    };
  }, [step, measure]);

  // Ensure spotlit element is on screen
  useEffect(() => {
    if (!step?.target) return;
    const el = document.querySelector(step.target) as HTMLElement | null;
    if (el && typeof el.scrollIntoView === 'function') {
      try {
        el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
      } catch {
        // ignore — older browsers
      }
    }
  }, [step]);

  // Keyboard nav: arrow keys + escape
  useEffect(() => {
    if (!isActive) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        skip();
      } else if (e.key === 'ArrowRight' || e.key === 'Enter') {
        next();
      } else if (e.key === 'ArrowLeft') {
        back();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isActive, next, back, skip]);

  if (!isActive || !step) return null;

  const theme = (() => {
    if (step.accent === 'success') return '#0ea371';
    if (step.accent === 'warning') return '#e87f17';
    if (step.accent === 'info')    return '#3b82f6';
    return '#635bff';
  })();

  return (
    <Box
      sx={{
        position: 'fixed',
        inset: 0,
        zIndex: 10000,
        // The backdrop is non-interactive; the tooltip + close button are
        // the only ways to dismiss / advance. This stops accidental clicks
        // through to the underlying app from advancing things.
        pointerEvents: rect ? 'auto' : 'auto',
      }}
      // Click on the dim backdrop = advance (matches game-tutorial UX), but
      // never on the spotlit element (we let those clicks fall through).
      onClick={(e) => {
        if (e.target === e.currentTarget) next();
      }}
    >
      {/* Layer 1: dim backdrop with hole. For centred steps (no target),
          we render a uniform translucent backdrop. */}
      {rect ? (
        <Spotlight rect={rect} />
      ) : (
        <Box
          sx={{
            position: 'fixed',
            inset: 0,
            bgcolor: 'rgba(0, 0, 0, 0.6)',
          }}
        />
      )}

      {/* Layer 2: glowing border around target */}
      <SpotlightBorder rect={rect} accentColor={theme} />

      {/* Layer 3: tooltip with controls */}
      <Tooltip
        step={step}
        rect={rect}
        index={currentIndex}
        total={steps.length}
        onNext={next}
        onBack={back}
        onSkip={skip}
        onFinish={finish}
      />
    </Box>
  );
}
