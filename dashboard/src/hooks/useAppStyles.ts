import { useTheme } from '@mui/material';

export function useAppStyles() {
  const theme = useTheme();
  const dark = theme.palette.mode === 'dark';

  return {
    dark,
    theme,
    border: theme.palette.divider,
    hoverBg: dark ? 'rgba(255,255,255,0.035)' : 'rgba(0,0,0,0.025)',
    surfaceBg: dark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.012)',
    inputBg: dark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
    accent: theme.palette.primary.main,
    mono: '"JetBrains Mono", ui-monospace, monospace' as const,
    chartGrid: dark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.06)',
    chartAxis: dark ? '#64748b' : '#94a3b8',
    chartTooltip: {
      contentStyle: {
        backgroundColor: dark ? '#1c1c20' : '#ffffff',
        border: `1px solid ${theme.palette.divider}`,
        borderRadius: 8,
        fontSize: '0.8rem',
        color: theme.palette.text.primary,
        boxShadow: dark ? '0 4px 16px rgba(0,0,0,0.5)' : '0 4px 16px rgba(0,0,0,0.1)',
      },
      labelStyle: { color: theme.palette.text.secondary },
    },
    codeBg: dark ? '#050507' : '#f4f4f5',
    dialogBg: dark ? '#151518' : '#ffffff',
  };
}
