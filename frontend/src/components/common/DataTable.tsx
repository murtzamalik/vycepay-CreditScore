import { useState } from 'react';
import { Box } from '@mui/material';
import { DataGrid, type GridColDef, type GridPaginationModel, type GridRowParams } from '@mui/x-data-grid';

interface DataTableProps<T extends { id: string | number }> {
  rows: T[];
  columns: GridColDef[];
  loading?: boolean;
  pageSize?: number;
  totalRows?: number;
  onPageChange?: (page: number, pageSize: number) => void;
  onRowClick?: (row: T) => void;
  autoHeight?: boolean;
}

export default function DataTable<T extends { id: string | number }>({
  rows,
  columns,
  loading = false,
  pageSize = 10,
  totalRows,
  onPageChange,
  onRowClick,
  autoHeight = true,
}: DataTableProps<T>) {
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize,
  });

  const handlePaginationChange = (model: GridPaginationModel) => {
    setPaginationModel(model);
    onPageChange?.(model.page, model.pageSize);
  };

  const handleRowClick = (params: GridRowParams) => {
    onRowClick?.(params.row as T);
  };

  return (
    <Box sx={{ width: '100%' }}>
      <DataGrid
        rows={rows}
        columns={columns}
        loading={loading}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationChange}
        pageSizeOptions={[5, 10, 25, 50]}
        rowCount={totalRows ?? rows.length}
        paginationMode={totalRows !== undefined ? 'server' : 'client'}
        autoHeight={autoHeight}
        disableRowSelectionOnClick
        onRowClick={handleRowClick}
        sx={{
          border: 'none',
          '& .MuiDataGrid-cell:focus': {
            outline: 'none',
          },
          '& .MuiDataGrid-cell:focus-within': {
            outline: 'none',
          },
          ...(onRowClick
            ? {
                '& .MuiDataGrid-row': {
                  cursor: 'pointer',
                },
              }
            : {}),
        }}
      />
    </Box>
  );
}
