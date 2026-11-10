import { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  IconButton,
  Chip,
  Alert,
  Divider,
  Switch,
  FormControlLabel,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CheckIcon from '@mui/icons-material/Check';
import { useSaveEmbedConfigMutation } from '../../api/partnerApi';
import EmbeddableWidget from './EmbeddableWidget';
import type { EmbedConfig as EmbedConfigType, PublicEmbedConfig } from '../../types/partner';

interface EmbedConfigProps {
  customerId: string;
  existingConfig?: EmbedConfigType;
}

export default function EmbedConfig({ customerId, existingConfig }: EmbedConfigProps) {
  const [saveConfig, { isLoading }] = useSaveEmbedConfigMutation();

  const [origins, setOrigins] = useState<string[]>(existingConfig?.allowedOrigins ?? []);
  const [newOrigin, setNewOrigin] = useState('');
  const [primaryColor, setPrimaryColor] = useState(
    (existingConfig?.themeConfig?.primaryColor as string) ?? '#1976d2',
  );
  const [secondaryColor, setSecondaryColor] = useState(
    (existingConfig?.themeConfig?.secondaryColor as string) ?? '#dc004e',
  );
  const [logoUrl, setLogoUrl] = useState(
    (existingConfig?.themeConfig?.logoUrl as string) ?? '',
  );
  const [appName, setAppName] = useState(
    (existingConfig?.themeConfig?.appName as string) ?? 'VyceScore',
  );
  const [showNiqScore, setShowNiqScore] = useState(
    (existingConfig?.widgetConfig?.showNiqScore as boolean) ?? true,
  );
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [snippetCopied, setSnippetCopied] = useState(false);

  const handleAddOrigin = () => {
    const trimmed = newOrigin.trim();
    if (trimmed && !origins.includes(trimmed)) {
      setOrigins([...origins, trimmed]);
      setNewOrigin('');
    }
  };

  const handleRemoveOrigin = (origin: string) => {
    setOrigins(origins.filter((o) => o !== origin));
  };

  const handleSave = async () => {
    setError(null);
    setSuccess(null);
    try {
      await saveConfig({
        customerId,
        data: {
          allowedOrigins: origins,
          themeConfig: {
            primaryColor,
            secondaryColor,
            logoUrl: logoUrl || undefined,
            appName,
          },
          widgetConfig: {
            showNiqScore,
          },
        },
      }).unwrap();
      setSuccess('Embed configuration saved successfully.');
    } catch {
      setError('Failed to save embed configuration.');
    }
  };

  const customerToken = existingConfig?.customerToken ?? 'YOUR_TOKEN';
  const embedSnippet = `<iframe
  src="${window.location.origin}/embed/widget?token=${customerToken}"
  width="480"
  height="400"
  frameborder="0"
  allow="clipboard-write"
></iframe>`;

  const handleCopySnippet = async () => {
    await navigator.clipboard.writeText(embedSnippet);
    setSnippetCopied(true);
    setTimeout(() => setSnippetCopied(false), 2000);
  };

  // Preview config for the widget
  const previewConfig: PublicEmbedConfig = {
    customerToken,
    allowedOrigins: origins,
    themeConfig: {
      primaryColor,
      secondaryColor,
      logoUrl: logoUrl || undefined,
      appName,
    },
    widgetConfig: {
      showNiqScore,
    },
  };

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3 }}>
        White-Label Embed Configuration
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      )}

      <Box sx={{ display: 'flex', gap: 3, flexDirection: { xs: 'column', lg: 'row' } }}>
        {/* Configuration form */}
        <Box sx={{ flex: 1 }}>
          {/* Allowed Origins */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Allowed Origins
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Domains that are allowed to embed the score lookup widget.
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                <TextField
                  size="small"
                  fullWidth
                  value={newOrigin}
                  onChange={(e) => setNewOrigin(e.target.value)}
                  placeholder="https://example.com"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleAddOrigin();
                    }
                  }}
                />
                <Button variant="outlined" onClick={handleAddOrigin} startIcon={<AddIcon />}>
                  Add
                </Button>
              </Box>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {origins.map((origin) => (
                  <Chip
                    key={origin}
                    label={origin}
                    onDelete={() => handleRemoveOrigin(origin)}
                    deleteIcon={<DeleteIcon />}
                    variant="outlined"
                  />
                ))}
                {origins.length === 0 && (
                  <Typography variant="caption" color="text.secondary">
                    No origins configured (all origins allowed)
                  </Typography>
                )}
              </Box>
            </CardContent>
          </Card>

          {/* Theme config */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Theme Settings
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <TextField
                  label="App Name"
                  value={appName}
                  onChange={(e) => setAppName(e.target.value)}
                  size="small"
                  fullWidth
                />
                <TextField
                  label="Logo URL"
                  value={logoUrl}
                  onChange={(e) => setLogoUrl(e.target.value)}
                  size="small"
                  fullWidth
                  placeholder="https://example.com/logo.png"
                />
                <Box sx={{ display: 'flex', gap: 2 }}>
                  <TextField
                    label="Primary Color"
                    type="color"
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    size="small"
                    sx={{ flex: 1 }}
                    InputProps={{
                      inputProps: { style: { height: 36, cursor: 'pointer' } },
                    }}
                  />
                  <TextField
                    label="Secondary Color"
                    type="color"
                    value={secondaryColor}
                    onChange={(e) => setSecondaryColor(e.target.value)}
                    size="small"
                    sx={{ flex: 1 }}
                    InputProps={{
                      inputProps: { style: { height: 36, cursor: 'pointer' } },
                    }}
                  />
                </Box>
              </Box>
            </CardContent>
          </Card>

          {/* Widget config */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Widget Settings
              </Typography>
              <FormControlLabel
                control={
                  <Switch
                    checked={showNiqScore}
                    onChange={(e) => setShowNiqScore(e.target.checked)}
                  />
                }
                label="Show NIQ Score in widget"
              />
            </CardContent>
          </Card>

          <Button
            variant="contained"
            size="large"
            onClick={handleSave}
            disabled={isLoading}
            fullWidth
          >
            {isLoading ? 'Saving...' : 'Save Configuration'}
          </Button>
        </Box>

        {/* Preview + embed code */}
        <Box sx={{ flex: 1 }}>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Widget Preview
              </Typography>
              <EmbeddableWidget
                customerToken={customerToken}
                previewConfig={previewConfig}
              />
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                <Typography variant="h6">Embed Code</Typography>
                <IconButton onClick={handleCopySnippet} size="small">
                  {snippetCopied ? <CheckIcon color="success" /> : <ContentCopyIcon />}
                </IconButton>
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Copy this snippet to embed the score lookup widget in your website.
              </Typography>
              <Box
                component="pre"
                sx={{
                  p: 2,
                  backgroundColor: 'grey.100',
                  borderRadius: 1,
                  overflow: 'auto',
                  fontSize: 12,
                  fontFamily: 'monospace',
                }}
              >
                {embedSnippet}
              </Box>

              <Divider sx={{ my: 2 }} />

              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                postMessage API
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Send lookup requests programmatically:
              </Typography>
              <Box
                component="pre"
                sx={{
                  p: 2,
                  mt: 1,
                  backgroundColor: 'grey.100',
                  borderRadius: 1,
                  overflow: 'auto',
                  fontSize: 12,
                  fontFamily: 'monospace',
                }}
              >
{`// Send lookup request
iframe.contentWindow.postMessage(
  { type: 'VYCE_LOOKUP', nationalId: '12345678' },
  '${window.location.origin}'
);

// Listen for results
window.addEventListener('message', (event) => {
  if (event.data.type === 'VYCE_SCORE_RESULT') {
    console.log(event.data.data); // { vyceScore, niqScore, ... }
  }
});`}
              </Box>
            </CardContent>
          </Card>
        </Box>
      </Box>
    </Box>
  );
}
