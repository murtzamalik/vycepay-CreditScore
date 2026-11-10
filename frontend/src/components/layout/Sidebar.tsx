import {
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Box,
  Typography,
  Divider,
} from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import SearchIcon from '@mui/icons-material/Search';
import PeopleIcon from '@mui/icons-material/People';
import BusinessIcon from '@mui/icons-material/Business';
import HistoryIcon from '@mui/icons-material/History';
import SettingsIcon from '@mui/icons-material/Settings';
import BarChartIcon from '@mui/icons-material/BarChart';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import WidgetsIcon from '@mui/icons-material/Widgets';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useWhiteLabel } from '../../theme/WhiteLabelContext';
import type { UserRole } from '../../types/common';

interface NavItem {
  label: string;
  path: string;
  icon: React.ReactNode;
  roles: UserRole[];
  section?: string;
}

const NAV_ITEMS: NavItem[] = [
  {
    label: 'Dashboard',
    path: '/dashboard',
    icon: <DashboardIcon />,
    roles: ['Admin', 'Operator', 'Partner', 'ReadOnly'],
    section: 'Overview',
  },
  {
    label: 'Score Lookup',
    path: '/scores/lookup',
    icon: <SearchIcon />,
    roles: ['Admin', 'Operator'],
    section: 'Scoring',
  },
  // Partner-specific items
  {
    label: 'Partner Dashboard',
    path: '/partner/dashboard',
    icon: <DashboardIcon />,
    roles: ['Partner'],
    section: 'Partner',
  },
  {
    label: 'Score Lookup',
    path: '/partner/scores',
    icon: <SearchIcon />,
    roles: ['Partner'],
  },
  {
    label: 'Usage & Billing',
    path: '/partner/usage',
    icon: <BarChartIcon />,
    roles: ['Partner'],
  },
  {
    label: 'API Keys',
    path: '/partner/api-keys',
    icon: <VpnKeyIcon />,
    roles: ['Partner'],
  },
  {
    label: 'Embed Widget',
    path: '/partner/embed-config',
    icon: <WidgetsIcon />,
    roles: ['Partner'],
  },
  // Admin items
  {
    label: 'Customers',
    path: '/admin/customers',
    icon: <BusinessIcon />,
    roles: ['Admin', 'Operator'],
    section: 'Administration',
  },
  {
    label: 'Users',
    path: '/admin/users',
    icon: <PeopleIcon />,
    roles: ['Admin'],
  },
  {
    label: 'Audit Logs',
    path: '/admin/audit-logs',
    icon: <HistoryIcon />,
    roles: ['Admin', 'Operator'],
  },
  {
    label: 'Settings',
    path: '/settings',
    icon: <SettingsIcon />,
    roles: ['Admin', 'Operator'],
  },
];

export const SIDEBAR_WIDTH = 260;

// Sidebar always uses dark colors regardless of theme mode (branded element)
const SIDEBAR_TEXT_PRIMARY = '#f1f5f9';
const SIDEBAR_TEXT_SECONDARY = '#94a3b8';
const SIDEBAR_TEXT_DISABLED = '#475569';
const SIDEBAR_DIVIDER = 'rgba(148, 163, 184, 0.08)';

