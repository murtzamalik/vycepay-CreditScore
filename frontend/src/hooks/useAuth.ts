import { useSelector, useDispatch } from 'react-redux';
import type { RootState, AppDispatch } from '../store';
import { logout, setApiKey } from '../features/auth/authSlice';
import { useLoginMutation } from '../api/authApi';
import type { UserRole } from '../types/common';

export function useAuth() {
  const dispatch = useDispatch<AppDispatch>();
  const auth = useSelector((state: RootState) => state.auth);
  const [loginMutation, { isLoading: isLoginLoading }] = useLoginMutation();

  const login = async (email: string, password: string) => {
    const result = await loginMutation({ email, password }).unwrap();
    // If no API key is stored, set the default UAT test key for score lookups.
    // In production this would be managed via the Partner API Keys page.
    if (!auth.apiKey) {
      const defaultApiKey = import.meta.env.VITE_DEFAULT_API_KEY;
      if (defaultApiKey) {
        dispatch(setApiKey(defaultApiKey));
      }
    }
    return result;
  };

  const handleLogout = () => {
    dispatch(logout());
  };

  const updateApiKey = (key: string) => {
    dispatch(setApiKey(key));
  };

  const hasRole = (requiredRoles: UserRole[]): boolean => {
    if (!auth.user) return false;
    return requiredRoles.includes(auth.user.role);
  };

  return {
    user: auth.user,
    isAuthenticated: auth.isAuthenticated,
    isLoginLoading,
    accessToken: auth.accessToken,
    login,
    logout: handleLogout,
    updateApiKey,
    hasRole,
  };
}
