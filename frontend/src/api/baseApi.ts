import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import type { RootState } from '../store';

const baseQuery = fetchBaseQuery({
  baseUrl: import.meta.env.VITE_API_BASE_URL || '/v1',
  prepareHeaders: (headers, { getState }) => {
    const state = getState() as RootState;
    const { accessToken, apiKey } = state.auth;

    if (accessToken) {
      headers.set('Authorization', `Bearer ${accessToken}`);
    }
    if (apiKey) {
      headers.set('X-API-Key', apiKey);
    }
    headers.set('Content-Type', 'application/json');
    return headers;
  },
});

export const baseApi = createApi({
  reducerPath: 'api',
  baseQuery,
  tagTypes: ['Score', 'User', 'ScoreHistory', 'Customer', 'AuditLog', 'PartnerUsage', 'ApiKey', 'EmbedConfig'],
  endpoints: () => ({}),
});
