import { Box, Toolbar } from '@mui/material';
import { Outlet } from 'react-router-dom';
import Sidebar, { SIDEBAR_WIDTH } from './Sidebar';
import Header from './Header';

export default function AppShell() {
  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }} className="vyce-noise">
      <Sidebar />
      <Header />
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: `calc(100% - ${SIDEBAR_WIDTH}px)`,
          backgroundColor: 'transparent',
        }}
      >
        <Toolbar />
        <Outlet />
      </Box>
    </Box>
  );
}
