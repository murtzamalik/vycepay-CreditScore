export interface RiskDriver {
  feature: string;
  label: string;
  impact: 'positive' | 'negative';
  shapValue: number;
  description: string;
}

export interface ScoreLiteResponse {
  nationalId: string;
  vyceScore: number;
  niqScore: number;
  scoreDate: string;
  modelVersion: string;
  cached: boolean;
}

export interface ScoreProResponse extends ScoreLiteResponse {
  riskDrivers: RiskDriver[];
  probabilityOfDefault: number;
  confidenceInterval: {
    lower: number;
    upper: number;
  };
}

export interface ScoreHistoryEntry {
  date: string;
  vyceScore: number;
  niqScore: number;
}

export interface BatchScoreRequest {
  nationalIds: string[];
  tier: 'lite' | 'pro';
}

export interface BatchScoreResponse {
  jobId: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  totalRequested: number;
  processed: number;
  results: ScoreLiteResponse[] | ScoreProResponse[];
}

export interface ScoresState {
  currentScore: ScoreProResponse | null;
  scoreHistory: ScoreHistoryEntry[];
  isLoading: boolean;
  error: string | null;
}
