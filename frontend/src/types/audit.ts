export interface AuditLogEntry {
  id: string;
  timestamp: string;
  userId: string;
  userName: string;
  action: string;
  endpoint: string;
  method: string;
  statusCode: number;
  ipAddress: string;
  userAgent: string;
  requestBody?: string;
  responseTime: number;
  details?: string;
}

export interface AuditLogFilters {
  startDate?: string;
  endDate?: string;
  userId?: string;
  action?: string;
  endpoint?: string;
  page: number;
  pageSize: number;
}
