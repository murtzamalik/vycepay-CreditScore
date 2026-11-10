import { useState, useMemo } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  TextField,
  MenuItem,
  Button,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Table,
  TableBody,
  TableRow,
  TableCell,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import type { GridColDef } from '@mui/x-data-grid';
import DataTable from '../../components/common/DataTable';
import type { AuditLogEntry } from '../../types/audit';

const SAMPLE_AUDIT_LOGS: AuditLogEntry[] = [
  {
    id: '1',
    timestamp: '2026-03-08T10:32:15Z',
    userId: 'u1',
    userName: 'James Mwangi',
    action: 'score.lookup.lite',
    endpoint: '/v1/scores/lite/12345678',
    method: 'GET',
    statusCode: 200,
    ipAddress: '41.204.187.42',
    userAgent: 'Mozilla/5.0',
    responseTime: 145,
    details: 'Score lookup for national ID 12345678',
  },
  {
    id: '2',
    timestamp: '2026-03-08T10:28:03Z',
    userId: 'u1',
    userName: 'James Mwangi',
    action: 'customer.create',
    endpoint: '/v1/admin/customers',
    method: 'POST',
    statusCode: 201,
    ipAddress: '41.204.187.42',
    userAgent: 'Mozilla/5.0',
    requestBody: '{"name":"Faulu Microfinance","tier":"lite"}',
    responseTime: 230,
    details: 'Created customer Faulu Microfinance with Lite tier',
  },
  {
    id: '3',
    timestamp: '2026-03-08T09:45:22Z',
    userId: 'u3',
    userName: 'Odhiambo Ochieng',
    action: 'auth.login',
    endpoint: '/v1/auth/login',
    method: 'POST',
    statusCode: 200,
    ipAddress: '197.232.45.110',
    userAgent: 'Mozilla/5.0',
    responseTime: 89,
    details: 'Successful login',
  },
  {
    id: '4',
    timestamp: '2026-03-08T09:30:11Z',
    userId: 'u2',
    userName: 'Wanjiku Kamau',
    action: 'score.lookup.pro',
    endpoint: '/v1/scores/pro/87654321',
    method: 'GET',
    statusCode: 200,
    ipAddress: '41.89.244.18',
    userAgent: 'VyceScore-SDK/1.2',
    responseTime: 1120,
    details: 'Pro score lookup for national ID 87654321',
  },
  {
    id: '5',
    timestamp: '2026-03-07T16:20:45Z',
    userId: 'u1',
    userName: 'James Mwangi',
    action: 'user.role.update',
    endpoint: '/v1/admin/users/u4',
    method: 'PUT',
    statusCode: 200,
    ipAddress: '41.204.187.42',
    userAgent: 'Mozilla/5.0',
    requestBody: '{"role":"ReadOnly"}',
    responseTime: 156,
    details: 'Changed role for Amina Hassan to ReadOnly',
  },
  {
    id: '6',
    timestamp: '2026-03-07T15:10:33Z',
    userId: 'u3',
    userName: 'Odhiambo Ochieng',
    action: 'customer.license.update',
    endpoint: '/v1/admin/customers/2/license',
    method: 'PUT',
    statusCode: 200,
    ipAddress: '197.232.45.110',
    userAgent: 'Mozilla/5.0',
    requestBody: '{"tier":"enterprise","queryLimit":200000}',
    responseTime: 198,
    details: 'Updated KCB Group license to Enterprise tier',
  },
  {
    id: '7',
    timestamp: '2026-03-07T14:15:28Z',
    userId: 'u2',
    userName: 'Wanjiku Kamau',
    action: 'auth.login',
    endpoint: '/v1/auth/login',
    method: 'POST',
    statusCode: 200,
    ipAddress: '41.89.244.18',
    userAgent: 'Mozilla/5.0',
    responseTime: 95,
    details: 'Successful login',
  },
  {
    id: '8',
    timestamp: '2026-03-07T12:05:19Z',
    userId: 'unknown',
    userName: 'Unknown',
    action: 'auth.login',
    endpoint: '/v1/auth/login',
    method: 'POST',
    statusCode: 401,
    ipAddress: '102.68.12.55',
    userAgent: 'curl/7.88.1',
    responseTime: 42,
    details: 'Failed login attempt - invalid credentials',
  },
  {
    id: '9',
    timestamp: '2026-03-06T11:42:55Z',
    userId: 'u1',
    userName: 'James Mwangi',
    action: 'batch.submit',
    endpoint: '/v1/batches',
    method: 'POST',
    statusCode: 202,
    ipAddress: '41.204.187.42',
    userAgent: 'Mozilla/5.0',
    requestBody: '{"nationalIds":["..."],"tier":"lite"}',
    responseTime: 312,
    details: 'Submitted batch scoring job with 500 IDs',
  },
  {
    id: '10',
    timestamp: '2026-03-06T09:18:07Z',
    userId: 'u1',
    userName: 'James Mwangi',
    action: 'customer.activate',
    endpoint: '/v1/admin/customers/4/activate',
    method: 'POST',
    statusCode: 200,
    ipAddress: '41.204.187.42',
    userAgent: 'Mozilla/5.0',
    responseTime: 178,
    details: 'Activated customer Faulu Microfinance',
  },
];

