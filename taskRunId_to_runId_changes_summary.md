# Summary of taskRunId to runId Renaming Changes

This document summarizes all the changes made to rename URL parameters and variables from `taskRunId` to `runId` throughout the webapp.

## Key Changes Made:

### 1. Constants and Route Formatting
- **`client/src/lib/constants.ts`**: Changed `TASK_RUN_ID_PARAM` from `'taskRunId'` to `'runId'`
- **`client/src/lib/routeFormatter.ts`**: 
  - Updated `TaskRunParams` and `TaskRunPageSearchParams` types to use `runId`
  - Updated `taskRunRoute()` and `staticRunURL()` functions to use `runId` parameter

### 2. Hooks
- **`client/src/lib/hooks/useTaskParams.ts`**: Renamed `taskRunId` to `runId` in parameter extraction and return value
- **`client/src/lib/hooks/useCopy.ts`**: Updated `useCopyRunURL()` function parameter from `taskRunId` to `runId`

### 3. Component Props and Usage
- **`client/src/components/TaskRunModal/TaskRunModal.tsx`**: 
  - Updated `TaskRunModalProps` interface to use `runId`
  - Updated all usage throughout the component
  - Renamed `useRunIDParam()` hook parameters and return values
- **`client/src/components/TaskRunModal/FeedbackBox.tsx`**: Updated `FeedbackBoxContainerProps` to use `runId`
- **`client/src/components/TaskRunModal/TaskRunDetails.tsx`**: Updated prop usage to `runId`
- **`client/src/components/TaskRunModal/proxy/ProxyRunDetailsVersionMessagesView.tsx`**: Updated prop usage to `runId`

### 4. Store Files
- **`client/src/store/task_runs.ts`**: Updated `fetchTaskRun()` function parameter from `taskRunId` to `runId`
- **`client/src/store/task_run_transcriptions.ts`**: Updated `fetchTaskRunTranscriptions()` function parameter from `taskRunId` to `runId`
- **`client/src/store/task_run_reviews.ts`**: Updated `fetchTaskRunReviews()` and `respondToReview()` function parameters from `taskRunId` to `runId`
- **`client/src/store/run_completions.ts`**: Updated `fetchRunCompletion()` function parameter from `taskRunId` to `runId`
- **`client/src/store/fetchers.ts`**: Updated all fetcher hooks to use `runId` parameter names

### 5. Playground Components
- **`client/src/app/[tenant]/agents/[taskId]/[taskSchemaId]/playground/hooks/utils.ts`**: Renamed `formatTaskRunIdParam()` to `formatRunIdParam()`
- **`client/src/app/[tenant]/agents/[taskId]/[taskSchemaId]/playground/hooks/useFetchTaskRunUntilCreated.ts`**: Updated parameter from `taskRunId` to `runId`
- **`client/src/app/[tenant]/agents/[taskId]/[taskSchemaId]/playground/hooks/useInputGenerator.ts`**: Renamed `onResetTaskRunIds` to `onResetRunIds`
- **`client/src/app/[tenant]/agents/[taskId]/[taskSchemaId]/playground/hooks/usePlaygroundPersistedState.ts`**: 
  - Updated type definitions to use `runId1`, `runId2`, `runId3`
  - Renamed `handleSetTaskRunId` to `handleSetRunId`
  - Updated all related usage
- **`client/src/app/[tenant]/agents/[taskId]/[taskSchemaId]/playground/hooks/useSequentialRunIdUpdates.ts`**: 
  - **RENAMED FILE** to `useSequentialRunIdUpdates.ts`
  - Updated function name and all parameters to use `runId`
- **`client/src/app/[tenant]/agents/[taskId]/[taskSchemaId]/playground/playgroundOutput.tsx`**: Updated variable names from `taskRunId` to `runId`
- **`client/src/app/[tenant]/agents/[taskId]/[taskSchemaId]/playground/playgroundContent.tsx`**: 
  - Updated all parsed search params to use `runId` names
  - Updated hook calls and function references throughout

### 6. Landing Page URLs
- **`client/src/app/landing/LandingPage.tsx`**: Updated hardcoded URLs to use `runId` parameters
- **`client/src/app/landing/sections/StaticData/LandingStaticData.tsx`**: Updated all hardcoded demo URLs to use `runId` parameters

### 7. Additional Playground Files (mentioned in grep results)
- Various other playground-related files had their `taskRunId` references updated to `runId`

## URL Parameter Changes:
- URLs that previously used `?taskRunId=xxx` now use `?runId=xxx`
- URLs that previously used `&taskRunId1=xxx&taskRunId2=yyy&taskRunId3=zzz` now use `&runId1=xxx&runId2=yyy&runId3=zzz` 
- The `inputTaskRunId` parameter is now `inputRunId`

## Impact:
- All existing URLs with `taskRunId` parameters will need to be updated to use `runId` 
- The change affects both internal navigation and any bookmarked/shared URLs
- API calls and internal state management now consistently use `runId` terminology

## Files Created:
- `client/src/app/[tenant]/agents/[taskId]/[taskSchemaId]/playground/hooks/useSequentialRunIdUpdates.ts` (renamed from `useSequentialTaskRunIdUpdates.ts`)

## Files Deleted:
- `client/src/app/[tenant]/agents/[taskId]/[taskSchemaId]/playground/hooks/useSequentialTaskRunIdUpdates.ts`

This comprehensive renaming ensures consistency throughout the codebase and aligns with the goal of removing "task" terminology from URL parameters in favor of the simpler "run" terminology.