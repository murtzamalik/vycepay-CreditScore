import { useState } from 'react';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Chip,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Alert,
  Snackbar,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import BlockIcon from '@mui/icons-material/Block';
import type { GridColDef } from '@mui/x-data-grid';
import DataTable from '../../components/common/DataTable';
import type { UserRole } from '../../types/common';

interface UserRow {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  organization: string;
  status: 'active' | 'inactive';
  lastLogin: string;
}

const ROLE_CHIP_STYLES: Record<UserRole, { backgroundColor: string; color: string; border: string }> = {
  Admin: {
    backgroundColor: 'rgba(0, 212, 170, 0.12)',
    color: '#00d4aa',
    border: '1px solid rgba(0, 212, 170, 0.2)',
  },
  Operator: {
    backgroundColor: 'rgba(14, 165, 233, 0.12)',
    color: '#0ea5e9',
    border: '1px solid rgba(14, 165, 233, 0.2)',
  },
  Partner: {
    backgroundColor: 'rgba(139, 92, 246, 0.12)',
    color: '#8b5cf6',
    border: '1px solid rgba(139, 92, 246, 0.2)',
  },
  ReadOnly: {
    backgroundColor: 'rgba(100, 116, 139, 0.12)',
    color: '#64748b',
    border: '1px solid rgba(100, 116, 139, 0.2)',
  },
};

const STATUS_CHIP_STYLES: Record<'active' | 'inactive', { backgroundColor: string; color: string; border: string }> = {
  active: {
    backgroundColor: 'rgba(16, 185, 129, 0.12)',
    color: '#10b981',
    border: '1px solid rgba(16, 185, 129, 0.2)',
  },
  inactive: {
    backgroundColor: 'rgba(71, 85, 105, 0.12)',
    color: '#475569',
    border: '1px solid rgba(71, 85, 105, 0.2)',
  },
};

const SAMPLE_USERS: UserRow[] = [
  {
    id: '1',
    name: 'James Mwangi',
    email: 'james@vycepay.com',
    role: 'Admin',
    organization: 'VycePay',
    status: 'active',
    lastLogin: '2026-03-08 10:30',
  },
  {
    id: '2',
    name: 'Wanjiku Kamau',
    email: 'wanjiku@equitybank.co.ke',
    role: 'Partner',
    organization: 'Equity Bank',
    status: 'active',
    lastLogin: '2026-03-07 14:15',
  },
  {
    id: '3',
    name: 'Odhiambo Ochieng',
    email: 'odhiambo@vycepay.com',
    role: 'Operator',
    organization: 'VycePay',
    status: 'active',
    lastLogin: '2026-03-08 09:45',
  },
  {
    id: '4',
    name: 'Amina Hassan',
    email: 'amina@kcbgroup.com',
    role: 'ReadOnly',
    organization: 'KCB Group',
    status: 'inactive',
    lastLogin: '2026-02-20 16:00',
  },
];

interface AddUserForm {
  email: string;
  name: string;
  role: UserRole;
}

interface EditRoleForm {
  role: UserRole;
}

