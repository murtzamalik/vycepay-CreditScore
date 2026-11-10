import { Box, Typography, useTheme } from '@mui/material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import type { ScoreHistoryEntry } from '../../types/scores';

interface ScoreTrendChartProps {
  data: ScoreHistoryEntry[];
  height?: number;
  title?: string;
}

export default function ScoreTrendChart({
  data,
  height = 300,
  title = 'Score Trend',
}: ScoreTrendChartProps) {
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
      year: '2-digit',
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
        <LineChart data={formattedData} margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 12, fill: axisColor }}
            axisLine={{ stroke: gridColor }}
            tickLine={false}
          />
          <YAxis
            yAxisId="left"
            domain={[300, 900]}
            tick={{ fontSize: 12, fill: axisColor }}
            axisLine={{ stroke: gridColor }}
            tickLine={false}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={[0, 100]}
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
          <ReferenceLine
            yAxisId="left"
            y={500}
            stroke="#f59e0b"
            strokeDasharray="5 5"
            strokeOpacity={0.4}
            label={{ value: 'Medium', fill: '#f59e0b', fontSize: 11, opacity: 0.6 }}
          />
          <ReferenceLine
            yAxisId="left"
            y={700}
            stroke="#10b981"
            strokeDasharray="5 5"
            strokeOpacity={0.4}
            label={{ value: 'Low Risk', fill: '#10b981', fontSize: 11, opacity: 0.6 }}
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="vyceScore"
            name="VyceScore"
            stroke="#00d4aa"
            strokeWidth={2.5}
            dot={{ r: 4, fill: '#00d4aa', strokeWidth: 0 }}
            activeDot={{
              r: 6,
              fill: '#00d4aa',
              stroke: 'rgba(0, 212, 170, 0.3)',
              strokeWidth: 4,
            }}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="niqScore"
            name="NIQ Score"
            stroke="#0ea5e9"
            strokeWidth={2.5}
            dot={{ r: 4, fill: '#0ea5e9', strokeWidth: 0 }}
            activeDot={{
              r: 6,
              fill: '#0ea5e9',
              stroke: 'rgba(14, 165, 233, 0.3)',
              strokeWidth: 4,
            }}
          />
        </LineChart>
      </ResponsiveContainer>
    </Box>
  );
}