const METHOD_CHIP_STYLES: Record<string, { backgroundColor: string; color: string; border: string }> = {
  GET: {
    backgroundColor: 'rgba(14, 165, 233, 0.12)',
    color: '#0ea5e9',
    border: '1px solid rgba(14, 165, 233, 0.2)',
  },
  POST: {
    backgroundColor: 'rgba(16, 185, 129, 0.12)',
    color: '#10b981',
    border: '1px solid rgba(16, 185, 129, 0.2)',
  },
  PUT: {
    backgroundColor: 'rgba(245, 158, 11, 0.12)',
    color: '#f59e0b',
    border: '1px solid rgba(245, 158, 11, 0.2)',
  },
  DELETE: {
    backgroundColor: 'rgba(239, 68, 68, 0.12)',
    color: '#ef4444',
    border: '1px solid rgba(239, 68, 68, 0.2)',
  },
  PATCH: {
    backgroundColor: 'rgba(139, 92, 246, 0.12)',
    color: '#8b5cf6',
    border: '1px solid rgba(139, 92, 246, 0.2)',
  },
};

const STATUS_CODE_STYLES: Record<string, { backgroundColor: string; color: string; border: string }> = {
  '2xx': {
    backgroundColor: 'rgba(16, 185, 129, 0.12)',
    color: '#10b981',
    border: '1px solid rgba(16, 185, 129, 0.2)',
  },
  '3xx': {
    backgroundColor: 'rgba(14, 165, 233, 0.12)',
    color: '#0ea5e9',
    border: '1px solid rgba(14, 165, 233, 0.2)',
  },
  '4xx': {
    backgroundColor: 'rgba(245, 158, 11, 0.12)',
    color: '#f59e0b',
    border: '1px solid rgba(245, 158, 11, 0.2)',
  },
  '5xx': {
    backgroundColor: 'rgba(239, 68, 68, 0.12)',
    color: '#ef4444',
    border: '1px solid rgba(239, 68, 68, 0.2)',
  },
};

function getStatusCodeStyle(code: number) {
  if (code < 300) return STATUS_CODE_STYLES['2xx'];
  if (code < 400) return STATUS_CODE_STYLES['3xx'];
  if (code < 500) return STATUS_CODE_STYLES['4xx'];
  return STATUS_CODE_STYLES['5xx'];
}

