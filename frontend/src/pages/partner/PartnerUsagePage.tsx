import { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  MenuItem,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Button,
  Chip,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import {
  useGetPartnerUsageQuery,
  useGetPartnerUsageReportQuery,
} from '../../api/partnerApi';
import QueryVolumeChart from '../../components/charts/QueryVolumeChart';
import LoadingSpinner from '../../components/common/LoadingSpinner';

function getRecentMonths(count: number): string[] {
  const months: string[] = [];
  const now = new Date();
  for (let i = 0; i < count; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    months.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`);
  }
  return months;
}

export default function PartnerUsagePage() {
  const recentMonths = getRecentMonths(12);
  const [selectedMonth, setSelectedMonth] = useState(recentMonths[0]);

  const { isLoading: usageLoading } = useGetPartnerUsageQuery();
  const { data: report, isLoading: reportLoading } = useGetPartnerUsageReportQuery(selectedMonth);

  if (usageLoading) {
    return <LoadingSpinner message="Loading usage data..." fullPage={false} />;
  }

  const handleDownloadCsv = () => {
    if (!report) return;

    const headers = 'Date,Lite Queries,Pro Queries,Batch Queries,Total Queries\n';
    const rows = report.dailyBreakdown
      .map((d) => `${d.date},${d.liteQueries},${d.proQueries},${d.batchQueries},${d.totalQueries}`)
      .join('\n');

    const csv = headers + rows;
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `usage-report-${selectedMonth}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const chartData =
    report?.dailyBreakdown.map((d) => ({
      date: d.date,
      lite: d.liteQueries,
      pro: d.proQueries,
    })) ?? [];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" sx={{ color: 'text.primary', fontFamily: '"Sora", sans-serif' }}>
          Usage Reports
        </Typography>
        <TextField
          select
          value={selectedMonth}
          onChange={(e) => setSelectedMonth(e.target.value)}
          size="small"
          sx={{ minWidth: 180 }}
        >
          {recentMonths.map((m) => (
            <MenuItem key={m} value={m}>
              {m}
            </MenuItem>
          ))}
        </TextField>
      </Box>

      {/* Summary cards */}
      {report && (
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={6} md={3}>
            <Card className="vyce-animate vyce-animate-delay-1" sx={{ borderRadius: '16px' }}>
              <CardContent>
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>Total Queries</Typography>
                <Typography variant="h5" sx={{ fontWeight: 700, color: 'text.primary' }}>
                  {report.totalQueries.toLocaleString()}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card className="vyce-animate vyce-animate-delay-2" sx={{ borderRadius: '16px' }}>
              <CardContent>
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>Included in Plan</Typography>
                <Typography variant="h5" sx={{ fontWeight: 700, color: 'text.primary' }}>
                  {report.includedQueries.toLocaleString()}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card className="vyce-animate vyce-animate-delay-3" sx={{ borderRadius: '16px' }}>
              <CardContent>
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>Overage Queries</Typography>
                <Typography variant="h5" sx={{ fontWeight: 700, color: report.overageQueries > 0 ? 'error.main' : 'text.primary' }}>
                  {report.overageQueries.toLocaleString()}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card className="vyce-animate vyce-animate-delay-4" sx={{ borderRadius: '16px' }}>
              <CardContent>
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>Total Amount</Typography>
                <Typography variant="h5" sx={{ fontWeight: 700, color: 'text.primary' }}>
                  {report.currency} {report.totalAmount.toLocaleString()}
                </Typography>
                <Chip
                  label={report.status}
                  size="small"
                  sx={{
                    mt: 0.5,
                    backgroundColor:
                      report.status === 'PAID' ? 'rgba(16, 185, 129, 0.15)' :
                      report.status === 'OVERDUE' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(148, 163, 184, 0.1)',
                    color:
                      report.status === 'PAID' ? '#10b981' :
                      report.status === 'OVERDUE' ? '#ef4444' : 'text.secondary',
                    border: `1px solid ${
                      report.status === 'PAID' ? 'rgba(16, 185, 129, 0.3)' :
                      report.status === 'OVERDUE' ? 'rgba(239, 68, 68, 0.3)' : 'rgba(148, 163, 184, 0.2)'
                    }`,
                  }}
                />
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Billing breakdown */}
      {report && (
        <Card sx={{ borderRadius: '16px', mb: 3 }}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2, color: 'text.primary', fontFamily: '"Sora", sans-serif' }}>
              Billing Breakdown ({selectedMonth})
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableBody>
                  <TableRow>
                    <TableCell sx={{ color: 'text.secondary' }}>Base Fee ({report.tier})</TableCell>
                    <TableCell align="right" sx={{ color: 'text.primary' }}>
                      {report.currency} {report.baseFee.toLocaleString()}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell sx={{ color: 'text.secondary' }}>Lite Queries ({report.liteQueries.toLocaleString()} x KES 3)</TableCell>
                    <TableCell align="right" sx={{ color: 'text.primary' }}>
                      {report.currency} {report.liteCost.toLocaleString()}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell sx={{ color: 'text.secondary' }}>Pro Queries ({report.proQueries.toLocaleString()} x KES 15)</TableCell>
                    <TableCell align="right" sx={{ color: 'text.primary' }}>
                      {report.currency} {report.proCost.toLocaleString()}
                    </TableCell>
                  </TableRow>
                  {report.overageQueries > 0 && (
                    <TableRow>
                      <TableCell sx={{ color: 'error.main' }}>
                        Overage ({report.overageQueries.toLocaleString()} queries)
                      </TableCell>
                      <TableCell align="right" sx={{ color: 'error.main' }}>
                        {report.currency} {report.overageCost.toLocaleString()}
                      </TableCell>
                    </TableRow>
                  )}
                  <TableRow sx={{ '& td': { fontWeight: 700, borderTop: '2px solid', borderTopColor: 'primary.main', borderBottom: 'none' } }}>
                    <TableCell sx={{ color: 'text.primary' }}>Total</TableCell>
                    <TableCell align="right" sx={{ color: 'primary.main' }}>
                      {report.currency} {report.totalAmount.toLocaleString()}
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      {/* Daily chart */}
      {chartData.length > 0 && (
        <Card sx={{ borderRadius: '16px', mb: 3 }}>
          <CardContent>
            <QueryVolumeChart
              data={chartData}
              title={`Daily Query Volume (${selectedMonth})`}
              height={300}
            />
          </CardContent>
        </Card>
      )}

      {/* Daily breakdown table */}
      {report && report.dailyBreakdown.length > 0 && (
        <Card sx={{ borderRadius: '16px' }}>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" sx={{ color: 'text.primary', fontFamily: '"Sora", sans-serif' }}>
                Daily Breakdown
              </Typography>
              <Button
                variant="outlined"
                size="small"
                startIcon={<DownloadIcon />}
                onClick={handleDownloadCsv}
              >
                Download CSV
              </Button>
            </Box>
            <TableContainer
              component={Paper}
              variant="outlined"
              sx={{ borderRadius: '12px' }}
            >
              <Table size="small">
                <TableHead>
                  <TableRow>
                    {['Date', 'Lite', 'Pro', 'Batch', 'Total'].map((header) => (
                      <TableCell
                        key={header}
                        align={header === 'Date' ? 'left' : 'right'}
                        sx={{ fontWeight: 600 }}
                      >
                        {header}
                      </TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {report.dailyBreakdown.map((d) => (
                    <TableRow key={d.date}>
                      <TableCell sx={{ color: 'text.primary' }}>{d.date}</TableCell>
                      <TableCell align="right" sx={{ color: 'text.secondary' }}>{d.liteQueries.toLocaleString()}</TableCell>
                      <TableCell align="right" sx={{ color: 'text.secondary' }}>{d.proQueries.toLocaleString()}</TableCell>
                      <TableCell align="right" sx={{ color: 'text.secondary' }}>{d.batchQueries.toLocaleString()}</TableCell>
                      <TableCell align="right" sx={{ color: 'text.primary', fontWeight: 500 }}>{d.totalQueries.toLocaleString()}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      {reportLoading && <LoadingSpinner message="Loading report..." fullPage={false} />}
    </Box>
  );
}
