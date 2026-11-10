import { Navigate, Outlet } from 'react-router-dom';
import { Box, Typography, Button } from '@mui/material';
import BlockIcon from '@mui/icons-material/Block';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import type { UserRole } from '../types/common';

interface RoleGuardProps {
  allowedRoles: UserRole[];
}

function Forbidden() {
  const navigate = useNavigate();

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '60vh',
        textAlign: 'center',
        p: 4,
      }}
    >
      <BlockIcon sx={{ fontSize: 80, color: 'error.main', mb: 2 }} />
      <Typography variant="h4" gutterBottom>
        403 - Access Denied
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 3, maxWidth: 480 }}>
        You do not have sufficient permissions to access this page. Please contact your
        administrator if you believe this is an error.
      </Typography>
      <Button variant="contained" onClick={() => navigate('/dashboard')}>
        Go to Dashboard
      </Button>
    </Box>
  );
}

export default function RoleGuard({ allowedRoles }: RoleGuardProps) {
  const { hasRole, isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (!hasRole(allowedRoles)) {
    return <Forbidden />;
  }

  return <Outlet />;
}
