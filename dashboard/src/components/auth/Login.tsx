import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Alert,
  InputAdornment,
  IconButton,
  useTheme,
} from '@mui/material';
import { Visibility, VisibilityOff } from '@mui/icons-material';
import LightModeOutlined from '@mui/icons-material/LightModeOutlined';
import DarkModeOutlined from '@mui/icons-material/DarkModeOutlined';
import { useAuth } from '@/contexts/AuthContext';
import { useThemeMode } from '@/contexts/ThemeContext';

const Login: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const { mode, toggleTheme } = useThemeMode();
  const { login } = useAuth();

  const dark = mode === 'dark';

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const from = (location.state as any)?.from?.pathname || '/';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      await login({ username, password });
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Invalid username or password');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        bgcolor: 'background.default',
        p: 3,
        position: 'relative',
      }}
    >
      <IconButton
        onClick={toggleTheme}
        size="small"
        sx={{
          position: 'absolute',
          top: 20,
          right: 20,
          color: 'text.secondary',
          border: `1px solid ${theme.palette.divider}`,
          width: 34,
          height: 34,
        }}
      >
        {dark ? <LightModeOutlined sx={{ fontSize: 16 }} /> : <DarkModeOutlined sx={{ fontSize: 16 }} />}
      </IconButton>

      <Box sx={{ mb: 4.5, textAlign: 'center' }}>
        <Box
          component="img"
          src="/sentinel.png"
          alt="Sentinel Governance AI"
          sx={{
            height: 120,
            width: 'auto',
            objectFit: 'contain',
            mx: 'auto',
            display: 'block',
          }}
        />
      </Box>

      <Card sx={{ width: '100%', maxWidth: 400 }}>
        <CardContent sx={{ p: 3.5 }}>
          <Typography variant="h5" sx={{ fontWeight: 600, mb: 0.25, color: 'text.primary' }}>
            Sign in
          </Typography>
          <Typography sx={{ color: 'text.secondary', mb: 3, fontSize: '0.8125rem' }}>
            Enter your credentials to continue
          </Typography>

          {error && (
            <Alert severity="error" sx={{ mb: 2.5 }}>{error}</Alert>
          )}

          <form onSubmit={handleSubmit}>
            <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>
              Username
            </Typography>
            <TextField
              fullWidth
              variant="outlined"
              size="small"
              placeholder="Enter your username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              required
              disabled={isLoading}
              sx={{ mb: 2 }}
            />

            <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>
              Password
            </Typography>
            <TextField
              fullWidth
              type={showPassword ? 'text' : 'password'}
              variant="outlined"
              size="small"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              disabled={isLoading}
              sx={{ mb: 3 }}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowPassword(!showPassword)}
                      edge="end"
                      size="small"
                      sx={{ color: 'text.secondary' }}
                    >
                      {showPassword ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />

            <Button
              type="submit"
              fullWidth
              variant="contained"
              disabled={isLoading}
              sx={{ py: 1, fontWeight: 600 }}
            >
              {isLoading ? 'Signing in...' : 'Sign in'}
            </Button>
          </form>

          <Box
            sx={{
              mt: 2.5,
              p: 1.75,
              borderRadius: '6px',
              bgcolor: dark ? 'rgba(255,255,255,0.025)' : 'rgba(0,0,0,0.02)',
              border: `1px solid ${theme.palette.divider}`,
            }}
          >
            <Typography sx={{ color: 'text.secondary', fontSize: '0.6875rem' }}>
              <span style={{ fontWeight: 600, color: theme.palette.text.primary }}>Dev credentials</span>
              <br />
              admin / admin123
            </Typography>
          </Box>
        </CardContent>
      </Card>

      <Typography sx={{ mt: 3.5, color: 'text.secondary', fontSize: '0.6875rem', opacity: 0.5 }}>
        Sentinel AI v1.0.0
      </Typography>
    </Box>
  );
};

export default Login;
