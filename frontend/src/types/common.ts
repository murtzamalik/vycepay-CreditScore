export interface ApiError {
  status: number;
  message: string;
  details?: Record<string, string[]>;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export type UserRole = 'Admin' | 'Operator' | 'Partner' | 'ReadOnly';
