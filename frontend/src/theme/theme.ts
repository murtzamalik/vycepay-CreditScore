import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#00d4aa',
      light: '#33ddbb',
      dark: '#009977',
      contrastText: '#0a0e1a',
    },
    secondary: {
      main: '#0ea5e9',
      light: '#38bdf8',
      dark: '#0284c7',
      contrastText: '#0a0e1a',
    },
    background: {
      default: '#0a0e1a',
      paper: '#111827',
    },
    error: {
      main: '#ef4444',
      light: '#f87171',
      dark: '#dc2626',
    },
    warning: {
      main: '#f59e0b',
      light: '#fbbf24',
      dark: '#d97706',
    },
    success: {
      main: '#10b981',
      light: '#34d399',
      dark: '#059669',
    },
    info: {
      main: '#0ea5e9',
      light: '#38bdf8',
      dark: '#0284c7',
    },
    text: {
      primary: '#f1f5f9',
      secondary: '#94a3b8',
      disabled: '#475569',
    },
    divider: 'rgba(148, 163, 184, 0.08)',
    action: {
      hover: 'rgba(0, 212, 170, 0.06)',
      selected: 'rgba(0, 212, 170, 0.1)',
      focus: 'rgba(0, 212, 170, 0.12)',
    },
  },
  typography: {
    fontFamily: '"DM Sans", "Helvetica", "Arial", sans-serif',
    h1: {
      fontFamily: '"Sora", "DM Sans", sans-serif',
      fontWeight: 800,
      letterSpacing: '-0.02em',
    },
    h2: {
      fontFamily: '"Sora", "DM Sans", sans-serif',
      fontWeight: 700,
      letterSpacing: '-0.02em',
    },
    h3: {
      fontFamily: '"Sora", "DM Sans", sans-serif',
      fontWeight: 700,
      letterSpacing: '-0.01em',
    },
    h4: {
      fontFamily: '"Sora", "DM Sans", sans-serif',
      fontWeight: 700,
      letterSpacing: '-0.01em',
    },
    h5: {
      fontFamily: '"Sora", "DM Sans", sans-serif',
      fontWeight: 600,
      letterSpacing: '-0.01em',
    },
    h6: {
      fontFamily: '"Sora", "DM Sans", sans-serif',
      fontWeight: 600,
    },
    subtitle1: {
      fontWeight: 500,
    },
    subtitle2: {
      fontWeight: 600,
      fontSize: '0.8125rem',
      letterSpacing: '0.02em',
      textTransform: 'uppercase' as const,
    },
    body2: {
      fontSize: '0.875rem',
      lineHeight: 1.6,
    },
    caption: {
      fontSize: '0.75rem',
      color: '#64748b',
    },
    button: {
      fontWeight: 600,
      letterSpacing: '0.01em',
    },
  },
  shape: {
    borderRadius: 12,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: '#0a0e1a',
          backgroundImage: 'radial-gradient(ellipse at 20% 0%, rgba(0, 212, 170, 0.03) 0%, transparent 50%), radial-gradient(ellipse at 80% 100%, rgba(14, 165, 233, 0.03) 0%, transparent 50%)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          borderRadius: 10,
          padding: '10px 24px',
          transition: 'all 0.2s ease',
        },
        contained: {
          background: 'linear-gradient(135deg, #00d4aa 0%, #00b894 100%)',
          color: '#0a0e1a',
          boxShadow: '0 2px 12px rgba(0, 212, 170, 0.25)',
          '&:hover': {
            background: 'linear-gradient(135deg, #00e4ba 0%, #00c8a4 100%)',
            boxShadow: '0 4px 20px rgba(0, 212, 170, 0.35)',
            transform: 'translateY(-1px)',
          },
        },
        outlined: {
          borderColor: 'rgba(0, 212, 170, 0.3)',
          color: '#00d4aa',
          '&:hover': {
            borderColor: '#00d4aa',
            backgroundColor: 'rgba(0, 212, 170, 0.06)',
          },
        },
        text: {
          color: '#94a3b8',
          '&:hover': {
            backgroundColor: 'rgba(148, 163, 184, 0.08)',
            color: '#f1f5f9',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: '#111827',
          border: '1px solid rgba(148, 163, 184, 0.06)',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.2)',
          backgroundImage: 'none',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: '#080c15',
          color: '#f1f5f9',
          borderRight: '1px solid rgba(148, 163, 184, 0.06)',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#0d1117',
          backgroundImage: 'none',
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            backgroundColor: 'rgba(148, 163, 184, 0.04)',
            borderRadius: 10,
            '& fieldset': {
              borderColor: 'rgba(148, 163, 184, 0.12)',
            },
            '&:hover fieldset': {
              borderColor: 'rgba(0, 212, 170, 0.3)',
            },
            '&.Mui-focused fieldset': {
              borderColor: '#00d4aa',
              boxShadow: '0 0 0 3px rgba(0, 212, 170, 0.1)',
            },
          },
          '& .MuiInputLabel-root': {
            color: '#64748b',
          },
          '& .MuiInputLabel-root.Mui-focused': {
            color: '#00d4aa',
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          fontWeight: 600,
          fontSize: 12,
        },
        colorPrimary: {
          backgroundColor: 'rgba(0, 212, 170, 0.12)',
          color: '#00d4aa',
          border: '1px solid rgba(0, 212, 170, 0.2)',
        },
        colorSecondary: {
          backgroundColor: 'rgba(14, 165, 233, 0.12)',
          color: '#38bdf8',
          border: '1px solid rgba(14, 165, 233, 0.2)',
        },
        colorError: {
          backgroundColor: 'rgba(239, 68, 68, 0.12)',
          color: '#f87171',
          border: '1px solid rgba(239, 68, 68, 0.2)',
        },
        colorWarning: {
          backgroundColor: 'rgba(245, 158, 11, 0.12)',
          color: '#fbbf24',
          border: '1px solid rgba(245, 158, 11, 0.2)',
        },
        colorSuccess: {
          backgroundColor: 'rgba(16, 185, 129, 0.12)',
          color: '#34d399',
          border: '1px solid rgba(16, 185, 129, 0.2)',
        },
        colorInfo: {
          backgroundColor: 'rgba(14, 165, 233, 0.12)',
          color: '#38bdf8',
          border: '1px solid rgba(14, 165, 233, 0.2)',
        },
        outlined: {
          borderColor: 'rgba(148, 163, 184, 0.15)',
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 10,
        },
        standardError: {
          backgroundColor: 'rgba(239, 68, 68, 0.08)',
          border: '1px solid rgba(239, 68, 68, 0.2)',
          color: '#f87171',
        },
        standardSuccess: {
          backgroundColor: 'rgba(16, 185, 129, 0.08)',
          border: '1px solid rgba(16, 185, 129, 0.2)',
          color: '#34d399',
        },
        standardWarning: {
          backgroundColor: 'rgba(245, 158, 11, 0.08)',
          border: '1px solid rgba(245, 158, 11, 0.2)',
          color: '#fbbf24',
        },
        standardInfo: {
          backgroundColor: 'rgba(14, 165, 233, 0.08)',
          border: '1px solid rgba(14, 165, 233, 0.2)',
          color: '#38bdf8',
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          backgroundColor: '#141a2a',
          border: '1px solid rgba(148, 163, 184, 0.1)',
          boxShadow: '0 24px 64px rgba(0, 0, 0, 0.5)',
          borderRadius: 16,
        },
      },
    },
    MuiDialogTitle: {
      styleOverrides: {
        root: {
          fontFamily: '"Sora", "DM Sans", sans-serif',
          fontWeight: 600,
        },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: {
          backgroundColor: 'rgba(148, 163, 184, 0.08)',
          borderRadius: 6,
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: {
          borderColor: 'rgba(148, 163, 184, 0.08)',
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          color: '#94a3b8',
          '&:hover': {
            backgroundColor: 'rgba(0, 212, 170, 0.08)',
            color: '#00d4aa',
          },
        },
      },
    },
    MuiToggleButton: {
      styleOverrides: {
        root: {
          borderColor: 'rgba(148, 163, 184, 0.15)',
          color: '#94a3b8',
          '&.Mui-selected': {
            backgroundColor: 'rgba(0, 212, 170, 0.12)',
            color: '#00d4aa',
            borderColor: 'rgba(0, 212, 170, 0.3)',
            '&:hover': {
              backgroundColor: 'rgba(0, 212, 170, 0.18)',
            },
          },
          '&:hover': {
            backgroundColor: 'rgba(148, 163, 184, 0.06)',
          },
        },
      },
    },
    MuiSwitch: {
      styleOverrides: {
        switchBase: {
          '&.Mui-checked': {
            color: '#00d4aa',
            '& + .MuiSwitch-track': {
              backgroundColor: 'rgba(0, 212, 170, 0.4)',
            },
          },
        },
        track: {
          backgroundColor: 'rgba(148, 163, 184, 0.2)',
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: '1px solid rgba(148, 163, 184, 0.06)',
        },
        head: {
          color: '#94a3b8',
          fontWeight: 600,
          fontSize: 12,
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          backgroundColor: 'rgba(0, 212, 170, 0.03)',
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:hover': {
            backgroundColor: 'rgba(0, 212, 170, 0.03)',
          },
        },
      },
    },
    MuiMenu: {
      styleOverrides: {
        paper: {
          backgroundColor: '#141a2a',
          border: '1px solid rgba(148, 163, 184, 0.1)',
          boxShadow: '0 12px 40px rgba(0, 0, 0, 0.4)',
        },
      },
    },
    MuiMenuItem: {
      styleOverrides: {
        root: {
          '&:hover': {
            backgroundColor: 'rgba(0, 212, 170, 0.06)',
          },
          '&.Mui-selected': {
            backgroundColor: 'rgba(0, 212, 170, 0.1)',
          },
        },
      },
    },
    MuiSkeleton: {
      styleOverrides: {
        root: {
          backgroundColor: 'rgba(148, 163, 184, 0.06)',
        },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          backgroundColor: '#1a1f2e',
          border: '1px solid rgba(148, 163, 184, 0.1)',
          color: '#f1f5f9',
          fontSize: 12,
          borderRadius: 8,
        },
      },
    },
    MuiSnackbar: {
      styleOverrides: {
        root: {
          '& .MuiAlert-filled': {
            borderRadius: 10,
          },
        },
      },
    },
  },
});

export default theme;