export default function UsersPage() {
  const [users, setUsers] = useState<UserRow[]>(SAMPLE_USERS);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deactivateDialogOpen, setDeactivateDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<UserRow | null>(null);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });

  const [addForm, setAddForm] = useState<AddUserForm>({
    email: '',
    name: '',
    role: 'ReadOnly',
  });

  const [editForm, setEditForm] = useState<EditRoleForm>({
    role: 'ReadOnly',
  });

  const handleAddUser = () => {
    const newUser: UserRow = {
      id: String(Date.now()),
      name: addForm.name,
      email: addForm.email,
      role: addForm.role,
      organization: 'VycePay',
      status: 'active',
      lastLogin: '-',
    };
    setUsers([...users, newUser]);
    setAddDialogOpen(false);
    setAddForm({ email: '', name: '', role: 'ReadOnly' });
    setSnackbar({ open: true, message: `User ${addForm.name} created successfully.`, severity: 'success' });
  };

  const handleOpenEdit = (user: UserRow) => {
    setSelectedUser(user);
    setEditForm({ role: user.role });
    setEditDialogOpen(true);
  };

  const handleUpdateRole = () => {
    if (!selectedUser) return;
    setUsers(
      users.map((u) =>
        u.id === selectedUser.id ? { ...u, role: editForm.role } : u
      )
    );
    setEditDialogOpen(false);
    setSnackbar({ open: true, message: `Role updated for ${selectedUser.name}.`, severity: 'success' });
  };

  const handleOpenDeactivate = (user: UserRow) => {
    setSelectedUser(user);
    setDeactivateDialogOpen(true);
  };

  const handleDeactivate = () => {
    if (!selectedUser) return;
    setUsers(
      users.map((u) =>
        u.id === selectedUser.id ? { ...u, status: 'inactive' as const } : u
      )
    );
    setDeactivateDialogOpen(false);
    setSnackbar({ open: true, message: `${selectedUser.name} has been deactivated.`, severity: 'success' });
  };

  const columns: GridColDef[] = [
    { field: 'name', headerName: 'Name', flex: 1, minWidth: 150 },
    { field: 'email', headerName: 'Email', flex: 1.5, minWidth: 200 },
    {
      field: 'role',
      headerName: 'Role',
      width: 120,
      renderCell: (params) => {
        const style = ROLE_CHIP_STYLES[params.value as UserRole];
        return (
          <Chip
            label={params.value as string}
            size="small"
            sx={{
              fontWeight: 600,
              fontSize: 11,
              fontFamily: '"DM Sans", sans-serif',
              ...style,
            }}
          />
        );
      },
    },
    { field: 'organization', headerName: 'Organization', flex: 1, minWidth: 150 },
    {
      field: 'status',
      headerName: 'Status',
      width: 100,
      renderCell: (params) => {
        const style = STATUS_CHIP_STYLES[params.value as 'active' | 'inactive'];
        return (
          <Chip
            label={params.value as string}
            size="small"
            sx={{
              fontSize: 11,
              fontFamily: '"DM Sans", sans-serif',
              ...style,
            }}
          />
        );
      },
    },
    { field: 'lastLogin', headerName: 'Last Login', width: 160 },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 120,
      sortable: false,
      renderCell: (params) => {
        const user = params.row as UserRow;
        return (
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            <Tooltip title="Edit Role">
              <IconButton size="small" onClick={() => handleOpenEdit(user)}>
                <EditIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            {user.status === 'active' && (
              <Tooltip title="Deactivate">
                <IconButton
                  size="small"
                  onClick={() => handleOpenDeactivate(user)}
                  sx={{ color: 'error.main' }}
                >
                  <BlockIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
          </Box>
        );
      },
    },
  ];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography
          variant="h4"
          className="vyce-animate"
          sx={{
            fontFamily: '"Sora", sans-serif',
            fontWeight: 700,
            color: 'text.primary',
          }}
        >
          User Management
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setAddDialogOpen(true)}
          className="vyce-animate vyce-animate-delay-1"
        >
          Add User
        </Button>
      </Box>

      <Card
        className="vyce-animate vyce-animate-delay-2"
        sx={{ borderRadius: 3 }}
      >
        <CardContent>
          <DataTable rows={users} columns={columns} pageSize={10} />
        </CardContent>
      </Card>

      {/* Add User Dialog */}
      <Dialog open={addDialogOpen} onClose={() => setAddDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ color: 'text.primary', fontFamily: '"Sora", sans-serif', fontWeight: 600 }}>
          Add New User
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
            <TextField label="Full Name" value={addForm.name} onChange={(e) => setAddForm({ ...addForm, name: e.target.value })} fullWidth required />
            <TextField label="Email" type="email" value={addForm.email} onChange={(e) => setAddForm({ ...addForm, email: e.target.value })} fullWidth required />
            <TextField select label="Role" value={addForm.role} onChange={(e) => setAddForm({ ...addForm, role: e.target.value as UserRole })} fullWidth>
              <MenuItem value="Admin">Admin</MenuItem>
              <MenuItem value="Operator">Operator</MenuItem>
              <MenuItem value="Partner">Partner</MenuItem>
              <MenuItem value="ReadOnly">Read Only</MenuItem>
            </TextField>
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setAddDialogOpen(false)} sx={{ color: 'text.secondary' }}>Cancel</Button>
          <Button variant="contained" onClick={handleAddUser} disabled={!addForm.name || !addForm.email}>
            Create User
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit Role Dialog */}
      <Dialog open={editDialogOpen} onClose={() => setEditDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ color: 'text.primary', fontFamily: '"Sora", sans-serif', fontWeight: 600 }}>
          Edit Role {selectedUser ? `- ${selectedUser.name}` : ''}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ mt: 1 }}>
            <TextField select label="Role" value={editForm.role} onChange={(e) => setEditForm({ role: e.target.value as UserRole })} fullWidth>
              <MenuItem value="Admin">Admin</MenuItem>
              <MenuItem value="Operator">Operator</MenuItem>
              <MenuItem value="Partner">Partner</MenuItem>
              <MenuItem value="ReadOnly">Read Only</MenuItem>
            </TextField>
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setEditDialogOpen(false)} sx={{ color: 'text.secondary' }}>Cancel</Button>
          <Button variant="contained" onClick={handleUpdateRole}>
            Update Role
          </Button>
        </DialogActions>
      </Dialog>

      {/* Deactivate Confirmation Dialog */}
      <Dialog open={deactivateDialogOpen} onClose={() => setDeactivateDialogOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ color: 'text.primary', fontFamily: '"Sora", sans-serif', fontWeight: 600 }}>
          Deactivate User
        </DialogTitle>
        <DialogContent>
          <Typography variant="body1" sx={{ color: 'text.secondary', fontFamily: '"DM Sans", sans-serif' }}>
            Are you sure you want to deactivate{' '}
            <strong>{selectedUser?.name}</strong>? They will no longer be able to access the
            system.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setDeactivateDialogOpen(false)} sx={{ color: 'text.secondary' }}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleDeactivate}
            sx={{
              backgroundColor: 'error.main',
              color: '#ffffff',
              fontWeight: 700,
              '&:hover': {
                backgroundColor: 'error.dark',
              },
            }}
          >
            Deactivate
          </Button>
        </DialogActions>
      </Dialog>

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
