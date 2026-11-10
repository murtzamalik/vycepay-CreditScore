import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useGetMeQuery } from '../api/authApi';
import LoadingSpinner from '../components/common/LoadingSpinner';

export default function AuthGuard() {
  const { isAuthenticated, user, accessToken, logout } = useAuth();
  const location = useLocation();

  // Auto-fetch user profile if we have a token but no user data (e.g., page refresh)
  const { isLoading, isError } = useGetMeQuery(undefined, {
    skip: !accessToken || !!user,
  });

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Token is invalid/expired — clear state and redirect to login
  if (isError) {
    logout();
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Show loading while validating session
  if (isLoading) {
    return <LoadingSpinner message="Loading your session..." fullPage />;
  }

  return <Outlet />;
}
