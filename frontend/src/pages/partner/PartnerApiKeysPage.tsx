import { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  TextField,
  InputAdornment,
  IconButton,
  Tooltip,
  Chip,
} from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import RefreshIcon from '@mui/icons-material/Refresh';
import DeleteIcon from '@mui/icons-material/Delete';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import CheckIcon from '@mui/icons-material/Check';
import {
  useGetApiKeyInfoQuery,
  useRotateApiKeyMutation,
  useRevokeApiKeyMutation,
} from '../../api/partnerApi';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import { formatDate } from '../../utils/formatters';

export default function PartnerApiKeysPage() {
  const { data: keyInfo, isLoading } = useGetApiKeyInfoQuery();
  const [rotateKey, { isLoading: isRotating }] = useRotateApiKeyMutation();
  const [revokeKey, { isLoading: isRevoking }] = useRevokeApiKeyMutation();

  const [newKey, setNewKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [rotateDialogOpen, setRotateDialogOpen] = useState(false);
  const [revokeDialogOpen, setRevokeDialogOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  if (isLoading) {
    return <LoadingSpinner message="Loading API key info..." fullPage={false} />;
  }

  const handleRotate = async () => {
    setRotateDialogOpen(false);
    setError(null);
    setSuccessMessage(null);
    try {
      const result = await rotateKey().unwrap();
      setNewKey(result.apiKey);
      setSuccessMessage('API key rotated successfully. Copy the new key below -- it will not be shown again.');
    } catch {
      setError('Failed to rotate API key. Please try again.');
    }
  };

  const handleRevoke = async () => {
    setRevokeDialogOpen(false);
    setError(null);
    setSuccessMessage(null);
    setNewKey(null);
    try {
      await revokeKey().unwrap();
      setSuccessMessage('API key has been revoked. Contact your administrator to get a new key.');
    } catch {
      setError('Failed to revoke API key. Please try again.');
    }
  };

  const handleCopy = async () => {
    if (newKey) {
      await navigator.clipboard.writeText(newKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 3, color: 'text.primary', fontFamily: '"Sora", sans-serif' }}>
        API Key Management
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {successMessage && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      )}

      {/* New key display (after rotation) */}
      {newKey && (
        <Card
          sx={{
            mb: 3,
            border: '1px solid',
            borderColor: 'warning.main',
            borderRadius: '16px',
          }}
        >
          <CardContent>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, color: 'warning.main', mb: 1 }}>
              New API Key (copy now -- it will not be shown again)
            </Typography>
            <TextField
              fullWidth
              value={newKey}
              InputProps={{
                readOnly: true,
                endAdornment: (
                  <InputAdornment position="end">
                    <Tooltip title={copied ? 'Copied!' : 'Copy to clipboard'}>
                      <IconButton onClick={handleCopy} edge="end">
                        {copied ? <CheckIcon sx={{ color: 'success.main' }} /> : <ContentCopyIcon />}
                      </IconButton>
                    </Tooltip>
                  </InputAdornment>
                ),
                sx: {
                  fontFamily: 'monospace',
                  fontSize: 14,
                },
              }}
            />
          </CardContent>
        </Card>
      )}

      {/* Current key info */}
      <Card className="vyce-animate vyce-animate-delay-1" sx={{ mb: 3, borderRadius: '16px' }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
            <VpnKeyIcon sx={{ fontSize: 36, color: 'primary.main' }} />
            <Box>
              <Typography variant="h6" sx={{ color: 'text.primary', fontFamily: '"Sora", sans-serif' }}>
                Current API Key
              </Typography>
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                Used for authenticating API requests via the X-API-Key header.
              </Typography>
            </Box>
          </Box>

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
              <Typography variant="body2" sx={{ color: 'text.secondary', minWidth: 120 }}>
                Key Prefix:
              </Typography>
              <Chip
                label={keyInfo?.keyPrefix ?? 'No key'}
                variant="outlined"
                sx={{ fontFamily: 'monospace' }}
              />
            </Box>
            {keyInfo?.createdAt && (
              <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                <Typography variant="body2" sx={{ color: 'text.secondary', minWidth: 120 }}>
                  Created:
                </Typography>
                <Typography variant="body2" sx={{ color: 'text.primary' }}>{formatDate(keyInfo.createdAt)}</Typography>
              </Box>
            )}
            {keyInfo?.lastUsedAt && (
              <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                <Typography variant="body2" sx={{ color: 'text.secondary', minWidth: 120 }}>
                  Last Used:
                </Typography>
                <Typography variant="body2" sx={{ color: 'text.primary' }}>{formatDate(keyInfo.lastUsedAt)}</Typography>
              </Box>
            )}
          </Box>
        </CardContent>
      </Card>

      {/* Actions */}
      <Card className="vyce-animate vyce-animate-delay-2" sx={{ borderRadius: '16px' }}>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 2, color: 'text.primary', fontFamily: '"Sora", sans-serif' }}>
            Key Actions
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Button
              variant="contained"
              startIcon={<RefreshIcon />}
              onClick={() => setRotateDialogOpen(true)}
              disabled={isRotating}
            >
              {isRotating ? 'Rotating...' : 'Rotate Key'}
            </Button>
            <Button
              variant="outlined"
              startIcon={<DeleteIcon />}
              onClick={() => setRevokeDialogOpen(true)}
              disabled={isRevoking}
              color="error"
            >
              {isRevoking ? 'Revoking...' : 'Revoke Key'}
            </Button>
          </Box>
          <Typography variant="caption" sx={{ display: 'block', mt: 2, color: 'text.disabled' }}>
            Rotating the key will immediately invalidate the current key and generate a new one.
            Revoking the key will disable API access until an administrator generates a new key.
          </Typography>
        </CardContent>
      </Card>

      {/* Rotate confirmation dialog */}
      <Dialog
        open={rotateDialogOpen}
        onClose={() => setRotateDialogOpen(false)}
      >
        <DialogTitle sx={{ color: 'text.primary', fontFamily: '"Sora", sans-serif' }}>Rotate API Key?</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ color: 'text.secondary' }}>
            This will immediately invalidate your current API key and generate a new one.
            Any applications using the old key will stop working immediately.
            The new key will be displayed only once -- make sure to copy it.
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setRotateDialogOpen(false)} sx={{ color: 'text.secondary' }}>Cancel</Button>
          <Button onClick={handleRotate} variant="contained" autoFocus>
            Rotate Key
          </Button>
        </DialogActions>
      </Dialog>

      {/* Revoke confirmation dialog */}
      <Dialog
        open={revokeDialogOpen}
        onClose={() => setRevokeDialogOpen(false)}
      >
        <DialogTitle sx={{ color: 'text.primary', fontFamily: '"Sora", sans-serif' }}>Revoke API Key?</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ color: 'text.secondary' }}>
            This will permanently revoke your current API key. All API access will be disabled
            until an administrator generates a new key for your account. This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setRevokeDialogOpen(false)} sx={{ color: 'text.secondary' }}>Cancel</Button>
          <Button
            onClick={handleRevoke}
            variant="contained"
            color="error"
            autoFocus
          >
            Revoke Key
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
