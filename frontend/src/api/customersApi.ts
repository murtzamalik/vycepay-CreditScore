import { baseApi } from './baseApi';
import type { PaginatedResponse } from '../types/common';
import type {
  Customer,
  CreateCustomerRequest,
  CreateCustomerResponse,
  UpdateLicenseRequest,
  CustomerUsage,
} from '../types/customers';

export const customersApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getCustomers: builder.query<
      PaginatedResponse<Customer>,
      { page?: number; pageSize?: number; status?: string; tier?: string }
    >({
      query: (params) => ({
        url: '/admin/customers',
        params,
      }),
      providesTags: ['Customer'],
    }),

    createCustomer: builder.mutation<CreateCustomerResponse, CreateCustomerRequest>({
      query: (body) => ({
        url: '/admin/customers',
        method: 'POST',
        body,
      }),
      invalidatesTags: ['Customer'],
    }),

    updateLicense: builder.mutation<Customer, { id: string; data: UpdateLicenseRequest }>({
      query: ({ id, data }) => ({
        url: `/admin/customers/${id}/license`,
        method: 'PUT',
        body: data,
      }),
      invalidatesTags: ['Customer'],
    }),

    activateCustomer: builder.mutation<Customer, string>({
      query: (id) => ({
        url: `/admin/customers/${id}/activate`,
        method: 'POST',
      }),
      invalidatesTags: ['Customer'],
    }),

    getCustomerUsage: builder.query<CustomerUsage, string>({
      query: (id) => `/admin/customers/${id}/usage`,
    }),
  }),
});

export const {
  useGetCustomersQuery,
  useCreateCustomerMutation,
  useUpdateLicenseMutation,
  useActivateCustomerMutation,
  useGetCustomerUsageQuery,
} = customersApi;
