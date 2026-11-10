import {
  AppBar,
  Toolbar,
  IconButton,
  Box,
  Avatar,
  Menu,
  MenuItem,
  Chip,
  Badge,
  Typography,
  Tooltip,
} from '@mui/material';
import NotificationsNoneIcon from '@mui/icons-material/NotificationsNone';
import LogoutIcon from '@mui/icons-material/Logout';
import PersonOutlineIcon from '@mui/icons-material/PersonOutline';
import DarkModeOutlinedIcon from '@mui/icons-material/DarkModeOutlined';
import LightModeOutlinedIcon from '@mui/icons-material/LightModeOutlined';
import { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { useWhiteLabel } from '../../theme/WhiteLabelContext';
import { SIDEBAR_WIDTH } from './Sidebar';

export default function Header() {
  const { user, logout } = useAuth();
  const { isDark, toggleMode, config } = useWhiteLabel();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = () => {
    handleMenuClose();
    logout();
  };

  const initials = user?.name
    ? user.name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
    : '?';

  const primary = config.primaryColor;

  return (
    <AppBar
      position="fixed"
      elevation={0}
      sx={{
        width: `calc(100% - ${SIDEBAR_WIDTH}px)`,
        ml: `${SIDEBAR_WIDTH}px`,
        backgroundColor: isDark ? 'rgba(10, 14, 26, 0.8)' : 'rgba(255, 255, 255, 0.8)',
        backdropFilter: 'blur(12px)',
        borderBottom: 1,
        borderColor: 'divider',
      }}
    >
      <Toolbar sx={{ justifyContent: 'flex-end', gap: 1 }}>
        {user && (
          <Chip
            label={user.role}
            size="small"
            sx={{
              backgroundColor: `${primary}1a`,
              color: primary,
              fontWeight: 600,
              fontSize: 11,
              border: `1px solid ${primary}33`,
              mr: 1,
            }}
          />
        )}

        {/* Theme toggle */}
        <Tooltip title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}>
          <IconButton
            size="small"
            onClick={toggleMode}
            sx={{
              color: 'text.secondary',
              transition: 'transform 0.3s ease',
              '&:hover': {
                transform: 'rotate(30deg)',
              },
            }}
          >
            {isDark ? (
              <LightModeOutlinedIcon sx={{ fontSize: 20 }} />
            ) : (
              <DarkModeOutlinedIcon sx={{ fontSize: 20 }} />
            )}
          </IconButton>
        </Tooltip>

        <IconButton size="small" sx={{ color: 'text.secondary' }}>
          <Badge
            variant="dot"
            sx={{
              '& .MuiBadge-badge': {
                backgroundColor: primary,
                width: 8,
                height: 8,
                minWidth: 8,
              },
            }}
          >
            <NotificationsNoneIcon sx={{ fontSize: 20 }} />
          </Badge>
        </IconButton>

        <IconButton onClick={handleMenuOpen} size="small">
          <Avatar
            sx={{
              width: 34,
              height: 34,
              background: `linear-gradient(135deg, ${primary} 0%, ${config.secondaryColor} 100%)`,
              fontSize: 13,
              fontWeight: 700,
              fontFamily: '"Sora", sans-serif',
              color: isDark ? '#0a0e1a' : '#ffffff',
            }}
          >
            {initials}
          </Avatar>
        </IconButton>

        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={handleMenuClose}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}
          slotProps={{
            paper: {
              sx: { minWidth: 200, mt: 1 },
            },
          }}
        >
          {user && (
            <Box sx={{ px: 2, py: 1.5, borderBottom: 1, borderColor: 'divider' }}>
              <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary' }}>
                {user.name}
              </Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                {user.email}
              </Typography>
            </Box>
          )}
          <MenuItem onClick={handleMenuClose} sx={{ gap: 1.5, py: 1.5 }}>
            <PersonOutlineIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
            <Typography variant="body2">Profile</Typography>
          </MenuItem>
          <MenuItem onClick={handleLogout} sx={{ gap: 1.5, py: 1.5 }}>
            <LogoutIcon sx={{ fontSize: 18, color: 'error.main' }} />
            <Typography variant="body2" sx={{ color: 'error.main' }}>
              Sign Out
            </Typography>
          </MenuItem>
        </Menu>
      </Toolbar>
    </AppBar>
  );
}
