import { Box, Typography, Button } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useWhiteLabel } from '../../theme/WhiteLabelContext';

export default function UnauthorizedPage() {
  const navigate = useNavigate();
  const { isDark } = useWhiteLabel();

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'background.default',
        background: isDark
          ? 'radial-gradient(ellipse at 50% 50%, rgba(245, 158, 11, 0.04) 0%, rgba(239, 68, 68, 0.02) 40%, #0a0e1a 70%)'
          : 'radial-gradient(ellipse at 50% 50%, rgba(245, 158, 11, 0.03) 0%, rgba(239, 68, 68, 0.01) 40%, #f0f2f5 70%)',
        p: 4,
      }}
    >
      <Typography
        variant="h1"
        className="vyce-animate"
        sx={{
          fontWeight: 800,
          fontSize: { xs: '8rem', md: '12rem' },
          lineHeight: 1,
          fontFamily: '"Sora", sans-serif',
          background: 'linear-gradient(135deg, #f59e0b 0%, #ef4444 100%)',
          backgroundClip: 'text',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          mb: 2,
          userSelect: 'none',
        }}
      >
        403
      </Typography>
      <Typography
        variant="h5"
        gutterBottom
        className="vyce-animate vyce-animate-delay-1"
        sx={{
          fontWeight: 600,
          fontFamily: '"Sora", sans-serif',
          color: 'text.primary',
        }}
      >
        Access Denied
      </Typography>
      <Typography
        variant="body1"
        className="vyce-animate vyce-animate-delay-2"
        sx={{
          mb: 4,
          color: 'text.secondary',
          fontFamily: '"DM Sans", sans-serif',
        }}
      >
        You don't have permission to access this page.
      </Typography>
      <Button
        variant="contained"
        size="large"
        className="vyce-animate vyce-animate-delay-3"
        onClick={() => navigate('/dashboard')}
        sx={{ px: 4, py: 1.5 }}
      >
        Go to Dashboard
      </Button>
    </Box>
  );
}
