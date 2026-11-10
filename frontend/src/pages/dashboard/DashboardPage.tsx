import { useState } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  TextField,
  MenuItem,
} from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import PeopleIcon from '@mui/icons-material/People';
import AssessmentIcon from '@mui/icons-material/Assessment';
import SpeedIcon from '@mui/icons-material/Speed';
import QueryStatsIcon from '@mui/icons-material/QueryStats';
import ScoreTrendChart from '../../components/charts/ScoreTrendChart';
import QueryVolumeChart from '../../components/charts/QueryVolumeChart';
import type { ScoreHistoryEntry } from '../../types/scores';

interface KpiCardProps {
  title: string;
  value: string;
  subtitle: string;
  icon: React.ReactNode;
  color: string;
  gradient: string;
  animationClass?: string;
}

function KpiCard({ title, value, subtitle, icon, color, gradient, animationClass }: KpiCardProps) {
  return (
    <Card
      className={`vyce-card-glow ${animationClass || ''}`}
      sx={{
        height: '100%',
        minHeight: 140,
        display: 'flex',
        flexDirection: 'column',
        borderLeft: `3px solid ${color}`,
        borderRadius: '12px',
        transition: 'all 0.3s ease',
      }}
    >
      <CardContent sx={{ p: 3, flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography
              variant="body2"
              sx={{
                mb: 0.5,
                color: 'text.secondary',
                fontFamily: '"DM Sans", sans-serif',
                fontSize: '0.8rem',
              }}
            >
              {title}
            </Typography>
            <Typography
              variant="h4"
              sx={{
                fontWeight: 700,
                mb: 0.5,
                color: 'text.primary',
                fontFamily: '"Sora", sans-serif',
              }}
            >
              {value}
            </Typography>
            <Typography
              variant="caption"
              sx={{
                color: 'text.disabled',
                fontFamily: '"DM Sans", sans-serif',
                minHeight: '1.2em',
                lineHeight: 1.2,
                display: 'block',
              }}
            >
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
              color: '#0a0e1a',
              boxShadow: `0 4px 14px ${color}33`,
            }}
          >
            {icon}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}

type DateRange = '7d' | '30d' | '90d' | '6m' | '1y';

const DATE_RANGE_OPTIONS: Array<{ value: DateRange; label: string }> = [
  { value: '7d', label: 'Last 7 Days' },
  { value: '30d', label: 'Last 30 Days' },
  { value: '90d', label: 'Last 90 Days' },
  { value: '6m', label: 'Last 6 Months' },
  { value: '1y', label: 'Last Year' },
];

// Mock data keyed by date range
const MOCK_KPI: Record<DateRange, { scores: string; scoresDelta: string; partners: string; partnersDelta: string; avgScore: string; avgBand: string; uptime: string; aucRoc: string; aucDelta: string; queryVolume: string; queryDelta: string }> = {
  '7d': { scores: '2,147', scoresDelta: '+12.3% from prior week', partners: '34', partnersDelta: '0 new this week', avgScore: '658', avgBand: 'Medium Risk band', uptime: '100%', aucRoc: '0.812', aucDelta: '+0.003 from prior week', queryVolume: '8,420', queryDelta: '+5.1% from prior week' },
  '30d': { scores: '12,847', scoresDelta: '+8.2% from last month', partners: '34', partnersDelta: '3 new this month', avgScore: '654', avgBand: 'Medium Risk band', uptime: '99.97%', aucRoc: '0.809', aucDelta: '+0.007 from last month', queryVolume: '34,210', queryDelta: '+6.8% from last month' },
  '90d': { scores: '35,214', scoresDelta: '+15.6% from prior quarter', partners: '34', partnersDelta: '7 new this quarter', avgScore: '648', avgBand: 'Medium Risk band', uptime: '99.94%', aucRoc: '0.805', aucDelta: '+0.012 from prior quarter', queryVolume: '98,750', queryDelta: '+11.2% from prior quarter' },
  '6m': { scores: '62,480', scoresDelta: '+22.1% from prior 6 months', partners: '34', partnersDelta: '12 new in period', avgScore: '641', avgBand: 'Medium Risk band', uptime: '99.91%', aucRoc: '0.798', aucDelta: '+0.018 from prior period', queryVolume: '187,300', queryDelta: '+18.4% from prior period' },
  '1y': { scores: '108,352', scoresDelta: '+45.3% year over year', partners: '34', partnersDelta: '19 new this year', avgScore: '635', avgBand: 'Medium Risk band', uptime: '99.88%', aucRoc: '0.791', aucDelta: '+0.031 year over year', queryVolume: '342,800', queryDelta: '+38.7% year over year' },
};

const SAMPLE_TREND_DATA: ScoreHistoryEntry[] = [
  { date: '2025-10-01', vyceScore: 620, niqScore: 58 },
  { date: '2025-11-01', vyceScore: 645, niqScore: 60 },
  { date: '2025-12-01', vyceScore: 660, niqScore: 62 },
  { date: '2026-01-01', vyceScore: 680, niqScore: 64 },
  { date: '2026-02-01', vyceScore: 695, niqScore: 65 },
  { date: '2026-03-01', vyceScore: 710, niqScore: 67 },
];

const SAMPLE_QUERY_DATA = [
  { date: '2026-03-01', lite: 1240, pro: 380 },
  { date: '2026-03-02', lite: 1180, pro: 410 },
  { date: '2026-03-03', lite: 980, pro: 290 },
  { date: '2026-03-04', lite: 1350, pro: 420 },
  { date: '2026-03-05', lite: 1420, pro: 460 },
  { date: '2026-03-06', lite: 1280, pro: 395 },
  { date: '2026-03-07', lite: 1100, pro: 340 },
];

export default function DashboardPage() {
  const [dateRange, setDateRange] = useState<DateRange>('30d');
  const kpi = MOCK_KPI[dateRange];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography
          variant="h4"
          sx={{
            fontFamily: '"Sora", sans-serif',
            fontWeight: 700,
            color: 'text.primary',
          }}
        >
          Dashboard
        </Typography>
        <TextField
          select
          value={dateRange}
          onChange={(e) => setDateRange(e.target.value as DateRange)}
          size="small"
          sx={{ minWidth: 180 }}
        >
          {DATE_RANGE_OPTIONS.map((opt) => (
            <MenuItem key={opt.value} value={opt.value}>
              {opt.label}
            </MenuItem>
          ))}
        </TextField>
      </Box>

      <Grid container spacing={3} sx={{ mb: 4, alignItems: 'stretch' }}>
        <Grid item xs={12} sm={6} md={4} lg={2.4}>
          <KpiCard
            title="Total Scores Generated"
            value={kpi.scores}
            subtitle={kpi.scoresDelta}
            icon={<AssessmentIcon />}
            color="#00d4aa"
            gradient="linear-gradient(135deg, #00d4aa, #0ea5e9)"
            animationClass="vyce-animate vyce-animate-delay-1"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4} lg={2.4}>
          <KpiCard
            title="Active Partners"
            value={kpi.partners}
            subtitle={kpi.partnersDelta}
            icon={<PeopleIcon />}
            color="#0ea5e9"
            gradient="linear-gradient(135deg, #0ea5e9, #6366f1)"
            animationClass="vyce-animate vyce-animate-delay-2"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4} lg={2.4}>
          <KpiCard
            title="Avg VyceScore"
            value={kpi.avgScore}
            subtitle={kpi.avgBand}
            icon={<SpeedIcon />}
            color="#f59e0b"
            gradient="linear-gradient(135deg, #f59e0b, #ef4444)"
            animationClass="vyce-animate vyce-animate-delay-3"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4} lg={2.4}>
          <KpiCard
            title="Model AUC-ROC"
            value={kpi.aucRoc}
            subtitle={kpi.aucDelta}
            icon={<QueryStatsIcon />}
            color="#8b5cf6"
            gradient="linear-gradient(135deg, #8b5cf6, #ec4899)"
            animationClass="vyce-animate vyce-animate-delay-4"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4} lg={2.4}>
          <KpiCard
            title="API Uptime"
            value={kpi.uptime}
            subtitle={`${dateRange === '7d' ? 'Last 7 days' : dateRange === '30d' ? 'Last 30 days' : dateRange === '90d' ? 'Last 90 days' : dateRange === '6m' ? 'Last 6 months' : 'Last year'}`}
            icon={<TrendingUpIcon />}
            color="#10b981"
            gradient="linear-gradient(135deg, #10b981, #00d4aa)"
            animationClass="vyce-animate vyce-animate-delay-5"
          />
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <Card
            className="vyce-card-glow vyce-animate vyce-animate-delay-6"
            sx={{ borderRadius: '12px' }}
          >
            <CardContent>
              <ScoreTrendChart
                data={SAMPLE_TREND_DATA}
                title="Average Score Trend (6 months)"
                height={350}
              />
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card
            className="vyce-card-glow vyce-animate vyce-animate-delay-6"
            sx={{ borderRadius: '12px' }}
          >
            <CardContent>
              <Typography
                variant="h6"
                sx={{
                  mb: 2,
                  fontFamily: '"Sora", sans-serif',
                  fontWeight: 600,
                  color: 'text.primary',
                }}
              >
                Score Distribution
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
                {[
                  { label: 'High Risk (300-499)', pct: '18%', color: '#ef4444', glow: 'rgba(239, 68, 68, 0.4)' },
                  { label: 'Medium Risk (500-700)', pct: '52%', color: '#f59e0b', glow: 'rgba(245, 158, 11, 0.4)' },
                  { label: 'Low Risk (701-900)', pct: '30%', color: '#10b981', glow: 'rgba(16, 185, 129, 0.4)' },
                ].map((band) => (
                  <Box key={band.label}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                      <Typography
                        variant="body2"
                        sx={{
                          color: 'text.secondary',
                          fontFamily: '"DM Sans", sans-serif',
                        }}
                      >
                        {band.label}
                      </Typography>
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: 600,
                          color: 'text.primary',
                          fontFamily: '"DM Sans", sans-serif',
                        }}
                      >
                        {band.pct}
                      </Typography>
                    </Box>
                    <Box
                      sx={{
                        height: 8,
                        borderRadius: 4,
                        backgroundColor: 'divider',
                        overflow: 'hidden',
                      }}
                    >
                      <Box
                        sx={{
                          height: '100%',
                          width: band.pct,
                          backgroundColor: band.color,
                          borderRadius: 4,
                          boxShadow: `0 0 8px ${band.glow}`,
                        }}
                      />
                    </Box>
                  </Box>
                ))}
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12}>
          <Card
            className="vyce-card-glow vyce-animate vyce-animate-delay-6"
            sx={{ borderRadius: '12px' }}
          >
            <CardContent>
              <QueryVolumeChart data={SAMPLE_QUERY_DATA} title="Daily Query Volume" height={300} />
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
