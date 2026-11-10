import { Box, Typography, useTheme } from '@mui/material';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface QueryVolumeEntry {
  date: string;
  lite: number;
  pro: number;
}

interface QueryVolumeChartProps {
  data: QueryVolumeEntry[];
  height?: number;
  title?: string;
}

export default function QueryVolumeChart({
  data,
  height = 300,
  title = 'Query Volume',
}: QueryVolumeChartProps) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  const axisColor = isDark ? '#64748b' : '#94a3b8';
  const gridColor = isDark ? 'rgba(148, 163, 184, 0.06)' : 'rgba(0, 0, 0, 0.06)';
  const tooltipBg = isDark ? '#1a1f2e' : '#ffffff';
  const tooltipBorder = isDark ? 'rgba(0, 212, 170, 0.2)' : 'rgba(0, 0, 0, 0.08)';
  const tooltipShadow = isDark ? '0 8px 32px rgba(0, 0, 0, 0.4)' : '0 8px 24px rgba(0, 0, 0, 0.1)';
  const labelColor = theme.palette.text.primary;
  const itemColor = theme.palette.text.secondary;

  const formattedData = data.map((entry) => ({
    ...entry,
    date: new Date(entry.date).toLocaleDateString('en-KE', {
      month: 'short',
      day: 'numeric',
    }),
  }));

  return (
    <Box>
      {title && (
        <Typography
          variant="h6"
          sx={{
            mb: 2,
            fontFamily: '"Sora", sans-serif',
            fontSize: 16,
            color: 'text.primary',
          }}
        >
          {title}
        </Typography>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={formattedData} margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 12, fill: axisColor }}
            axisLine={{ stroke: gridColor }}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 12, fill: axisColor }}
            axisLine={{ stroke: gridColor }}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: tooltipBg,
              border: `1px solid ${tooltipBorder}`,
              borderRadius: 8,
              boxShadow: tooltipShadow,
            }}
            labelStyle={{ color: labelColor }}
            itemStyle={{ color: itemColor }}
          />
          <Legend wrapperStyle={{ color: itemColor }} />
          <Bar
            dataKey="lite"
            name="Lite Queries"
            fill="#00d4aa"
            radius={[4, 4, 0, 0]}
            fillOpacity={0.8}
          />
          <Bar
            dataKey="pro"
            name="Pro Queries"
            fill="#0ea5e9"
            radius={[4, 4, 0, 0]}
            fillOpacity={0.8}
          />
        </BarChart>
      </ResponsiveContainer>
    </Box>
  );
}
