export interface DailyUsageEntry {
  date: string;
  liteQueries: number;
  proQueries: number;
  batchQueries: number;
  totalQueries: number;
}

export interface PartnerUsage {
  customerId: string;
  customerName: string;
  tier: string;
  billingPeriod: string;
  totalQueries: number;
  liteQueries: number;
  proQueries: number;
  batchQueries: number;
  queryLimit: number;
  queriesRemaining: number;
  usagePercentage: number;
  dailyUsage: DailyUsageEntry[];
}

export interface UsageTrendEntry {
  period: string;
  totalQueries: number;
  liteQueries: number;
  proQueries: number;
}

export interface PartnerUsageTrend {
  customerId: string;
  months: UsageTrendEntry[];
}

export interface MonthlyStatement {
  billingPeriod: string;
  customerName: string;
  customerId: string;
  tier: string;
  status: string;
  baseFee: number;
  liteQueries: number;
  liteCost: number;
  proQueries: number;
  proCost: number;
  batchQueries: number;
  overageQueries: number;
  overageCost: number;
  totalQueries: number;
  includedQueries: number;
  totalAmount: number;
  currency: string;
  dailyBreakdown: DailyUsageEntry[];
  generatedAt: string;
}

export interface ApiKeyInfo {
  keyPrefix: string;
  createdAt: string | null;
  lastUsedAt: string | null;
}

export interface ApiKeyRotateResponse {
  apiKey: string;
  message: string;
}

export interface ApiKeyRevokeResponse {
  message: string;
}

export interface ThemeConfig {
  primaryColor?: string;
  secondaryColor?: string;
  logoUrl?: string;
  appName?: string;
  [key: string]: unknown;
}

export interface WidgetConfig {
  showNiqScore?: boolean;
  [key: string]: unknown;
}

export interface EmbedConfig {
  embedConfigId: string;
  customerId: string;
  customerToken: string;
  allowedOrigins: string[];
  themeConfig: ThemeConfig | null;
  widgetConfig: WidgetConfig | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface EmbedConfigRequest {
  allowedOrigins: string[];
  themeConfig?: ThemeConfig | null;
  widgetConfig?: WidgetConfig | null;
}

export interface PublicEmbedConfig {
  customerToken: string;
  allowedOrigins: string[];
  themeConfig: ThemeConfig | null;
  widgetConfig: WidgetConfig | null;
}