export default function AuditLogsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [actionFilter, setActionFilter] = useState('all');
  const [userFilter, setUserFilter] = useState('all');
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [selectedLog, setSelectedLog] = useState<AuditLogEntry | null>(null);

  const uniqueActions = useMemo(
    () => [...new Set(SAMPLE_AUDIT_LOGS.map((l) => l.action))].sort(),
    []
  );

  const uniqueUsers = useMemo(
    () =>
      [...new Map(SAMPLE_AUDIT_LOGS.map((l) => [l.userId, l.userName])).entries()]
        .filter(([id]) => id !== 'unknown')
        .sort((a, b) => a[1].localeCompare(b[1])),
    []
  );

  const filteredLogs = SAMPLE_AUDIT_LOGS.filter((log) => {
    if (actionFilter !== 'all' && log.action !== actionFilter) return false;
    if (userFilter !== 'all' && log.userId !== userFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        log.userName.toLowerCase().includes(q) ||
        log.action.toLowerCase().includes(q) ||
        log.endpoint.toLowerCase().includes(q) ||
        (log.details?.toLowerCase().includes(q) ?? false)
      );
    }
    return true;
  });

  const handleRowClick = (log: AuditLogEntry) => {
    setSelectedLog(log);
    setDetailDialogOpen(true);
  };

  const handleExportCsv = () => {
    const headers = [
      'Timestamp',
      'User',
      'Action',
      'Method',
      'Endpoint',
      'Status',
      'IP Address',
      'Response Time (ms)',
      'Details',
    ];
    const rows = filteredLogs.map((log) => [
      log.timestamp,
      log.userName,
      log.action,
      log.method,
      log.endpoint,
      String(log.statusCode),
      log.ipAddress,
      String(log.responseTime),
      log.details ?? '',
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map((row) => row.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(',')),
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `audit_logs_${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const columns: GridColDef[] = [
    {
      field: 'timestamp',
      headerName: 'Timestamp',
      width: 180,
      renderCell: (params) => (
        <Typography variant="body2" sx={{ color: 'text.secondary', fontFamily: '"DM Sans", sans-serif', fontSize: 13 }}>
          {new Date(params.value as string).toLocaleString('en-KE', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          })}
        </Typography>
      ),
    },
    { field: 'userName', headerName: 'User', width: 160 },
    {
      field: 'action',
      headerName: 'Action',
      width: 200,
      renderCell: (params) => (
        <Typography
          variant="body2"
          sx={{
            fontFamily: 'monospace',
            fontSize: 12,
            color: 'text.secondary',
          }}
        >
          {params.value as string}
        </Typography>
      ),
    },
    {
      field: 'method',
      headerName: 'Method',
      width: 90,
      renderCell: (params) => {
        const method = params.value as string;
        const style = METHOD_CHIP_STYLES[method] ?? {
          backgroundColor: 'rgba(100, 116, 139, 0.12)',
          color: '#64748b',
          border: '1px solid rgba(100, 116, 139, 0.2)',
        };
        return (
          <Chip
            label={method}
            size="small"
            sx={{
              fontWeight: 600,
              fontSize: 11,
              fontFamily: 'monospace',
              ...style,
            }}
          />
        );
      },
    },
    {
      field: 'statusCode',
      headerName: 'Status',
      width: 80,
      renderCell: (params) => {
        const code = params.value as number;
        const style = getStatusCodeStyle(code);
        return (
          <Chip
            label={String(code)}
            size="small"
            sx={{
              fontSize: 11,
              fontFamily: '"DM Sans", sans-serif',
              ...style,
            }}
          />
        );
      },
    },
    {
      field: 'responseTime',
      headerName: 'Time (ms)',
      width: 100,
      renderCell: (params) => (
        <Typography variant="body2" sx={{ color: 'text.secondary', fontFamily: '"DM Sans", sans-serif', fontSize: 13 }}>
          {params.value as number}ms
        </Typography>
      ),
    },
    {
      field: 'ipAddress',
      headerName: 'IP Address',
      width: 140,
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
          Audit Logs
        </Typography>
        <Button
          variant="outlined"
          startIcon={<DownloadIcon />}
          onClick={handleExportCsv}
          className="vyce-animate vyce-animate-delay-1"
        >
          Export CSV
        </Button>
      </Box>

      <Card
        className="vyce-animate vyce-animate-delay-2"
        sx={{ mb: 3, borderRadius: 3 }}
      >
        <CardContent sx={{ pb: '16px !important' }}>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <TextField
              label="Search"
              placeholder="Search logs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              size="small"
              sx={{ minWidth: 250, flexGrow: 1 }}
            />
            <TextField
              select
              label="Action"
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              size="small"
              sx={{ minWidth: 200 }}
            >
              <MenuItem value="all">All Actions</MenuItem>
              {uniqueActions.map((action) => (
                <MenuItem key={action} value={action}>
                  {action}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label="User"
              value={userFilter}
              onChange={(e) => setUserFilter(e.target.value)}
              size="small"
              sx={{ minWidth: 180 }}
            >
              <MenuItem value="all">All Users</MenuItem>
              {uniqueUsers.map(([id, name]) => (
                <MenuItem key={id} value={id}>
                  {name}
                </MenuItem>
              ))}
            </TextField>
          </Box>
        </CardContent>
      </Card>

      <Card
        className="vyce-animate vyce-animate-delay-3"
        sx={{ borderRadius: 3 }}
      >
        <CardContent>
          <DataTable
            rows={filteredLogs}
            columns={columns}
            pageSize={10}
            onRowClick={handleRowClick}
          />
        </CardContent>
      </Card>

      {/* Detail Dialog */}
      <Dialog
        open={detailDialogOpen}
        onClose={() => setDetailDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ color: 'text.primary', fontFamily: '"Sora", sans-serif', fontWeight: 600 }}>
          Audit Log Detail
        </DialogTitle>
        <DialogContent>
          {selectedLog && (
            <Table size="small">
              <TableBody>
                <DetailRow label="Timestamp" value={new Date(selectedLog.timestamp).toLocaleString('en-KE')} />
                <DetailRow label="User" value={`${selectedLog.userName} (${selectedLog.userId})`} />
                <DetailRow label="Action" value={selectedLog.action} />
                <DetailRow label="Method" value={selectedLog.method} />
                <DetailRow label="Endpoint" value={selectedLog.endpoint} />
                <DetailRow label="Status Code" value={String(selectedLog.statusCode)} />
                <DetailRow label="Response Time" value={`${selectedLog.responseTime}ms`} />
                <DetailRow label="IP Address" value={selectedLog.ipAddress} />
                <DetailRow label="User Agent" value={selectedLog.userAgent} />
                {selectedLog.requestBody && (
                  <DetailRow label="Request Body" value={selectedLog.requestBody} mono />
                )}
                {selectedLog.details && (
                  <DetailRow label="Details" value={selectedLog.details} />
                )}
              </TableBody>
            </Table>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button
            onClick={() => setDetailDialogOpen(false)}
            sx={{ color: 'text.secondary' }}
          >
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

function DetailRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <TableRow>
      <TableCell
        sx={{
          fontWeight: 600,
          width: 160,
          color: 'text.secondary',
          fontFamily: '"DM Sans", sans-serif',
        }}
      >
        {label}
      </TableCell>
      <TableCell
        sx={{
          fontFamily: mono ? 'monospace' : '"DM Sans", sans-serif',
          fontSize: mono ? 12 : 'inherit',
          wordBreak: 'break-all',
          color: 'text.primary',
        }}
      >
        {value}
      </TableCell>
    </TableRow>
  );
}
