import { Box, Typography, Button } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useWhiteLabel } from '../../theme/WhiteLabelContext';

export default function NotFoundPage() {
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
          ? 'radial-gradient(ellipse at 50% 50%, rgba(0, 212, 170, 0.05) 0%, rgba(14, 165, 233, 0.02) 40%, #0a0e1a 70%)'
          : 'radial-gradient(ellipse at 50% 50%, rgba(0, 212, 170, 0.03) 0%, rgba(14, 165, 233, 0.01) 40%, #f0f2f5 70%)',
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
          background: 'linear-gradient(135deg, #00d4aa 0%, #0ea5e9 100%)',
          backgroundClip: 'text',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          mb: 2,
          userSelect: 'none',
        }}
      >
        404
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
        Page Not Found
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
        The page you're looking for doesn't exist or has been moved.
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
