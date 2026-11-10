import { createContext, useContext, useState, useMemo, useCallback, useEffect, type ReactNode } from 'react';
import { ThemeProvider } from '@mui/material/styles';
import { createWhiteLabelTheme } from './index';
import type { WhiteLabelConfig, ThemeMode } from '../types/theme';

const DEFAULT_CONFIG: WhiteLabelConfig = {
  primaryColor: '#00d4aa',
  secondaryColor: '#0ea5e9',
  appName: 'VyceScore',
  mode: 'dark',
};

interface WhiteLabelContextValue {
  config: WhiteLabelConfig;
  updateConfig: (config: Partial<WhiteLabelConfig>) => void;
  toggleMode: () => void;
  isDark: boolean;
}

const WhiteLabelContext = createContext<WhiteLabelContextValue>({
  config: DEFAULT_CONFIG,
  updateConfig: () => {},
  toggleMode: () => {},
  isDark: true,
});

export function useWhiteLabel() {
  return useContext(WhiteLabelContext);
}

interface WhiteLabelProviderProps {
  children: ReactNode;
  initialConfig?: Partial<WhiteLabelConfig>;
}

export function WhiteLabelProvider({ children, initialConfig }: WhiteLabelProviderProps) {
  const [config, setConfig] = useState<WhiteLabelConfig>(() => {
    const saved = localStorage.getItem('whiteLabelConfig');
    if (saved) {
      try {
        return { ...DEFAULT_CONFIG, ...JSON.parse(saved) };
      } catch {
        // ignore parse errors
      }
    }
    return { ...DEFAULT_CONFIG, ...initialConfig };
  });

  // Sync data-theme attribute on <html> for CSS overrides
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', config.mode);
  }, [config.mode]);

  const theme = useMemo(() => createWhiteLabelTheme(config), [config]);

  const updateConfig = useCallback((partial: Partial<WhiteLabelConfig>) => {
    setConfig((prev) => {
      const updated = { ...prev, ...partial };
      localStorage.setItem('whiteLabelConfig', JSON.stringify(updated));
      return updated;
    });
  }, []);

  const toggleMode = useCallback(() => {
    setConfig((prev) => {
      const newMode: ThemeMode = prev.mode === 'dark' ? 'light' : 'dark';
      const updated = { ...prev, mode: newMode };
      localStorage.setItem('whiteLabelConfig', JSON.stringify(updated));
      return updated;
    });
  }, []);

  const isDark = config.mode === 'dark';

  const contextValue = useMemo(
    () => ({ config, updateConfig, toggleMode, isDark }),
    [config, updateConfig, toggleMode, isDark]
  );

  return (
    <WhiteLabelContext.Provider value={contextValue}>
      <ThemeProvider theme={theme}>{children}</ThemeProvider>
    </WhiteLabelContext.Provider>
  );
}
