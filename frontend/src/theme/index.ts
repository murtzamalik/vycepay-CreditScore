import { createTheme, type ThemeOptions } from '@mui/material/styles';
import type { WhiteLabelConfig } from '../types/theme';

/**
 * Default VyceScore brand colors — Obsidian Fintech palette.
 */
const DEFAULT_BRAND: WhiteLabelConfig = {
  primaryColor: '#00d4aa',
  secondaryColor: '#0ea5e9',
  appName: 'VyceScore',
  mode: 'dark',
};

/* ── colour tokens per mode ── */

const darkTokens = {
  bgDeepest: '#0a0e1a',
  bgSurface: '#111827',
  bgElevated: '#141a2a',
  bgSidebar: '#080c15',
  bgInput: 'rgba(148, 163, 184, 0.04)',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textMuted: '#64748b',
  border: 'rgba(148, 163, 184, 0.06)',
  borderAccent: 'rgba(148, 163, 184, 0.12)',
  divider: 'rgba(148, 163, 184, 0.08)',
  cardShadow: '0 1px 3px rgba(0, 0, 0, 0.2)',
  dialogShadow: '0 24px 64px rgba(0, 0, 0, 0.5)',
};

const lightTokens = {
  bgDeepest: '#f0f2f5',
  bgSurface: '#ffffff',
  bgElevated: '#f8f9fb',
  bgSidebar: '#080c15',  // Sidebar stays dark in light mode (branded element)
  bgInput: 'rgba(0, 0, 0, 0.02)',
  textPrimary: '#0f172a',
  textSecondary: '#475569',
  textMuted: '#94a3b8',
  border: 'rgba(0, 0, 0, 0.06)',
  borderAccent: 'rgba(0, 0, 0, 0.12)',
  divider: 'rgba(0, 0, 0, 0.08)',
  cardShadow: '0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)',
  dialogShadow: '0 24px 64px rgba(0, 0, 0, 0.12)',
};

/**
 * Build base theme options from a white-label config.
 */
