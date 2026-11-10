import { baseApi } from './baseApi';
import type { PaginatedResponse } from '../types/common';
import type { AuditLogEntry, AuditLogFilters } from '../types/audit';

export const auditApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getAuditLogs: builder.query<PaginatedResponse<AuditLogEntry>, AuditLogFilters>({
      query: (params) => ({
        url: '/admin/audit-logs',
        params,
      }),
      providesTags: ['AuditLog'],
    }),
  }),
});

export const { useGetAuditLogsQuery } = auditApi;
