import { useState } from 'react';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Chip,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Alert,
  Snackbar,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import type { GridColDef } from '@mui/x-data-grid';
import DataTable from '../../components/common/DataTable';
import type { Customer, CustomerStatus, CustomerTier } from '../../types/customers';

const STATUS_CHIP_STYLES: Record<CustomerStatus, { backgroundColor: string; color: string; border: string }> = {
  pending: {
    backgroundColor: 'rgba(245, 158, 11, 0.12)',
    color: '#f59e0b',
    border: '1px solid rgba(245, 158, 11, 0.2)',
  },
  active: {
    backgroundColor: 'rgba(16, 185, 129, 0.12)',
    color: '#10b981',
    border: '1px solid rgba(16, 185, 129, 0.2)',
  },
  suspended: {
    backgroundColor: 'rgba(239, 68, 68, 0.12)',
    color: '#ef4444',
    border: '1px solid rgba(239, 68, 68, 0.2)',
  },
  deactivated: {
    backgroundColor: 'rgba(100, 116, 139, 0.12)',
    color: '#64748b',
    border: '1px solid rgba(100, 116, 139, 0.2)',
  },
};

const TIER_CHIP_STYLES: Record<CustomerTier, { backgroundColor: string; color: string; border: string }> = {
  lite: {
    backgroundColor: 'rgba(0, 212, 170, 0.12)',
    color: '#00d4aa',
    border: '1px solid rgba(0, 212, 170, 0.2)',
  },
  pro: {
    backgroundColor: 'rgba(14, 165, 233, 0.12)',
    color: '#0ea5e9',
    border: '1px solid rgba(14, 165, 233, 0.2)',
  },
  enterprise: {
    backgroundColor: 'rgba(139, 92, 246, 0.12)',
    color: '#8b5cf6',
    border: '1px solid rgba(139, 92, 246, 0.2)',
  },
};

const SAMPLE_CUSTOMERS: Customer[] = [
  {
    id: '1',
    name: 'Equity Bank Kenya',
    email: 'api@equitybank.co.ke',
    tier: 'pro',
    status: 'active',
    queryLimit: 50000,
    queriesUsed: 32450,
    createdAt: '2025-06-15T10:00:00Z',
    updatedAt: '2026-03-01T08:30:00Z',
  },
  {
    id: '2',
    name: 'KCB Group',
    email: 'integration@kcbgroup.com',
    tier: 'enterprise',
    status: 'active',
    queryLimit: 200000,
    queriesUsed: 145230,
    createdAt: '2025-08-20T14:00:00Z',
    updatedAt: '2026-03-05T11:15:00Z',
  },
  {
    id: '3',
    name: 'Safaricom M-Pesa',
    email: 'partners@safaricom.co.ke',
    tier: 'pro',
    status: 'active',
    queryLimit: 100000,
    queriesUsed: 87600,
    createdAt: '2025-09-10T09:00:00Z',
    updatedAt: '2026-03-07T16:45:00Z',
  },
  {
    id: '4',
    name: 'Faulu Microfinance',
    email: 'tech@faulu.co.ke',
    tier: 'lite',
    status: 'pending',
    queryLimit: 10000,
    queriesUsed: 0,
    createdAt: '2026-03-06T12:00:00Z',
    updatedAt: '2026-03-06T12:00:00Z',
  },
  {
    id: '5',
    name: 'NCBA Bank',
    email: 'digital@ncbagroup.com',
    tier: 'pro',
    status: 'suspended',
    queryLimit: 50000,
    queriesUsed: 49800,
    createdAt: '2025-11-01T08:00:00Z',
    updatedAt: '2026-02-28T14:30:00Z',
  },
];

interface AddCustomerForm {
  name: string;
  email: string;
  tier: CustomerTier;
  queryLimit: number;
}

