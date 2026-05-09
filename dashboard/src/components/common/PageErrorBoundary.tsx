/**
 * PageErrorBoundary
 *
 * Wraps the routed page area so a single crash (broken API contract,
 * undefined access, etc.) doesn't take down the surrounding shell —
 * the sidebar, top bar, walkthrough overlay all keep working. The user
 * can navigate to a different page via the sidebar instead of facing a
 * white screen.
 *
 * Resets the error when the URL changes (the user navigated away).
 */
import { Component, type ReactNode } from 'react';
import { Alert, AlertTitle, Box, Button, Stack, Typography } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import HomeIcon from '@mui/icons-material/Home';

interface Props {
  children: ReactNode;
  /** Reset key — when this changes, the boundary clears its error. Pass the URL
   *  pathname so navigating away from a broken page recovers automatically. */
  resetKey: string;
}

interface State {
  error: Error | null;
}

export default class PageErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidUpdate(prev: Props) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    // eslint-disable-next-line no-console
    console.error('Page crashed:', error, info);
  }

  handleReload = () => window.location.reload();
  handleGoHome = () => {
    this.setState({ error: null });
    window.location.assign('/');
  };

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <Box sx={{ maxWidth: 720, mx: 'auto', py: 4 }}>
        <Alert
          severity="error"
          variant="outlined"
          sx={{ alignItems: 'flex-start', '& .MuiAlert-message': { width: '100%' } }}
        >
          <AlertTitle sx={{ fontWeight: 700 }}>This page hit an error</AlertTitle>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1.5 }}>
            Something on this page didn't render correctly. The rest of the app
            is still working — use the sidebar to navigate elsewhere, or try
            reloading.
          </Typography>
          <Box
            component="pre"
            sx={{
              p: 1.5,
              bgcolor: 'action.hover',
              borderRadius: 1,
              fontSize: '0.75rem',
              fontFamily: 'monospace',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              maxHeight: 200,
              overflow: 'auto',
              mb: 2,
            }}
          >
            {this.state.error.message}
          </Box>
          <Stack direction="row" spacing={1}>
            <Button
              size="small"
              variant="contained"
              startIcon={<HomeIcon />}
              onClick={this.handleGoHome}
            >
              Go to dashboard
            </Button>
            <Button
              size="small"
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={this.handleReload}
            >
              Reload page
            </Button>
          </Stack>
        </Alert>
      </Box>
    );
  }
}
