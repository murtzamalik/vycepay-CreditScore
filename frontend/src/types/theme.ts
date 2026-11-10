export type ThemeMode = 'light' | 'dark';

export interface WhiteLabelConfig {
  primaryColor: string;
  secondaryColor: string;
  logoUrl?: string;
  appName: string;
  mode: ThemeMode;
}