export function buildThemeOptions(config: WhiteLabelConfig): ThemeOptions {
  const isDark = config.mode === 'dark';
  const t = isDark ? darkTokens : lightTokens;

  const primaryContrast = isDark ? '#0a0e1a' : '#ffffff';
  const containedText = isDark ? '#0a0e1a' : '#ffffff';

  return {
    palette: {
      mode: config.mode,
      primary: {
        main: config.primaryColor,
        contrastText: primaryContrast,
      },
      secondary: {
        main: config.secondaryColor,
        contrastText: primaryContrast,
      },
      background: {
        default: t.bgDeepest,
        paper: t.bgSurface,
      },
      error: { main: '#ef4444' },
      warning: { main: '#f59e0b' },
      success: { main: '#10b981' },
      text: {
        primary: t.textPrimary,
        secondary: t.textSecondary,
      },
      divider: t.divider,
    },
    typography: {
      fontFamily: '"DM Sans", "Helvetica", "Arial", sans-serif',
      h4: {
        fontFamily: '"Sora", "DM Sans", sans-serif',
        fontWeight: 700,
        letterSpacing: '-0.01em',
      },
      h5: {
        fontFamily: '"Sora", "DM Sans", sans-serif',
        fontWeight: 600,
      },
      h6: {
        fontFamily: '"Sora", "DM Sans", sans-serif',
        fontWeight: 600,
      },
    },
    shape: {
      borderRadius: 12,
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            backgroundColor: t.bgDeepest,
            backgroundImage: isDark
              ? 'radial-gradient(ellipse at 20% 0%, rgba(0, 212, 170, 0.03) 0%, transparent 50%), radial-gradient(ellipse at 80% 100%, rgba(14, 165, 233, 0.03) 0%, transparent 50%)'
              : 'none',
          },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: {
            backgroundColor: isDark ? '#0d1117' : 'rgba(255, 255, 255, 0.8)',
            backgroundImage: 'none',
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            fontWeight: 600,
            borderRadius: 10,
          },
          contained: {
            background: isDark
              ? `linear-gradient(135deg, ${config.primaryColor} 0%, ${config.primaryColor}cc 100%)`
              : config.primaryColor,
            color: containedText,
            boxShadow: `0 2px 12px ${config.primaryColor}40`,
            '&:hover': {
              boxShadow: `0 4px 20px ${config.primaryColor}50`,
              background: isDark
                ? `linear-gradient(135deg, ${config.primaryColor}ee 0%, ${config.primaryColor} 100%)`
                : config.primaryColor,
            },
          },
          outlined: {
            borderColor: isDark ? `${config.primaryColor}4d` : `${config.primaryColor}66`,
            color: config.primaryColor,
            '&:hover': {
              borderColor: config.primaryColor,
              backgroundColor: `${config.primaryColor}0d`,
            },
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            backgroundColor: t.bgSurface,
            border: `1px solid ${t.border}`,
            boxShadow: t.cardShadow,
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
            backgroundColor: isDark ? t.bgSidebar : darkTokens.bgSidebar,
            color: isDark ? t.textPrimary : darkTokens.textPrimary,
            borderRight: `1px solid ${isDark ? t.border : darkTokens.border}`,
          },
        },
      },
      MuiTextField: {
        styleOverrides: {
          root: {
            '& .MuiOutlinedInput-root': {
              backgroundColor: t.bgInput,
              borderRadius: 10,
              '& fieldset': {
                borderColor: t.borderAccent,
              },
              '&:hover fieldset': {
                borderColor: `${config.primaryColor}4d`,
              },
              '&.Mui-focused fieldset': {
                borderColor: config.primaryColor,
              },
            },
          },
        },
      },
      MuiDialog: {
        styleOverrides: {
          paper: {
            backgroundColor: t.bgElevated,
            border: `1px solid ${isDark ? 'rgba(148, 163, 184, 0.1)' : 'rgba(0, 0, 0, 0.06)'}`,
            borderRadius: 16,
            boxShadow: t.dialogShadow,
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
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: {
            borderBottom: `1px solid ${t.divider}`,
          },
          head: {
            color: t.textSecondary,
            fontWeight: 600,
            fontSize: 12,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          },
        },
      },
      MuiDivider: {
        styleOverrides: {
          root: {
            borderColor: t.divider,
          },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: {
            color: t.textSecondary,
            '&:hover': {
              backgroundColor: `${config.primaryColor}14`,
              color: config.primaryColor,
            },
          },
        },
      },
      MuiSwitch: {
        styleOverrides: {
          switchBase: {
            '&.Mui-checked': {
              color: config.primaryColor,
              '& + .MuiSwitch-track': {
                backgroundColor: `${config.primaryColor}66`,
              },
            },
          },
        },
      },
      MuiMenu: {
        styleOverrides: {
          paper: {
            backgroundColor: t.bgElevated,
            border: `1px solid ${isDark ? 'rgba(148, 163, 184, 0.1)' : 'rgba(0, 0, 0, 0.06)'}`,
          },
        },
      },
      MuiToggleButton: {
        styleOverrides: {
          root: {
            borderColor: t.borderAccent,
            color: t.textSecondary,
            '&.Mui-selected': {
              backgroundColor: `${config.primaryColor}1f`,
              color: config.primaryColor,
              borderColor: `${config.primaryColor}4d`,
              '&:hover': {
                backgroundColor: `${config.primaryColor}2e`,
              },
            },
          },
        },
      },
      MuiLinearProgress: {
        styleOverrides: {
          root: {
            backgroundColor: isDark ? 'rgba(148, 163, 184, 0.08)' : 'rgba(0, 0, 0, 0.06)',
            borderRadius: 6,
          },
        },
      },
      MuiSkeleton: {
        styleOverrides: {
          root: {
            backgroundColor: isDark ? 'rgba(148, 163, 184, 0.06)' : 'rgba(0, 0, 0, 0.06)',
          },
        },
      },
      MuiTooltip: {
        styleOverrides: {
          tooltip: {
            backgroundColor: t.bgElevated,
            border: `1px solid ${isDark ? 'rgba(148, 163, 184, 0.1)' : 'rgba(0, 0, 0, 0.08)'}`,
            color: t.textPrimary,
            fontSize: 12,
            borderRadius: 8,
          },
        },
      },
    },
  };
}

/**
 * Base theme options using defaults.
 */
export const baseThemeOptions: ThemeOptions = buildThemeOptions(DEFAULT_BRAND);

/**
 * Create a customized theme by merging overrides with the base config.
 */
export function createAppTheme(overrides?: ThemeOptions) {
  if (overrides) {
    return createTheme(baseThemeOptions, overrides);
  }
  return createTheme(baseThemeOptions);
}

/**
 * Create a theme from a white-label config.
 */
export function createWhiteLabelTheme(config: WhiteLabelConfig): ReturnType<typeof createTheme> {
  return createTheme(buildThemeOptions(config));
}

export { darkTokens, lightTokens };

const theme = createAppTheme();
export default theme;
