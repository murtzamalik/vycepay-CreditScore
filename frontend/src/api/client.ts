import axios, {
  type AxiosInstance,
  type AxiosError,
  type InternalAxiosRequestConfig,
  type AxiosResponse,
} from 'axios';
import type { ApiError } from '../types/common';

/**
 * Axios-based API client with auth interceptors.
 * Use this for imperative API calls outside of RTK Query.
 */
const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: inject auth tokens
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const accessToken = localStorage.getItem('accessToken');
    const apiKey = localStorage.getItem('apiKey');

    if (accessToken && config.headers) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    if (apiKey && config.headers) {
      config.headers['X-API-Key'] = apiKey;
    }

    return config;
  },
  (error: AxiosError) => Promise.reject(error)
);

// Response interceptor: normalize errors and handle 401
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError<ApiError>) => {
    if (error.response?.status === 401) {
      // Clear stored tokens and redirect to login
      localStorage.removeItem('accessToken');
      localStorage.removeItem('refreshToken');
      window.location.href = '/login';
    }

    const apiError: ApiError = {
      status: error.response?.status ?? 500,
      message:
        error.response?.data?.message ??
        error.message ??
        'An unexpected error occurred',
      details: error.response?.data?.details,
    };

    return Promise.reject(apiError);
  }
);

export default apiClient;
