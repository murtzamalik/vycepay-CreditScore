import { useState } from 'react';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  TextField,
  Switch,
  Divider,
  Grid,
  Alert,
  Snackbar,
  FormControlLabel,
  Chip,
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import { useAuth } from '../../hooks/useAuth';

interface NotificationPreferences {
  scoreThresholdAlerts: boolean;
  usageLimitWarnings: boolean;
  systemMaintenance: boolean;
}

interface SystemSettings {
  cacheTtlHours: number;
  rateLimitPerMinute: number;
  maintenanceMode: boolean;
}

export default function SettingsPage() {
  const { user, hasRole } = useAuth();
  const isAdmin = hasRole(['Admin']);

  // Profile Settings
  const [profileName, setProfileName] = useState(user?.name ?? '');

  // API Configuration
  const [apiBaseUrl] = useState(
    import.meta.env.VITE_API_BASE_URL ?? 'https://api.vycescore.com/v1'
  );
  const [showApiKey, setShowApiKey] = useState(false);

  // Notification Preferences
  const [notifications, setNotifications] = useState<NotificationPreferences>({
    scoreThresholdAlerts: true,
    usageLimitWarnings: true,
    systemMaintenance: true,
  });

  // System Settings (Admin only)
  const [systemSettings, setSystemSettings] = useState<SystemSettings>({
    cacheTtlHours: 24,
    rateLimitPerMinute: 100,
    maintenanceMode: false,
  });

  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error';
  }>({
    open: false,
    message: '',
    severity: 'success',
  });

  const handleSaveProfile = () => {
    setSnackbar({
      open: true,
      message: 'Profile settings saved successfully.',
      severity: 'success',
    });
  };

  const handleSaveNotifications = () => {
    setSnackbar({
      open: true,
      message: 'Notification preferences saved successfully.',
      severity: 'success',
    });
  };

  const handleSaveSystemSettings = () => {
    setSnackbar({
      open: true,
      message: 'System settings saved successfully.',
      severity: 'success',
    });
  };

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 3, color: 'text.primary', fontFamily: '"Sora", sans-serif' }}>
        Settings
      </Typography>

      <Grid container spacing={3}>
        {/* Profile Settings */}
        <Grid item xs={12} md={6}>
          <Card className="vyce-animate vyce-animate-delay-1" sx={{ borderRadius: '16px' }}>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ color: 'text.primary', fontFamily: '"Sora", sans-serif' }}>
                Profile Settings
              </Typography>
              <Divider sx={{ mb: 2 }} />

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <TextField
                  label="Full Name"
                  value={profileName}
                  onChange={(e) => setProfileName(e.target.value)}
                  fullWidth
                />
                <TextField
                  label="Email"
                  value={user?.email ?? ''}
                  fullWidth
                  disabled
                  helperText="Contact an administrator to change your email"
                />
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                    Role:
                  </Typography>
                  <Chip
                    label={user?.role ?? 'Unknown'}
                    size="small"
                    color="primary"
                    variant="outlined"
                    sx={{ fontWeight: 600 }}
                  />
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                    Organization:
                  </Typography>
                  <Typography variant="body2" sx={{ color: 'text.primary' }}>
                    {user?.organizationName ?? 'N/A'}
                  </Typography>
                </Box>
                <Button
                  variant="contained"
                  startIcon={<SaveIcon />}
                  onClick={handleSaveProfile}
                  disabled={profileName === user?.name}
                  sx={{ alignSelf: 'flex-start' }}
                >
                  Save Profile
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* API Configuration */}
        <Grid item xs={12} md={6}>
          <Card className="vyce-animate vyce-animate-delay-2" sx={{ borderRadius: '16px' }}>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ color: 'text.primary', fontFamily: '"Sora", sans-serif' }}>
                API Configuration
              </Typography>
              <Divider sx={{ mb: 2 }} />

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <TextField
                  label="API Base URL"
                  value={apiBaseUrl}
                  fullWidth
                  disabled
                  helperText="Configured via environment variables"
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={showApiKey}
                      onChange={(e) => setShowApiKey(e.target.checked)}
                    />
                  }
                  label={
                    <Typography variant="body2" sx={{ color: 'text.primary' }}>
                      Show API key in dashboard widgets
                    </Typography>
                  }
                />
                <Alert severity="info" variant="outlined">
                  API keys can be managed from the Partner API Keys page. Contact
                  your administrator if you need a new key generated.
                </Alert>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Notification Preferences */}
        <Grid item xs={12} md={6}>
          <Card className="vyce-animate vyce-animate-delay-3" sx={{ borderRadius: '16px' }}>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ color: 'text.primary', fontFamily: '"Sora", sans-serif' }}>
                Notification Preferences
              </Typography>
              <Divider sx={{ mb: 2 }} />

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={notifications.scoreThresholdAlerts}
                      onChange={(e) =>
                        setNotifications({
                          ...notifications,
                          scoreThresholdAlerts: e.target.checked,
                        })
                      }
                    />
                  }
                  label={
                    <Typography variant="body2" sx={{ color: 'text.primary' }}>
                      Score threshold alerts
                    </Typography>
                  }
                />
                <Typography variant="caption" sx={{ ml: 6, mt: -1, color: 'text.disabled' }}>
                  Receive email notifications when a score falls below configured thresholds
                </Typography>

                <FormControlLabel
                  control={
                    <Switch
                      checked={notifications.usageLimitWarnings}
                      onChange={(e) =>
                        setNotifications({
                          ...notifications,
                          usageLimitWarnings: e.target.checked,
                        })
                      }
                    />
                  }
                  label={
                    <Typography variant="body2" sx={{ color: 'text.primary' }}>
                      Usage limit warnings
                    </Typography>
                  }
                />
                <Typography variant="caption" sx={{ ml: 6, mt: -1, color: 'text.disabled' }}>
                  Get notified when API usage reaches 80% and 95% of the allocated quota
                </Typography>

                <FormControlLabel
                  control={
                    <Switch
                      checked={notifications.systemMaintenance}
                      onChange={(e) =>
                        setNotifications({
                          ...notifications,
                          systemMaintenance: e.target.checked,
                        })
                      }
                    />
                  }
                  label={
                    <Typography variant="body2" sx={{ color: 'text.primary' }}>
                      System maintenance notifications
                    </Typography>
                  }
                />
                <Typography variant="caption" sx={{ ml: 6, mt: -1, color: 'text.disabled' }}>
                  Receive advance notice of scheduled maintenance windows
                </Typography>

                <Button
                  variant="contained"
                  startIcon={<SaveIcon />}
                  onClick={handleSaveNotifications}
                  sx={{ alignSelf: 'flex-start', mt: 1 }}
                >
                  Save Preferences
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* System Settings - Admin only */}
        {isAdmin && (
          <Grid item xs={12} md={6}>
            <Card className="vyce-animate vyce-animate-delay-4" sx={{ borderRadius: '16px' }}>
              <CardContent>
                <Typography variant="h6" gutterBottom sx={{ color: 'text.primary', fontFamily: '"Sora", sans-serif' }}>
                  System Settings
                </Typography>
                <Divider sx={{ mb: 2 }} />

                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <TextField
                    label="Cache TTL (hours)"
                    type="number"
                    value={systemSettings.cacheTtlHours}
                    onChange={(e) =>
                      setSystemSettings({
                        ...systemSettings,
                        cacheTtlHours: Number(e.target.value),
                      })
                    }
                    fullWidth
                    inputProps={{ min: 1, max: 168 }}
                    helperText="How long scored results are cached in Redis (1-168 hours)"
                  />
                  <TextField
                    label="Rate Limit (requests/minute)"
                    type="number"
                    value={systemSettings.rateLimitPerMinute}
                    onChange={(e) =>
                      setSystemSettings({
                        ...systemSettings,
                        rateLimitPerMinute: Number(e.target.value),
                      })
                    }
                    fullWidth
                    inputProps={{ min: 10, max: 10000 }}
                    helperText="Default API rate limit per customer per minute"
                  />
                  <FormControlLabel
                    control={
                      <Switch
                        checked={systemSettings.maintenanceMode}
                        onChange={(e) =>
                          setSystemSettings({
                            ...systemSettings,
                            maintenanceMode: e.target.checked,
                          })
                        }
                        sx={{
                          '& .MuiSwitch-switchBase.Mui-checked': {
                            color: '#f59e0b',
                            '& + .MuiSwitch-track': { backgroundColor: '#f59e0b' },
                          },
                        }}
                      />
                    }
                    label={
                      <Typography variant="body2" sx={{ color: 'text.primary' }}>
                        Maintenance mode
                      </Typography>
                    }
                  />
                  {systemSettings.maintenanceMode && (
                    <Alert severity="warning" variant="outlined">
                      Enabling maintenance mode will return 503 responses to all API
                      consumers. The admin portal will remain accessible.
                    </Alert>
                  )}
                  <Button
                    variant="contained"
                    startIcon={<SaveIcon />}
                    onClick={handleSaveSystemSettings}
                    sx={{ alignSelf: 'flex-start' }}
                  >
                    Save System Settings
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>

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
