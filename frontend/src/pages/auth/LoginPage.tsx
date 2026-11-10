import { useState } from 'react';
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
  Link,
} from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useRequestPasswordResetMutation } from '../../api/authApi';
import { useWhiteLabel } from '../../theme/WhiteLabelContext';

interface LocationState {
  from?: { pathname: string };
}

type ViewMode = 'login' | 'forgotPassword';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('login');
  const [resetEmail, setResetEmail] = useState('');
  const [resetSuccess, setResetSuccess] = useState(false);

  const { login, isLoginLoading, isAuthenticated } = useAuth();
  const [requestPasswordReset, { isLoading: isResetLoading }] =
    useRequestPasswordResetMutation();
  const { config, isDark } = useWhiteLabel();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as LocationState)?.from?.pathname || '/dashboard';

  if (isAuthenticated) {
    navigate(from, { replace: true });
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email || !password) {
      setError('Please enter both email and password.');
      return;
    }

    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch {
      setError('Invalid email or password. Please try again.');
    }
  };

  const handlePasswordReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!resetEmail) {
      setError('Please enter your email address.');
      return;
    }

    try {
      await requestPasswordReset({ email: resetEmail }).unwrap();
      setResetSuccess(true);
    } catch {
      setError('Failed to send reset link. Please try again.');
    }
  };

  const handleBackToLogin = () => {
    setViewMode('login');
    setError(null);
    setResetSuccess(false);
    setResetEmail('');
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'background.default',
        background: isDark
          ? 'radial-gradient(ellipse at 50% 40%, rgba(0, 212, 170, 0.06) 0%, rgba(14, 165, 233, 0.03) 40%, #0a0e1a 70%)'
          : 'radial-gradient(ellipse at 50% 40%, rgba(0, 212, 170, 0.04) 0%, rgba(14, 165, 233, 0.02) 40%, #f0f2f5 70%)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Geometric grid background */}
      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          backgroundImage:
            `linear-gradient(${isDark ? 'rgba(148, 163, 184, 0.03)' : 'rgba(0, 0, 0, 0.03)'} 1px, transparent 1px), linear-gradient(90deg, ${isDark ? 'rgba(148, 163, 184, 0.03)' : 'rgba(0, 0, 0, 0.03)'} 1px, transparent 1px)`,
          backgroundSize: '60px 60px',
          pointerEvents: 'none',
        }}
      />
      {/* Subtle diagonal accent lines */}
      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          backgroundImage:
            'linear-gradient(135deg, transparent 40%, rgba(0, 212, 170, 0.015) 40%, rgba(0, 212, 170, 0.015) 40.5%, transparent 40.5%, transparent 60%, rgba(14, 165, 233, 0.015) 60%, rgba(14, 165, 233, 0.015) 60.5%, transparent 60.5%)',
          pointerEvents: 'none',
        }}
      />

      <Card
        className="vyce-animate"
        sx={{
          width: '100%',
          maxWidth: 420,
          mx: 2,
          backgroundColor: 'background.paper',
          border: (theme) => `1px solid ${isDark ? 'rgba(0, 212, 170, 0.15)' : theme.palette.divider}`,
          borderRadius: '16px',
          boxShadow: isDark
            ? '0 0 40px rgba(0, 212, 170, 0.06), 0 8px 32px rgba(0, 0, 0, 0.4)'
            : '0 8px 32px rgba(0, 0, 0, 0.08)',
          position: 'relative',
          zIndex: 1,
        }}
      >
        <CardContent sx={{ p: 4 }}>
          <Box sx={{ textAlign: 'center', mb: 4 }}>
            {config.logoUrl ? (
              <Box
                component="img"
                src={config.logoUrl}
                alt={config.appName}
                sx={{ width: 56, height: 56, borderRadius: '12px', objectFit: 'contain', mx: 'auto', mb: 2 }}
              />
            ) : (
              <Box
                sx={{
                  width: 56,
                  height: 56,
                  borderRadius: '14px',
                  background: 'linear-gradient(135deg, #00d4aa 0%, #0ea5e9 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  mx: 'auto',
                  mb: 2,
                  boxShadow: '0 4px 20px rgba(0, 212, 170, 0.3)',
                }}
              >
                <Typography variant="h6" sx={{ fontWeight: 700, color: '#0a0e1a', fontFamily: '"Sora", sans-serif' }}>
                  {config.appName.slice(0, 2).toUpperCase()}
                </Typography>
              </Box>
            )}
            <Typography
              variant="h5"
              sx={{
                fontWeight: 700,
                fontFamily: '"Sora", sans-serif',
                background: 'linear-gradient(135deg, #00d4aa 0%, #0ea5e9 100%)',
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
            >
              {config.appName}
            </Typography>
            <Typography
              variant="body2"
              sx={{
                color: 'text.disabled',
                fontFamily: '"DM Sans", sans-serif',
                textTransform: 'uppercase',
                letterSpacing: '0.15em',
                fontSize: '0.7rem',
                mt: 0.5,
              }}
            >
              {viewMode === 'login'
                ? 'Credit Scoring Admin Portal'
                : 'Reset your password'}
            </Typography>
          </Box>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {viewMode === 'login' ? (
            <Box component="form" onSubmit={handleSubmit}>
              <TextField
                fullWidth
                label="Email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                margin="normal"
                autoComplete="email"
                autoFocus
              />
              <TextField
                fullWidth
                label="Password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                margin="normal"
                autoComplete="current-password"
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        onClick={() => setShowPassword(!showPassword)}
                        edge="end"
                        size="small"
                      >
                        {showPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
              <Button
                type="submit"
                fullWidth
                variant="contained"
                size="large"
                disabled={isLoginLoading}
                sx={{
                  mt: 3,
                  py: 1.5,
                  fontFamily: '"DM Sans", sans-serif',
                  fontWeight: 700,
                  fontSize: '0.95rem',
                  textTransform: 'none',
                }}
              >
                {isLoginLoading ? 'Signing in...' : 'Sign In'}
              </Button>
              <Box sx={{ mt: 2, textAlign: 'center' }}>
                <Link
                  component="button"
                  type="button"
                  variant="body2"
                  onClick={() => {
                    setViewMode('forgotPassword');
                    setError(null);
                  }}
                  sx={{
                    cursor: 'pointer',
                    color: 'primary.main',
                    fontFamily: '"DM Sans", sans-serif',
                    textDecorationColor: 'rgba(0, 212, 170, 0.3)',
                    '&:hover': {
                      textDecorationColor: 'primary.main',
                    },
                  }}
                >
                  Forgot Password?
                </Link>
              </Box>
            </Box>
          ) : (
            <Box component="form" onSubmit={handlePasswordReset}>
              {resetSuccess ? (
                <Alert severity="success" sx={{ mb: 2 }}>
                  A password reset link has been sent to your email address. Please check
                  your inbox.
                </Alert>
              ) : (
                <>
                  <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary', fontFamily: '"DM Sans", sans-serif' }}>
                    Enter the email address associated with your account and we will send
                    you a link to reset your password.
                  </Typography>
                  <TextField
                    fullWidth
                    label="Email"
                    type="email"
                    value={resetEmail}
                    onChange={(e) => setResetEmail(e.target.value)}
                    margin="normal"
                    autoComplete="email"
                    autoFocus
                  />
                  <Button
                    type="submit"
                    fullWidth
                    variant="contained"
                    size="large"
                    disabled={isResetLoading}
                    sx={{
                      mt: 3,
                      py: 1.5,
                      fontFamily: '"DM Sans", sans-serif',
                      fontWeight: 700,
                      fontSize: '0.95rem',
                      textTransform: 'none',
                    }}
                  >
                    {isResetLoading ? 'Sending...' : 'Send Reset Link'}
                  </Button>
                </>
              )}
              <Button
                fullWidth
                variant="text"
                startIcon={<ArrowBackIcon />}
                onClick={handleBackToLogin}
                sx={{
                  mt: 1,
                  color: 'text.secondary',
                  fontFamily: '"DM Sans", sans-serif',
                  textTransform: 'none',
                  '&:hover': {
                    color: 'primary.main',
                    backgroundColor: 'action.hover',
                  },
                }}
              >
                Back to Sign In
              </Button>
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}
