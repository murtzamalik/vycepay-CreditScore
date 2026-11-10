import { Box, CircularProgress, Typography } from '@mui/material';

interface LoadingSpinnerProps {
  message?: string;
  size?: number;
  fullPage?: boolean;
}

export default function LoadingSpinner({
  message = 'Loading...',
  size = 40,
  fullPage = false,
}: LoadingSpinnerProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: fullPage ? '100vh' : '200px',
        gap: 2,
      }}
    >
      <CircularProgress
        size={size}
        sx={{
          color: 'primary.main',
          '& .MuiCircularProgress-circle': {
            strokeLinecap: 'round',
          },
        }}
      />
      {message && (
        <Typography variant="body2" sx={{ color: 'text.disabled', fontWeight: 500 }}>
          {message}
        </Typography>
      )}
    </Box>
  );
}