export default function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { hasRole } = useAuth();
  const { config } = useWhiteLabel();
  const primary = config.primaryColor;

  const visibleItems = NAV_ITEMS.filter((item) => hasRole(item.roles));

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: SIDEBAR_WIDTH,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: SIDEBAR_WIDTH,
          boxSizing: 'border-box',
          overflowX: 'hidden',
        },
      }}
    >
      {/* Logo area */}
      <Box
        sx={{
          p: 2.5,
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
        }}
      >
        {config.logoUrl ? (
          <Box
            component="img"
            src={config.logoUrl}
            alt={config.appName}
            sx={{ width: 36, height: 36, borderRadius: '10px', objectFit: 'contain' }}
          />
        ) : (
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: '10px',
              background: `linear-gradient(135deg, ${primary} 0%, ${config.secondaryColor} 100%)`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: `0 2px 12px ${primary}4d`,
            }}
          >
            <Typography
              variant="subtitle2"
              sx={{
                fontWeight: 800,
                color: '#0a0e1a',
                fontFamily: '"Sora", sans-serif',
                fontSize: 13,
                textTransform: 'none',
                letterSpacing: 0,
              }}
            >
              {config.appName.slice(0, 2).toUpperCase()}
            </Typography>
          </Box>
        )}
        <Box>
          <Typography
            sx={{
              fontWeight: 700,
              color: SIDEBAR_TEXT_PRIMARY,
              fontFamily: '"Sora", sans-serif',
              fontSize: 16,
              letterSpacing: '-0.01em',
              lineHeight: 1.2,
            }}
          >
            {config.appName}
          </Typography>
          <Typography
            sx={{
              fontSize: 10,
              color: SIDEBAR_TEXT_DISABLED,
              fontWeight: 500,
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
            }}
          >
            Credit Engine
          </Typography>
        </Box>
      </Box>

      <Divider sx={{ mx: 2, borderColor: SIDEBAR_DIVIDER }} />

      <List sx={{ pt: 1.5, px: 1 }}>
        {visibleItems.map((item, index) => {
          const isActive = location.pathname.startsWith(item.path);
          const showSection =
            item.section && (index === 0 || visibleItems[index - 1]?.section !== item.section);

          return (
            <Box key={item.path}>
              {showSection && (
                <Typography
                  sx={{
                    px: 1.5,
                    pt: index === 0 ? 0 : 2,
                    pb: 0.5,
                    fontSize: 10,
                    fontWeight: 600,
                    color: SIDEBAR_TEXT_DISABLED,
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                  }}
                >
                  {item.section}
                </Typography>
              )}
              <ListItem disablePadding sx={{ mb: 0.25 }}>
                <ListItemButton
                  onClick={() => navigate(item.path)}
                  sx={{
                    borderRadius: '10px',
                    py: 1,
                    px: 1.5,
                    position: 'relative',
                    backgroundColor: isActive ? `${primary}14` : 'transparent',
                    '&::before': isActive
                      ? {
                          content: '""',
                          position: 'absolute',
                          left: 0,
                          top: '50%',
                          transform: 'translateY(-50%)',
                          width: 3,
                          height: 20,
                          borderRadius: '0 3px 3px 0',
                          background: `linear-gradient(180deg, ${primary}, ${config.secondaryColor})`,
                        }
                      : {},
                    '&:hover': {
                      backgroundColor: isActive
                        ? `${primary}1a`
                        : 'rgba(148, 163, 184, 0.06)',
                    },
                  }}
                >
                  <ListItemIcon
                    sx={{
                      color: isActive ? primary : SIDEBAR_TEXT_DISABLED,
                      minWidth: 36,
                      '& .MuiSvgIcon-root': {
                        fontSize: 20,
                      },
                    }}
                  >
                    {item.icon}
                  </ListItemIcon>
                  <ListItemText
                    primary={item.label}
                    primaryTypographyProps={{
                      fontSize: 13,
                      fontWeight: isActive ? 600 : 400,
                      color: isActive ? SIDEBAR_TEXT_PRIMARY : SIDEBAR_TEXT_SECONDARY,
                      letterSpacing: '0.01em',
                    }}
                  />
                </ListItemButton>
              </ListItem>
            </Box>
          );
        })}
      </List>

      {/* Bottom accent line */}
      <Box sx={{ flexGrow: 1 }} />
      <Box
        sx={{
          p: 2,
          borderTop: `1px solid ${SIDEBAR_DIVIDER}`,
        }}
      >
        <Typography
          sx={{
            fontSize: 10,
            color: SIDEBAR_TEXT_DISABLED,
            textAlign: 'center',
            fontWeight: 500,
          }}
        >
          v1.0 &middot; Powered by VycePay
        </Typography>
      </Box>
    </Drawer>
  );
}
