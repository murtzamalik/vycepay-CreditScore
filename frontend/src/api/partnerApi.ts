import { baseApi } from './baseApi';
import type {
  PartnerUsage,
  PartnerUsageTrend,
  MonthlyStatement,
  ApiKeyInfo,
  ApiKeyRotateResponse,
  ApiKeyRevokeResponse,
  EmbedConfig,
  EmbedConfigRequest,
  PublicEmbedConfig,
} from '../types/partner';

export const partnerApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // --- Partner usage ---
    getPartnerUsage: builder.query<PartnerUsage, void>({
      query: () => '/partner/usage',
      providesTags: ['PartnerUsage'],
    }),

    getPartnerUsageReport: builder.query<MonthlyStatement, string>({
      query: (month) => `/partner/usage/report/${month}`,
      providesTags: (_result, _error, month) => [
        { type: 'PartnerUsage', id: month },
      ],
    }),

    getPartnerUsageTrend: builder.query<PartnerUsageTrend, number | void>({
      query: (months = 6) => ({
        url: '/partner/usage/trend',
        params: { months },
      }),
      providesTags: ['PartnerUsage'],
    }),

    // --- API Key management ---
    getApiKeyInfo: builder.query<ApiKeyInfo, void>({
      query: () => '/partner/api-keys/info',
      providesTags: ['ApiKey'],
    }),

    rotateApiKey: builder.mutation<ApiKeyRotateResponse, void>({
      query: () => ({
        url: '/partner/api-keys/rotate',
        method: 'POST',
      }),
      invalidatesTags: ['ApiKey'],
    }),

    revokeApiKey: builder.mutation<ApiKeyRevokeResponse, void>({
      query: () => ({
        url: '/partner/api-keys/revoke',
        method: 'POST',
      }),
      invalidatesTags: ['ApiKey'],
    }),

    // --- Admin billing ---
    getCustomerStatement: builder.query<
      MonthlyStatement,
      { customerId: string; month: string }
    >({
      query: ({ customerId, month }) =>
        `/admin/billing/customers/${customerId}/statement/${month}`,
    }),

    // --- Embed config (admin) ---
    saveEmbedConfig: builder.mutation<
      EmbedConfig,
      { customerId: string; data: EmbedConfigRequest }
    >({
      query: ({ customerId, data }) => ({
        url: `/admin/customers/${customerId}/embed-config`,
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['EmbedConfig'],
    }),

    // --- Embed config (public) ---
    getPublicEmbedConfig: builder.query<PublicEmbedConfig, string>({
      query: (customerToken) => `/embed/config/${customerToken}`,
      providesTags: ['EmbedConfig'],
    }),
  }),
});

export const {
  useGetPartnerUsageQuery,
  useGetPartnerUsageReportQuery,
  useGetPartnerUsageTrendQuery,
  useGetApiKeyInfoQuery,
  useRotateApiKeyMutation,
  useRevokeApiKeyMutation,
  useGetCustomerStatementQuery,
  useSaveEmbedConfigMutation,
  useGetPublicEmbedConfigQuery,
} = partnerApi;
