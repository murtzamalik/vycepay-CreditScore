import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type { ScoresState, ScoreProResponse, ScoreHistoryEntry } from '../../types/scores';

const initialState: ScoresState = {
  currentScore: null,
  scoreHistory: [],
  isLoading: false,
  error: null,
};

const scoresSlice = createSlice({
  name: 'scores',
  initialState,
  reducers: {
    setCurrentScore(state, action: PayloadAction<ScoreProResponse>) {
      state.currentScore = action.payload;
      state.error = null;
    },
    setScoreHistory(state, action: PayloadAction<ScoreHistoryEntry[]>) {
      state.scoreHistory = action.payload;
    },
    clearCurrentScore(state) {
      state.currentScore = null;
      state.scoreHistory = [];
      state.error = null;
    },
    setScoreError(state, action: PayloadAction<string>) {
      state.error = action.payload;
      state.isLoading = false;
    },
  },
});

export const { setCurrentScore, setScoreHistory, clearCurrentScore, setScoreError } =
  scoresSlice.actions;
export default scoresSlice.reducer;
