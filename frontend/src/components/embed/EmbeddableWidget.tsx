import { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  CircularProgress,
  Alert,
  ThemeProvider,
  createTheme,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import type { PublicEmbedConfig } from '../../types/partner';

interface EmbeddableWidgetProps {
  /** Customer token for loading embed configuration */
  customerToken: string;
  /** API base URL for score lookups */
  apiBaseUrl?: string;
  /** API key for authenticating score requests */
  apiKey?: string;
  /** Optional override config (for preview mode) */
  previewConfig?: PublicEmbedConfig;
}

interface ScoreResult {
  vyceScore: number;
  niqScore: number;
  nationalId: string;
  scoreDate: string;
}

/**
 * Embeddable score lookup widget for partner white-label integration.
 *
 * Supports two embedding modes:
 * 1. iframe: embedded via iframe, communicates via postMessage API
 * 2. Direct: rendered as a React component within partner applications
 *
 * postMessage API:
 *   - Incoming: { type: 'VYCE_LOOKUP', nationalId: string }
 *   - Outgoing: { type: 'VYCE_SCORE_RESULT', data: ScoreResult }
 *   - Outgoing: { type: 'VYCE_SCORE_ERROR', error: string }
 */
export default function EmbeddableWidget({
  customerToken,
  apiBaseUrl = '/v1',
  apiKey,
  previewConfig,
}: EmbeddableWidgetProps) {
  const [config, setConfig] = useState<PublicEmbedConfig | null>(previewConfig ?? null);
  const [nationalId, setNationalId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<ScoreResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [configLoading, setConfigLoading] = useState(!previewConfig);

  // Load embed config
  useEffect(() => {
    if (previewConfig) return;

    const loadConfig = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/embed/config/${customerToken}`);
        if (!response.ok) throw new Error('Failed to load embed configuration');
        const data = await response.json();
        setConfig(data);
      } catch (err) {
        setError('Widget configuration could not be loaded.');
      } finally {
        setConfigLoading(false);
      }
    };

    loadConfig();
  }, [customerToken, apiBaseUrl, previewConfig]);

  // Listen for postMessage events (iframe mode)
  const handleMessage = useCallback(
    async (event: MessageEvent) => {
      if (!config) return;

      // Validate origin
      if (
        config.allowedOrigins.length > 0 &&
        !config.allowedOrigins.includes(event.origin)
      ) {
        return;
      }

      if (event.data?.type === 'VYCE_LOOKUP' && event.data?.nationalId) {
        await performLookup(event.data.nationalId, event.source as Window);
      }
    },
    [config, apiBaseUrl, apiKey],
  );

  useEffect(() => {
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [handleMessage]);

  const performLookup = async (id: string, replyTarget?: Window) => {
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (apiKey) {
        headers['X-API-Key'] = apiKey;
      }

      const response = await fetch(`${apiBaseUrl}/scores/lite/${id}`, { headers });
      if (!response.ok) throw new Error('Score lookup failed');
      const data: ScoreResult = await response.json();
      setResult(data);

      // Post result back to parent (iframe mode)
      const msg = { type: 'VYCE_SCORE_RESULT', data };
      if (replyTarget) {
        replyTarget.postMessage(msg, '*');
      } else if (window.parent !== window) {
        window.parent.postMessage(msg, '*');
      }
    } catch (err) {
      const errMsg = 'Failed to retrieve score. Please try again.';
      setError(errMsg);

      const msg = { type: 'VYCE_SCORE_ERROR', error: errMsg };
      if (replyTarget) {
        replyTarget.postMessage(msg, '*');
      } else if (window.parent !== window) {
        window.parent.postMessage(msg, '*');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nationalId.trim()) return;
    await performLookup(nationalId.trim());
  };

  // Build theme from config
  const widgetTheme = createTheme({
    palette: {
      primary: {
        main: config?.themeConfig?.primaryColor ?? '#1976d2',
      },
      secondary: {
        main: config?.themeConfig?.secondaryColor ?? '#dc004e',
      },
    },
  });

  if (configLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  const appName = config?.themeConfig?.appName ?? 'VyceScore';

  return (
    <ThemeProvider theme={widgetTheme}>
      <Card variant="outlined" sx={{ maxWidth: 480, mx: 'auto' }}>
        <CardContent sx={{ p: 3 }}>
          {config?.themeConfig?.logoUrl && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
              <Box
                component="img"
                src={config.themeConfig.logoUrl}
                alt={appName}
                sx={{ height: 32, objectFit: 'contain' }}
              />
            </Box>
          )}

          <Typography variant="h6" align="center" sx={{ mb: 2 }}>
            {appName} - Score Lookup
          </Typography>

          <Box component="form" onSubmit={handleSubmit}>
            <TextField
              fullWidth
              label="National ID"
              value={nationalId}
              onChange={(e) => setNationalId(e.target.value)}
              placeholder="Enter national ID number"
              size="small"
              sx={{ mb: 2 }}
            />
            <Button
              type="submit"
              variant="contained"
              fullWidth
              disabled={isLoading || !nationalId.trim()}
              startIcon={isLoading ? <CircularProgress size={18} /> : <SearchIcon />}
            >
              {isLoading ? 'Searching...' : 'Look Up Score'}
            </Button>
          </Box>

          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}

          {result && (
            <Box sx={{ mt: 3, textAlign: 'center' }}>
              <Typography variant="h3" color="primary" sx={{ fontWeight: 700 }}>
                {result.vyceScore}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                VyceScore
              </Typography>

              {config?.widgetConfig?.showNiqScore !== false && (
                <Box sx={{ mt: 1 }}>
                  <Typography variant="h5" color="secondary" sx={{ fontWeight: 600 }}>
                    {result.niqScore}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    NIQ Score
                  </Typography>
                </Box>
              )}

              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                Score Date: {result.scoreDate}
              </Typography>
            </Box>
          )}
        </CardContent>
      </Card>
    </ThemeProvider>
  );
}
