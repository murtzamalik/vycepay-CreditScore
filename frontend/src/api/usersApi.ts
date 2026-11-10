import { baseApi } from './baseApi';
import type { PaginatedResponse, UserRole } from '../types/common';
import type { User } from '../types/auth';

export interface CreateUserRequest {
  email: string;
  name: string;
  role: UserRole;
}

export interface UpdateUserRequest {
  role?: UserRole;
  status?: 'active' | 'inactive';
}

export const usersApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getUsers: builder.query<
      PaginatedResponse<User & { status: 'active' | 'inactive' }>,
      { page?: number; pageSize?: number }
    >({
      query: (params) => ({
        url: '/admin/users',
        params,
      }),
      providesTags: ['User'],
    }),

    createUser: builder.mutation<User, CreateUserRequest>({
      query: (body) => ({
        url: '/admin/users',
        method: 'POST',
        body,
      }),
      invalidatesTags: ['User'],
    }),

    updateUser: builder.mutation<User, { id: string; data: UpdateUserRequest }>({
      query: ({ id, data }) => ({
        url: `/admin/users/${id}`,
        method: 'PUT',
        body: data,
      }),
      invalidatesTags: ['User'],
    }),
  }),
});

export const {
  useGetUsersQuery,
  useCreateUserMutation,
  useUpdateUserMutation,
} = usersApi;