interface LicenseForm {
  tier: CustomerTier;
  queryLimit: number;
}

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>(SAMPLE_CUSTOMERS);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [tierFilter, setTierFilter] = useState<string>('all');
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [licenseDialogOpen, setLicenseDialogOpen] = useState(false);
  const [apiKeyDialogOpen, setApiKeyDialogOpen] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [generatedApiKey, setGeneratedApiKey] = useState('');
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });

  const [addForm, setAddForm] = useState<AddCustomerForm>({
    name: '',
    email: '',
    tier: 'lite',
    queryLimit: 10000,
  });

  const [licenseForm, setLicenseForm] = useState<LicenseForm>({
    tier: 'lite',
    queryLimit: 10000,
  });

  const filteredCustomers = customers.filter((c) => {
    if (statusFilter !== 'all' && c.status !== statusFilter) return false;
    if (tierFilter !== 'all' && c.tier !== tierFilter) return false;
    return true;
  });

  const handleAddCustomer = () => {
    const newCustomer: Customer = {
      id: String(Date.now()),
      name: addForm.name,
      email: addForm.email,
      tier: addForm.tier,
      status: 'pending',
      queryLimit: addForm.queryLimit,
      queriesUsed: 0,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    setCustomers([...customers, newCustomer]);

    const fakeApiKey = `vs_${addForm.tier}_${crypto.randomUUID().replace(/-/g, '').slice(0, 32)}`;
    setGeneratedApiKey(fakeApiKey);
    setAddDialogOpen(false);
    setApiKeyDialogOpen(true);
    setAddForm({ name: '', email: '', tier: 'lite', queryLimit: 10000 });
  };

  const handleActivate = (customer: Customer) => {
    setCustomers(
      customers.map((c) =>
        c.id === customer.id ? { ...c, status: 'active' as CustomerStatus, updatedAt: new Date().toISOString() } : c
      )
    );
    setSnackbar({ open: true, message: `${customer.name} has been activated.`, severity: 'success' });
  };

  const handleOpenLicenseDialog = (customer: Customer) => {
    setSelectedCustomer(customer);
    setLicenseForm({ tier: customer.tier, queryLimit: customer.queryLimit });
    setLicenseDialogOpen(true);
  };

  const handleUpdateLicense = () => {
    if (!selectedCustomer) return;
    setCustomers(
      customers.map((c) =>
        c.id === selectedCustomer.id
          ? { ...c, tier: licenseForm.tier, queryLimit: licenseForm.queryLimit, updatedAt: new Date().toISOString() }
          : c
      )
    );
    setLicenseDialogOpen(false);
    setSnackbar({ open: true, message: 'License updated successfully.', severity: 'success' });
  };

  const handleCopyApiKey = async () => {
    await navigator.clipboard.writeText(generatedApiKey);
    setSnackbar({ open: true, message: 'API key copied to clipboard.', severity: 'success' });
  };

  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'Customer Name',
      flex: 1.5,
      minWidth: 180,
    },
    {
      field: 'email',
      headerName: 'Email',
      flex: 1.5,
      minWidth: 200,
    },
    {
      field: 'tier',
      headerName: 'Tier',
      width: 120,
      renderCell: (params) => {
        const style = TIER_CHIP_STYLES[params.value as CustomerTier];
        return (
          <Chip
            label={(params.value as string).toUpperCase()}
            size="small"
            sx={{
              fontWeight: 600,
              fontSize: 11,
              fontFamily: '"DM Sans", sans-serif',
              ...style,
            }}
          />
        );
      },
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => {
        const style = STATUS_CHIP_STYLES[params.value as CustomerStatus];
        return (
          <Chip
            label={params.value as string}
            size="small"
            sx={{
              fontSize: 11,
              textTransform: 'capitalize',
              fontFamily: '"DM Sans", sans-serif',
              ...style,
            }}
          />
        );
      },
    },
    {
      field: 'queryLimit',
      headerName: 'Query Limit',
      width: 120,
      renderCell: (params) => (
        <Typography variant="body2" sx={{ color: 'text.primary', fontFamily: '"DM Sans", sans-serif' }}>
          {(params.value as number).toLocaleString()}
        </Typography>
      ),
    },
    {
      field: 'queriesUsed',
      headerName: 'Used',
      width: 100,
      renderCell: (params) => (
        <Typography variant="body2" sx={{ color: 'text.secondary', fontFamily: '"DM Sans", sans-serif' }}>
          {(params.value as number).toLocaleString()}
        </Typography>
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 120,
      sortable: false,
      renderCell: (params) => {
        const customer = params.row as Customer;
        return (
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            <Tooltip title="Configure License">
              <IconButton
                size="small"
                onClick={() => handleOpenLicenseDialog(customer)}
              >
                <EditIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            {customer.status === 'pending' && (
              <Tooltip title="Activate">
                <IconButton
                  size="small"
                  onClick={() => handleActivate(customer)}
                  sx={{ color: 'success.main' }}
                >
                  <CheckCircleIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
          </Box>
        );
      },
    },
  ];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography
          variant="h4"
          className="vyce-animate"
          sx={{
            fontFamily: '"Sora", sans-serif',
            fontWeight: 700,
            color: 'text.primary',
          }}
        >
          Customer Management
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setAddDialogOpen(true)}
          className="vyce-animate vyce-animate-delay-1"
        >
          Add Customer
        </Button>
      </Box>

      <Card
        className="vyce-animate vyce-animate-delay-2"
        sx={{ mb: 3, borderRadius: 3 }}
      >
        <CardContent sx={{ pb: '16px !important' }}>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <TextField
              select
              label="Status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              size="small"
              sx={{ minWidth: 150 }}
            >
              <MenuItem value="all">All Statuses</MenuItem>
              <MenuItem value="pending">Pending</MenuItem>
              <MenuItem value="active">Active</MenuItem>
              <MenuItem value="suspended">Suspended</MenuItem>
              <MenuItem value="deactivated">Deactivated</MenuItem>
            </TextField>
            <TextField
              select
              label="Tier"
              value={tierFilter}
              onChange={(e) => setTierFilter(e.target.value)}
              size="small"
              sx={{ minWidth: 150 }}
            >
              <MenuItem value="all">All Tiers</MenuItem>
              <MenuItem value="lite">Lite</MenuItem>
              <MenuItem value="pro">Pro</MenuItem>
              <MenuItem value="enterprise">Enterprise</MenuItem>
            </TextField>
          </Box>
        </CardContent>
      </Card>

      <Card
        className="vyce-animate vyce-animate-delay-3"
        sx={{ borderRadius: 3 }}
      >
        <CardContent>
          <DataTable rows={filteredCustomers} columns={columns} pageSize={10} />
        </CardContent>
      </Card>

      {/* Add Customer Dialog */}
      <Dialog open={addDialogOpen} onClose={() => setAddDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ color: 'text.primary', fontFamily: '"Sora", sans-serif', fontWeight: 600 }}>
          Add New Customer
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
            <TextField label="Customer Name" value={addForm.name} onChange={(e) => setAddForm({ ...addForm, name: e.target.value })} fullWidth required />
            <TextField label="Email" type="email" value={addForm.email} onChange={(e) => setAddForm({ ...addForm, email: e.target.value })} fullWidth required />
            <TextField select label="Tier" value={addForm.tier} onChange={(e) => setAddForm({ ...addForm, tier: e.target.value as CustomerTier })} fullWidth>
              <MenuItem value="lite">Lite</MenuItem>
              <MenuItem value="pro">Pro</MenuItem>
              <MenuItem value="enterprise">Enterprise</MenuItem>
            </TextField>
            <TextField label="Query Limit" type="number" value={addForm.queryLimit} onChange={(e) => setAddForm({ ...addForm, queryLimit: Number(e.target.value) })} fullWidth inputProps={{ min: 1000, step: 1000 }} />
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setAddDialogOpen(false)} sx={{ color: 'text.secondary' }}>Cancel</Button>
          <Button variant="contained" onClick={handleAddCustomer} disabled={!addForm.name || !addForm.email}>
            Create Customer
          </Button>
        </DialogActions>
      </Dialog>

      {/* Configure License Dialog */}
      <Dialog open={licenseDialogOpen} onClose={() => setLicenseDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ color: 'text.primary', fontFamily: '"Sora", sans-serif', fontWeight: 600 }}>
          Configure License {selectedCustomer ? `- ${selectedCustomer.name}` : ''}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
            <TextField select label="Tier" value={licenseForm.tier} onChange={(e) => setLicenseForm({ ...licenseForm, tier: e.target.value as CustomerTier })} fullWidth>
              <MenuItem value="lite">Lite</MenuItem>
              <MenuItem value="pro">Pro</MenuItem>
              <MenuItem value="enterprise">Enterprise</MenuItem>
            </TextField>
            <TextField label="Query Limit" type="number" value={licenseForm.queryLimit} onChange={(e) => setLicenseForm({ ...licenseForm, queryLimit: Number(e.target.value) })} fullWidth inputProps={{ min: 1000, step: 1000 }} />
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setLicenseDialogOpen(false)} sx={{ color: 'text.secondary' }}>Cancel</Button>
          <Button variant="contained" onClick={handleUpdateLicense}>
            Update License
          </Button>
        </DialogActions>
      </Dialog>

      {/* API Key Display Dialog */}
      <Dialog open={apiKeyDialogOpen} onClose={() => setApiKeyDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ color: 'text.primary', fontFamily: '"Sora", sans-serif', fontWeight: 600 }}>
          Customer Created Successfully
        </DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            This API key will only be shown once. Please copy it now and store it securely.
          </Alert>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              p: 2,
              backgroundColor: 'background.default',
              borderRadius: 1,
              border: 1,
              borderColor: 'divider',
              fontFamily: 'monospace',
              fontSize: 13,
              wordBreak: 'break-all',
            }}
          >
            <Typography
              variant="body2"
              sx={{
                fontFamily: 'monospace',
                flexGrow: 1,
                wordBreak: 'break-all',
                color: 'primary.main',
              }}
            >
              {generatedApiKey}
            </Typography>
            <Tooltip title="Copy API Key">
              <IconButton size="small" onClick={handleCopyApiKey}>
                <ContentCopyIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button variant="contained" onClick={() => setApiKeyDialogOpen(false)}>
            Done
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          variant="filled"
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
