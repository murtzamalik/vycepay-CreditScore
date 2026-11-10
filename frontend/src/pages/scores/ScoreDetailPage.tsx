import { Box, Card, CardContent, Typography, Chip, Grid, Skeleton } from '@mui/material';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import { useParams } from 'react-router-dom';
import ScoreGauge from '../../components/charts/ScoreGauge';
import ScoreTrendChart from '../../components/charts/ScoreTrendChart';
import { useLazyGetProScoreQuery, useGetScoreHistoryQuery } from '../../api/scoresApi';
import { formatPercentage } from '../../utils/formatters';
import type { RiskDriver } from '../../types/scores';
import { useEffect } from 'react';

export default function ScoreDetailPage() {
  const { nationalId } = useParams<{ nationalId: string }>();
  const [fetchScore, scoreResult] = useLazyGetProScoreQuery();
  const historyResult = useGetScoreHistoryQuery(nationalId ?? '', {
    skip: !nationalId,
  });

  useEffect(() => {
    if (nationalId) {
      fetchScore(nationalId);
    }
  }, [nationalId, fetchScore]);

  const score = scoreResult.data;
  const isLoading = scoreResult.isLoading;

  if (isLoading) {
    return (
      <Box>
        <Skeleton variant="text" width={300} height={40} />
        <Skeleton variant="rectangular" height={300} sx={{ mt: 2, borderRadius: 2 }} />
      </Box>
    );
  }

  if (!score) {
    return (
      <Box>
        <Typography variant="h5" sx={{ color: 'text.primary', fontFamily: '"Sora", sans-serif' }}>
          Score not found
        </Typography>
        <Typography variant="body1" sx={{ color: 'text.secondary', fontFamily: '"DM Sans", sans-serif' }}>
          No score data available for the requested national ID.
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Typography
        variant="h4"
        className="vyce-animate"
        sx={{
          mb: 3,
          fontFamily: '"Sora", sans-serif',
          fontWeight: 700,
          color: 'text.primary',
        }}
      >
        Score Detail: {nationalId}
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Card
            className="vyce-animate vyce-animate-delay-1"
            sx={{ borderRadius: 3 }}
          >
            <CardContent sx={{ p: 3, textAlign: 'center' }}>
              <Box sx={{ filter: 'drop-shadow(0 0 14px rgba(0, 212, 170, 0.15))' }}>
                <ScoreGauge score={score.vyceScore} size={240} label="VyceScore" />
              </Box>
              <Box sx={{ mt: 3, filter: 'drop-shadow(0 0 10px rgba(14, 165, 233, 0.12))' }}>
                <ScoreGauge score={score.niqScore} size={180} label="NIQ Score" min={0} max={100} />
              </Box>
              <Box sx={{ mt: 2 }}>
                <Typography
                  variant="body2"
                  sx={{ color: 'text.secondary', fontFamily: '"DM Sans", sans-serif' }}
                >
                  Probability of Default
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 600,
                    color: 'text.primary',
                    fontFamily: '"Sora", sans-serif',
                  }}
                >
                  {formatPercentage(score.probabilityOfDefault)}
                </Typography>
                <Typography
                  variant="caption"
                  sx={{ color: 'text.disabled', fontFamily: '"DM Sans", sans-serif' }}
                >
                  Confidence: {score.confidenceInterval.lower} - {score.confidenceInterval.upper}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={8}>
          <Card
            className="vyce-animate vyce-animate-delay-2"
            sx={{ borderRadius: 3 }}
          >
            <CardContent sx={{ p: 3 }}>
              <Typography
                variant="h6"
                sx={{
                  mb: 2,
                  fontFamily: '"Sora", sans-serif',
                  fontWeight: 600,
                  color: 'text.primary',
                }}
              >
                Top Risk Drivers
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {score.riskDrivers.map((driver, index) => (
                  <RiskDriverCard key={driver.feature} driver={driver} index={index} />
                ))}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card
            className="vyce-animate vyce-animate-delay-4"
            sx={{ borderRadius: 3 }}
          >
            <CardContent sx={{ p: 3 }}>
              <ScoreTrendChart
                data={historyResult.data ?? []}
                title="Score History"
                height={350}
              />
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}

function RiskDriverCard({ driver, index }: { driver: RiskDriver; index: number }) {
  const isPositive = driver.impact === 'positive';
  return (
    <Box
      className={`vyce-animate vyce-animate-delay-${Math.min(index + 3, 6)}`}
      sx={{
        p: 2,
        borderRadius: 2,
        borderLeft: '3px solid',
        borderLeftColor: isPositive ? 'success.main' : 'error.main',
        backgroundColor: isPositive ? 'rgba(16, 185, 129, 0.06)' : 'rgba(239, 68, 68, 0.06)',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
        {isPositive ? (
          <ArrowUpwardIcon sx={{ color: 'success.main', fontSize: 20 }} />
        ) : (
          <ArrowDownwardIcon sx={{ color: 'error.main', fontSize: 20 }} />
        )}
        <Typography
          variant="subtitle2"
          sx={{
            fontWeight: 600,
            color: 'text.primary',
            fontFamily: '"DM Sans", sans-serif',
          }}
        >
          {driver.label}
        </Typography>
        <Chip
          label={driver.feature}
          size="small"
          variant="outlined"
          sx={{
            ml: 'auto',
            fontSize: 11,
            fontFamily: '"DM Sans", sans-serif',
          }}
        />
      </Box>
      <Typography
        variant="body2"
        sx={{ color: 'text.secondary', fontFamily: '"DM Sans", sans-serif' }}
      >
        {driver.description}
      </Typography>
      <Typography
        variant="caption"
        sx={{ color: 'text.disabled', fontFamily: '"DM Sans", sans-serif' }}
      >
        SHAP impact: {driver.shapValue > 0 ? '+' : ''}
        {driver.shapValue.toFixed(3)}
      </Typography>
    </Box>
  );
}
