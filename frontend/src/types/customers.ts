export type CustomerStatus = 'pending' | 'active' | 'suspended' | 'deactivated';
export type CustomerTier = 'lite' | 'pro' | 'enterprise';

export interface Customer {
  id: string;
  name: string;
  email: string;
  tier: CustomerTier;
  status: CustomerStatus;
  queryLimit: number;
  queriesUsed: number;
  apiKey?: string;
  createdAt: string;
  updatedAt: string;
}

export interface CreateCustomerRequest {
  name: string;
  email: string;
  tier: CustomerTier;
  queryLimit: number;
}

export interface CreateCustomerResponse {
  customer: Customer;
  apiKey: string;
}

export interface UpdateLicenseRequest {
  tier: CustomerTier;
  queryLimit: number;
}

export interface CustomerUsage {
  customerId: string;
  period: string;
  totalQueries: number;
  liteQueries: number;
  proQueries: number;
  batchQueries: number;
  dailyUsage: Array<{
    date: string;
    queries: number;
  }>;
}
