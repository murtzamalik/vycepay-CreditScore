import { baseApi } from './baseApi';
import type {
  ScoreLiteResponse,
  ScoreProResponse,
  ScoreHistoryEntry,
  BatchScoreRequest,
  BatchScoreResponse,
} from '../types/scores';

/* ------------------------------------------------------------------ */
/* Backend response shapes (snake_case)                                */
/* ------------------------------------------------------------------ */

interface BackendLiteResponse {
  vyce_score: number;
  niq_score: number;
  score_date: string;
  score_version: string;
  subject_id: string;
  metadata: {
    model_version: string;
    feature_date: string;
    data_quality: string;
  };
}

interface BackendRiskDriver {
  factor: string;
  impact: 'positive' | 'negative';
  description: string;
  contribution: number;
}

interface BackendProResponse {
  vyce_score: number;
  niq_score: number;
  risk_drivers: BackendRiskDriver[];
  score_date: string;
  model_version: string;
  prediction_horizon: string;
  confidence_interval: { lower: number; upper: number };
  interpretation: { risk_level: string; interpretation: string };
  history?: BackendHistoryItem[];
}

interface BackendHistoryItem {
  vyce_score: number;
  niq_score: number;
  score_date: string;
  model_version: string;
}

/* ------------------------------------------------------------------ */
/* Transform helpers                                                   */
/* ------------------------------------------------------------------ */

function transformLite(raw: BackendLiteResponse, nationalId: string): ScoreLiteResponse {
  return {
    nationalId,
    vyceScore: raw.vyce_score,
    niqScore: raw.niq_score,
    scoreDate: raw.score_date,
    modelVersion: raw.metadata.model_version,
    cached: false,
  };
}

function transformPro(raw: BackendProResponse, nationalId: string): ScoreProResponse {
  return {
    nationalId,
    vyceScore: raw.vyce_score,
    niqScore: raw.niq_score,
    scoreDate: raw.score_date,
    modelVersion: raw.model_version,
    cached: false,
    riskDrivers: raw.risk_drivers.map((d) => ({
      feature: d.factor,
      label: d.factor,
      impact: d.impact,
      shapValue: d.contribution / 100,
      description: d.description,
    })),
    probabilityOfDefault: 0,
    confidenceInterval: raw.confidence_interval,
  };
}

/* ------------------------------------------------------------------ */
/* RTK Query endpoints                                                 */
/* ------------------------------------------------------------------ */

export const scoresApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getLiteScore: builder.query<ScoreLiteResponse, string>({
      query: (nationalId) => `/scores/lite/${nationalId}`,
      transformResponse: (raw: BackendLiteResponse, _meta, nationalId) =>
        transformLite(raw, nationalId),
      providesTags: (_result, _error, nationalId) => [
        { type: 'Score', id: nationalId },
      ],
    }),
    getProScore: builder.query<ScoreProResponse, string>({
      query: (nationalId) => `/scores/pro/${nationalId}`,
      transformResponse: (raw: BackendProResponse, _meta, nationalId) =>
        transformPro(raw, nationalId),
      providesTags: (_result, _error, nationalId) => [
        { type: 'Score', id: nationalId },
      ],
    }),
    getScoreHistory: builder.query<ScoreHistoryEntry[], string>({
      query: (nationalId) => `/scores/pro/${nationalId}?includeHistory=true`,
      transformResponse: (raw: BackendProResponse) =>
        (raw.history ?? []).map((h) => ({
          date: h.score_date,
          vyceScore: h.vyce_score,
          niqScore: h.niq_score,
        })),
      providesTags: (_result, _error, nationalId) => [
        { type: 'ScoreHistory', id: nationalId },
      ],
    }),
    batchScore: builder.mutation<BatchScoreResponse, BatchScoreRequest>({
      query: (body) => ({
        url: '/scores/batch',
        method: 'POST',
        body,
      }),
    }),
  }),
});

export const {
  useLazyGetLiteScoreQuery,
  useLazyGetProScoreQuery,
  useGetScoreHistoryQuery,
  useBatchScoreMutation,
} = scoresApi;
