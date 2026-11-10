import { Box, Grid, Card, CardContent, Typography, LinearProgress, Chip } from '@mui/material';
import QueryStatsIcon from '@mui/icons-material/QueryStats';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import DataUsageIcon from '@mui/icons-material/DataUsage';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import { useGetPartnerUsageQuery, useGetPartnerUsageTrendQuery } from '../../api/partnerApi';
import QueryVolumeChart from '../../components/charts/QueryVolumeChart';
import LoadingSpinner from '../../components/common/LoadingSpinner';

interface KpiCardProps {
  title: string;
  value: string;
  subtitle: string;
  icon: React.ReactNode;
  gradient: string;
  animationDelay?: string;
}

function KpiCard({ title, value, subtitle, icon, gradient, animationDelay }: KpiCardProps) {
  return (
    <Card
      className={`vyce-animate ${animationDelay ?? ''}`}
      sx={{ borderRadius: '16px' }}
    >
      <CardContent sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 0.5 }}>
              {title}
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 700, mb: 0.5, color: 'text.primary', fontFamily: '"Sora", sans-serif' }}>
              {value}
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.disabled' }}>
              {subtitle}
            </Typography>
          </Box>
          <Box
            sx={{
              width: 48,
              height: 48,
              borderRadius: '12px',
              background: gradient,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
            }}
          >
            {icon}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}

export default function PartnerDashboard() {
  const { data: usage, isLoading: usageLoading } = useGetPartnerUsageQuery();
  const { data: trend } = useGetPartnerUsageTrendQuery(6);

  if (usageLoading) {
    return <LoadingSpinner message="Loading partner dashboard..." fullPage={false} />;
  }

  const usagePct = usage?.usagePercentage ?? 0;
  const queryChartData =
    usage?.dailyUsage.map((d) => ({
      date: d.date,
      lite: d.liteQueries,
      pro: d.proQueries,
    })) ?? [];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" sx={{ color: 'text.primary', fontFamily: '"Sora", sans-serif' }}>
          Partner Dashboard
        </Typography>
        {usage && (
          <Chip
            label={`${usage.tier} Plan`}
            size="medium"
            color="primary"
            variant="outlined"
            sx={{ fontWeight: 600 }}
          />
        )}
      </Box>

      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            title="Total Queries (This Month)"
            value={usage?.totalQueries.toLocaleString() ?? '0'}
            subtitle={`${usage?.billingPeriod ?? ''}`}
            icon={<QueryStatsIcon />}
            gradient="linear-gradient(135deg, #00d4aa, #0ea5e9)"
            animationDelay="vyce-animate-delay-1"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            title="Lite Queries"
            value={usage?.liteQueries.toLocaleString() ?? '0'}
            subtitle="Score pre-screening"
            icon={<TrendingUpIcon />}
            gradient="linear-gradient(135deg, #0ea5e9, #6366f1)"
            animationDelay="vyce-animate-delay-2"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            title="Pro Queries"
            value={usage?.proQueries.toLocaleString() ?? '0'}
            subtitle="Full underwriting"
            icon={<DataUsageIcon />}
            gradient="linear-gradient(135deg, #f59e0b, #ef4444)"
            animationDelay="vyce-animate-delay-3"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            title="Queries Remaining"
            value={usage?.queriesRemaining.toLocaleString() ?? '0'}
            subtitle={`of ${usage?.queryLimit.toLocaleString() ?? '0'} monthly limit`}
            icon={<AccountBalanceIcon />}
            gradient="linear-gradient(135deg, #10b981, #00d4aa)"
            animationDelay="vyce-animate-delay-4"
          />
        </Grid>
      </Grid>

      {/* Usage bar */}
      <Card sx={{ mb: 3, borderRadius: '16px' }}>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, color: 'text.primary' }}>
              Monthly Quota Usage
            </Typography>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, color: 'text.primary' }}>
              {usagePct.toFixed(1)}%
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={Math.min(usagePct, 100)}
            sx={{
              height: 12,
              borderRadius: 6,
              '& .MuiLinearProgress-bar': {
                borderRadius: 6,
                backgroundColor: usagePct > 90 ? '#ef4444' : usagePct > 75 ? '#f59e0b' : '#10b981',
              },
            }}
          />
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
            <Typography variant="caption" sx={{ color: 'text.disabled' }}>
              {usage?.totalQueries.toLocaleString() ?? 0} used
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.disabled' }}>
              {usage?.queryLimit.toLocaleString() ?? 0} limit
            </Typography>
          </Box>
        </CardContent>
      </Card>

      {/* Query volume chart */}
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Card sx={{ borderRadius: '16px' }}>
            <CardContent>
              <QueryVolumeChart
                data={queryChartData}
                title="Daily Query Volume (Current Month)"
                height={300}
              />
            </CardContent>
          </Card>
        </Grid>

        {/* Usage trend */}
        {trend && trend.months.length > 0 && (
          <Grid item xs={12}>
            <Card sx={{ borderRadius: '16px' }}>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2, color: 'text.primary', fontFamily: '"Sora", sans-serif' }}>
                  Monthly Usage Trend
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                  {trend.months.map((m) => (
                    <Box key={m.period} sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                      <Typography variant="body2" sx={{ minWidth: 80, fontWeight: 500, color: 'text.secondary' }}>
                        {m.period}
                      </Typography>
                      <Box sx={{ flexGrow: 1 }}>
                        <LinearProgress
                          variant="determinate"
                          value={
                            usage?.queryLimit
                              ? Math.min((m.totalQueries / usage.queryLimit) * 100, 100)
                              : 0
                          }
                          sx={{
                            height: 8,
                            borderRadius: 4,
                            '& .MuiLinearProgress-bar': {
                              borderRadius: 4,
                              background: 'linear-gradient(135deg, #00d4aa, #0ea5e9)',
                            },
                          }}
                        />
                      </Box>
                      <Typography variant="body2" sx={{ minWidth: 70, textAlign: 'right', color: 'text.secondary' }}>
                        {m.totalQueries.toLocaleString()}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>
    </Box>
  );
}
