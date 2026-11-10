import { Box, Typography } from '@mui/material';
import EmbedConfig from '../../components/embed/EmbedConfig';
import { useAuth } from '../../hooks/useAuth';
import LoadingSpinner from '../../components/common/LoadingSpinner';

export default function PartnerEmbedConfigPage() {
  const { user } = useAuth();

  if (!user) {
    return <LoadingSpinner message="Loading..." fullPage={false} />;
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 3 }}>
        Embed Widget
      </Typography>
      <EmbedConfig customerId={user.organizationId} />
    </Box>
  );
}
