import { Box, Typography } from '@mui/material';
import { PieChart, Pie, Cell } from 'recharts';

interface ScoreGaugeProps {
  score: number;
  size?: number;
  label?: string;
  min?: number;
  max?: number;
}

function getScoreColor(score: number): string {
  if (score < 500) return '#ef4444';
  if (score <= 700) return '#f59e0b';
  return '#10b981';
}

function getScoreLabel(score: number): string {
  if (score < 500) return 'High Risk';
  if (score <= 700) return 'Medium Risk';
  return 'Low Risk';
}

export default function ScoreGauge({
  score,
  size = 200,
  label,
  min = 300,
  max = 900,
}: ScoreGaugeProps) {
  const range = max - min;
  const normalizedScore = Math.max(min, Math.min(max, score));
  const filledValue = normalizedScore - min;
  const remainingValue = range - filledValue;

  const data = [
    { name: 'score', value: filledValue },
    { name: 'remaining', value: remainingValue },
  ];

  const scoreColor = min === 0 ? '#00d4aa' : getScoreColor(normalizedScore);
  const glowColor = scoreColor + '40';

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      {label && (
        <Typography
          sx={{
            mb: 1,
            fontSize: 11,
            fontWeight: 600,
            color: 'text.disabled',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
          }}
        >
          {label}
        </Typography>
      )}
      <Box
        sx={{
          position: 'relative',
          width: size,
          height: size * 0.6,
          filter: `drop-shadow(0 0 8px ${glowColor})`,
        }}
      >
        <PieChart width={size} height={size}>
          <Pie
            data={data}
            cx={size / 2}
            cy={size / 2}
            startAngle={180}
            endAngle={0}
            innerRadius={size * 0.3}
            outerRadius={size * 0.45}
            dataKey="value"
            stroke="none"
          >
            <Cell fill={scoreColor} />
            <Cell fill="rgba(148, 163, 184, 0.08)" />
          </Pie>
        </PieChart>
        <Box
          sx={{
            position: 'absolute',
            top: '55%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            textAlign: 'center',
          }}
        >
          <Typography
            sx={{
              fontFamily: '"Sora", sans-serif',
              fontWeight: 700,
              fontSize: size * 0.15,
              color: 'text.primary',
              lineHeight: 1,
            }}
          >
            {normalizedScore}
          </Typography>
          <Typography sx={{ fontSize: 11, color: 'text.disabled', mt: 0.25 }}>
            {min === 0 ? `${normalizedScore} / ${max}` : getScoreLabel(normalizedScore)}
          </Typography>
        </Box>
      </Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', width: size * 0.8 }}>
        <Typography sx={{ fontSize: 10, color: 'text.secondary' }}>{min}</Typography>
        <Typography sx={{ fontSize: 10, color: 'text.secondary' }}>{max}</Typography>
      </Box>
    </Box>
  );
}
