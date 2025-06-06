import { enableMapSet, produce } from 'immer';
import { create } from 'zustand';
import { client } from '@/lib/api';
import { WeeklyRun } from '@/types/workflowAI/models';

enableMapSet();

interface WeeklyRunsState {
  weeklyRuns: WeeklyRun[] | undefined;
  isLoading: boolean;
  isInitialized: boolean;

  fetchWeeklyRuns(weekCount: number): Promise<void>;
}

export const useWeeklyRuns = create<WeeklyRunsState>((set, get) => ({
  weeklyRuns: undefined,
  isLoading: false,
  isInitialized: false,

  fetchWeeklyRuns: async (weekCount: number) => {
    if (get().isLoading) return;

    set(
      produce((state) => {
        state.isLoading = true;
      })
    );

    const path = `/api/data/features/weekly-runs?week_count=${weekCount}`;

    try {
      const response = await client.get<{ items: WeeklyRun[] }>(path);
      set(
        produce((state) => {
          // We don't display the current week for now
          // TODO: this should be done backed side instead
          state.weeklyRuns = response.items.slice(0, response.items.length - 1);
        })
      );
    } catch (error) {
      console.error('Failed to fetch weekly runs', error);
    } finally {
      set(
        produce((state) => {
          state.isLoading = false;
          state.isInitialized = true;
        })
      );
    }
  },
}));
