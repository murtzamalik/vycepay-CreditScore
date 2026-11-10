import { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  ToggleButtonGroup,
  ToggleButton,
  Alert,
  CircularProgress,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { useNavigate } from 'react-router-dom';
import { useLazyGetLiteScoreQuery, useLazyGetProScoreQuery } from '../../api/scoresApi';
import ScoreGauge from '../../components/charts/ScoreGauge';
import { formatDate } from '../../utils/formatters';

type ScoreTier = 'lite' | 'pro';

export default function ScoreLookupPage() {
  const [nationalId, setNationalId] = useState('');
  const [tier, setTier] = useState<ScoreTier>('lite');
  const navigate = useNavigate();

  const [fetchLite, liteResult] = useLazyGetLiteScoreQuery();
  const [fetchPro, proResult] = useLazyGetProScoreQuery();

  const result = tier === 'lite' ? liteResult : proResult;
  const isLoading = result.isLoading || result.isFetching;

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nationalId.trim()) return;

    if (tier === 'lite') {
      await fetchLite(nationalId.trim());
    } else {
      await fetchPro(nationalId.trim());
    }
  };

  const handleViewDetails = () => {
    if (result.data) {
      navigate(`/scores/detail/${result.data.nationalId}`);
    }
  };

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
        Score Lookup
      </Typography>

      <Card
        className="vyce-animate vyce-animate-delay-1"
        sx={{ mb: 3, borderRadius: 3 }}
      >
        <CardContent sx={{ p: 3 }}>
          <Box component="form" onSubmit={handleSearch}>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start', flexWrap: 'wrap' }}>
              <TextField
                label="National ID"
                value={nationalId}
                onChange={(e) => setNationalId(e.target.value)}
                placeholder="Enter national ID number"
                sx={{ flexGrow: 1, minWidth: 250 }}
              />
              <ToggleButtonGroup
                value={tier}
                exclusive
                onChange={(_, value: ScoreTier | null) => {
                  if (value) setTier(value);
                }}
                size="medium"
              >
                <ToggleButton value="lite">Lite</ToggleButton>
                <ToggleButton value="pro">Pro</ToggleButton>
              </ToggleButtonGroup>
              <Button
                type="submit"
                variant="contained"
                size="large"
                disabled={isLoading || !nationalId.trim()}
                startIcon={isLoading ? <CircularProgress size={18} color="inherit" /> : <SearchIcon />}
                sx={{ py: 1.8 }}
              >
                {isLoading ? 'Searching...' : 'Search'}
              </Button>
            </Box>
          </Box>
        </CardContent>
      </Card>

      {result.error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Failed to retrieve score. The ID may not exist or the service may be unavailable.
        </Alert>
      )}

      {result.data && (
        <Card
          className="vyce-animate vyce-animate-delay-2"
          sx={{ borderRadius: 3 }}
        >
          <CardContent sx={{ p: 4 }}>
            <Box
              sx={{
                display: 'flex',
                flexDirection: { xs: 'column', md: 'row' },
                gap: 4,
                alignItems: 'center',
              }}
            >
              <Box sx={{ filter: 'drop-shadow(0 0 12px rgba(0, 212, 170, 0.15))' }}>
                <ScoreGauge score={result.data.vyceScore} size={220} label="VyceScore" />
              </Box>
              <Box sx={{ filter: 'drop-shadow(0 0 10px rgba(14, 165, 233, 0.12))' }}>
                <ScoreGauge score={result.data.niqScore} size={180} label="NIQ Score" min={0} max={100} />
              </Box>
              <Box sx={{ flexGrow: 1 }}>
                <Typography
                  variant="h6"
                  sx={{
                    mb: 2,
                    fontFamily: '"Sora", sans-serif',
                    fontWeight: 600,
                    color: 'text.primary',
                  }}
                >
                  Score Details
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <DetailRow label="National ID" value={result.data.nationalId} />
                  <DetailRow label="Score Date" value={formatDate(result.data.scoreDate)} />
                  <DetailRow label="Model Version" value={result.data.modelVersion} />
                  <DetailRow label="Cached" value={result.data.cached ? 'Yes' : 'No'} />
                  <DetailRow label="Tier" value={tier.toUpperCase()} />
                </Box>
                {tier === 'pro' && (
                  <Button
                    variant="outlined"
                    sx={{ mt: 2 }}
                    onClick={handleViewDetails}
                  >
                    View Full Details
                  </Button>
                )}
              </Box>
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ display: 'flex', gap: 2 }}>
      <Typography
        variant="body2"
        sx={{
          minWidth: 130,
          color: 'text.secondary',
          fontFamily: '"DM Sans", sans-serif',
        }}
      >
        {label}:
      </Typography>
      <Typography
        variant="body2"
        sx={{
          fontWeight: 500,
          color: 'text.primary',
          fontFamily: '"DM Sans", sans-serif',
        }}
      >
        {value}
      </Typography>
    </Box>
  );
}
