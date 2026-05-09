import React from 'react';
import { Box, Typography, Button, Stack, useTheme } from '@mui/material';
import InboxOutlined from '@mui/icons-material/InboxOutlined';

export interface EmptyStateAction {
  label: string;
  onClick?: () => void;
  href?: string;
  variant?: 'contained' | 'outlined' | 'text';
  startIcon?: React.ReactNode;
}

export interface EmptyStateProps {
  /** Short headline (e.g. "No model cards yet") */
  title: string;
  /** One- or two-line explanation of what this page is for */
  description?: string;
  /** Optional secondary line: how data normally arrives here */
  ingestHint?: string;
  /** Big icon at the top — defaults to inbox if omitted */
  icon?: React.ReactNode;
  /** Primary CTA — typically the natural "create" action */
  primaryAction?: EmptyStateAction;
  /** Secondary CTA — typically a docs link or alternative path */
  secondaryAction?: EmptyStateAction;
  /** Compact mode — smaller padding/icon for inline empty states */
  compact?: boolean;
  /** Optional override for the wrapper sx prop */
  sx?: object;
}

/**
 * Reusable empty-state placeholder for list/dashboard pages with no data yet.
 *
 * Distinguishes between the THREE common cases:
 *   1. AUTO_INGEST page — explain what triggers the data to appear
 *      (e.g. "Records appear here when agents call /v1/policy/check")
 *   2. HUMAN_ENTRY page — show a "Create" CTA
 *      (e.g. "Add your first model card")
 *   3. INTEGRATION_REQUIRED page — show a docs link explaining setup
 *      (e.g. "Connect MLflow to start tracking drift")
 *
 * Usage:
 *   <EmptyState
 *     title="No bias audits yet"
 *     description="Bias audits assess fairness across demographic subgroups."
 *     ingestHint="Audits run automatically on published model cards once a test dataset is attached."
 *     primaryAction={{ label: 'View model cards', href: '/clinical/model-cards' }}
 *     secondaryAction={{ label: 'Read docs', href: '/docs/bias-audits' }}
 *   />
 */
const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  ingestHint,
  icon,
  primaryAction,
  secondaryAction,
  compact = false,
  sx,
}) => {
  const theme = useTheme();
  const dark = theme.palette.mode === 'dark';

  const renderAction = (action: EmptyStateAction, isPrimary: boolean) => {
    const variant = action.variant ?? (isPrimary ? 'contained' : 'outlined');
    if (action.href && !action.onClick) {
      return (
        <Button
          key={action.label}
          variant={variant}
          href={action.href}
          startIcon={action.startIcon}
          size="small"
        >
          {action.label}
        </Button>
      );
    }
    return (
      <Button
        key={action.label}
        variant={variant}
        onClick={action.onClick}
        startIcon={action.startIcon}
        size="small"
      >
        {action.label}
      </Button>
    );
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        py: compact ? 4 : { xs: 5, md: 8 },
        px: { xs: 2, sm: 3 },
        bgcolor: 'background.paper',
        border: `1px dashed ${theme.palette.divider}`,
        borderRadius: 2,
        ...sx,
      }}
    >
      <Box
        sx={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: compact ? 44 : 56,
          height: compact ? 44 : 56,
          borderRadius: '50%',
          bgcolor: dark ? 'rgba(99,91,255,0.10)' : 'rgba(99,91,255,0.07)',
          color: 'primary.main',
          mb: 2,
          '& svg': { fontSize: compact ? 22 : 28 },
        }}
      >
        {icon ?? <InboxOutlined />}
      </Box>

      <Typography
        variant="h6"
        sx={{ fontWeight: 600, fontSize: compact ? '0.9375rem' : '1rem', mb: 0.5 }}
      >
        {title}
      </Typography>

      {description && (
        <Typography
          variant="body2"
          sx={{
            color: 'text.secondary',
            maxWidth: 480,
            fontSize: '0.8125rem',
            lineHeight: 1.55,
            mb: ingestHint ? 1 : 2.5,
          }}
        >
          {description}
        </Typography>
      )}

      {ingestHint && (
        <Box
          sx={{
            mt: 0.5,
            mb: 2.5,
            px: 1.5,
            py: 0.75,
            borderRadius: 1,
            bgcolor: dark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.025)',
            border: `1px solid ${theme.palette.divider}`,
            maxWidth: 520,
          }}
        >
          <Typography
            variant="caption"
            sx={{
              color: 'text.secondary',
              fontSize: '0.7rem',
              lineHeight: 1.5,
              display: 'block',
            }}
          >
            <strong style={{ color: theme.palette.text.primary }}>How it populates: </strong>
            {ingestHint}
          </Typography>
        </Box>
      )}

      {(primaryAction || secondaryAction) && (
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1.25}
          sx={{ mt: 1, width: { xs: '100%', sm: 'auto' }, maxWidth: 360 }}
        >
          {primaryAction && renderAction(primaryAction, true)}
          {secondaryAction && renderAction(secondaryAction, false)}
        </Stack>
      )}
    </Box>
  );
};

export default EmptyState;
