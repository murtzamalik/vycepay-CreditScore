import { baseApi } from './baseApi';
import type { LoginRequest, User } from '../types/auth';

/** Raw shape returned by the backend POST /v1/auth/login */
interface BackendLoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

/** Decoded JWT payload (only the fields we need) */
interface JwtPayload {
  sub: string;
  role: string;
  exp: number;
}

function decodeJwtPayload(token: string): JwtPayload {
  const base64 = token.split('.')[1];
  const json = atob(base64);
  return JSON.parse(json);
}

/** Normalised response used by the auth slice */
export interface NormalisedLoginResponse {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  user: User;
}

export const authApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    login: builder.mutation<NormalisedLoginResponse, LoginRequest>({
      query: (credentials) => ({
        url: '/auth/login',
        method: 'POST',
        body: credentials,
      }),
      transformResponse: (raw: BackendLoginResponse): NormalisedLoginResponse => {
        const payload = decodeJwtPayload(raw.access_token);
        return {
          accessToken: raw.access_token,
          refreshToken: raw.refresh_token,
          expiresIn: raw.expires_in,
          user: {
            id: payload.sub,
            email: '',          // populated after getMe
            name: '',           // populated after getMe
            role: payload.role as User['role'],
            organizationId: '',
            organizationName: '',
            createdAt: '',
            lastLoginAt: null,
          },
        };
      },
    }),
    refreshToken: builder.mutation<BackendLoginResponse, { refresh_token: string }>({
      query: (body) => ({
        url: '/auth/refresh',
        method: 'POST',
        body,
      }),
    }),
    getMe: builder.query<User, void>({
      query: () => '/auth/me',
    }),
    requestPasswordReset: builder.mutation<{ message: string }, { email: string }>({
      query: (body) => ({
        url: '/auth/password-reset',
        method: 'POST',
        body,
      }),
    }),
  }),
});

export const {
  useLoginMutation,
  useRefreshTokenMutation,
  useGetMeQuery,
  useRequestPasswordResetMutation,
} = authApi;
