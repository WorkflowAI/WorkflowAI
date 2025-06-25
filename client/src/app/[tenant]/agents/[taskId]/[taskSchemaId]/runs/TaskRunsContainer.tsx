'use client';

import { useCallback, useEffect, useMemo, useRef } from 'react';
import TaskRunModal from '@/components/TaskRunModal/TaskRunModal';
import { Paging } from '@/components/ui/Paging';
import { PageContainer } from '@/components/v2/PageContainer';
import { TASK_RUN_ID_PARAM } from '@/lib/constants';
import { useTaskSchemaParams } from '@/lib/hooks/useTaskParams';
import { useParsedSearchParams, useRedirectWithParams } from '@/lib/queryString';
import { getVersionsDictionary } from '@/lib/versionUtils';
import {
  useOrFetchSchema,
  useOrFetchTask,
  useOrFetchTaskRunsSearchFields,
  useOrFetchVersions,
  useOrSearchTaskRuns,
  useTaskRuns,
} from '@/store';
import { FieldQuery, SearchOperator } from '@/types/workflowAI';
import { TaskRunEmptyView } from './TaskRunEmptyView';
import { TaskRunSearchField } from './searchField/TaskRunSearchField';
import { TaskRunTableContent } from './taskRunTable/TaskRunTable';
import { TaskRunTableHeader } from './taskRunTable/TaskRunTableHeader';

const TASK_RUNS_PER_PAGE = 30;

export function TaskRunsContainer() {
  const { tenant, taskId, taskSchemaId: taskSchemaIdFromParams } = useTaskSchemaParams();

  const {
    page,
    field_name: fieldNamesValue,
    operator: operatorsValue,
    value: valuesValue,
  } = useParsedSearchParams('page', 'field_name', 'operator', 'value');

  const currentPage = page !== undefined ? Number(page) ?? 0 : 0;

  const { searchFields } = useOrFetchTaskRunsSearchFields(tenant, taskId, taskSchemaIdFromParams);

  const fieldParamsArray: Array<{
    fieldName: string;
    operator: string;
    value: string;
  }> = useMemo(() => {
    const fieldNames = fieldNamesValue?.split(',');
    const operators = operatorsValue?.split(',');
    const values = valuesValue?.split(',');

    const result: Array<{
      fieldName: string;
      operator: string;
      value: string;
    }> = [];

    fieldNames?.forEach((fieldName, index) => {
      if (!fieldName || !operators?.[index] || !values?.[index]) return;

      const entry = {
        fieldName,
        operator: operators?.[index],
        value: values?.[index],
      };

      result.push(entry);
    });

    return result;
  }, [fieldNamesValue, operatorsValue, valuesValue]);

  const fieldQueries: Array<FieldQuery> | undefined = useMemo(() => {
    if (fieldParamsArray.length === 0) return undefined;

    const result: Array<FieldQuery> = [];
    fieldParamsArray.forEach((fieldParam) => {
      const searchFieldsEntry = searchFields?.fields.find((candidate) => candidate.field_name === fieldParam.fieldName);

      if (!searchFieldsEntry) return undefined;
      const type = searchFieldsEntry.type;

      let convertedValue: string | number | boolean;
      switch (type) {
        case 'number':
        case 'integer':
          convertedValue = Number(fieldParam.value);
          break;
        case 'boolean':
          convertedValue = fieldParam.value.toLowerCase() === 'true';
          break;
        default:
          convertedValue = fieldParam.value;
      }

      result.push({
        field_name: fieldParam.fieldName,
        operator: fieldParam.operator as SearchOperator,
        values: [convertedValue],
        type: type,
      });
    });

    return result;
  }, [fieldParamsArray, searchFields]);

  const {
    taskRunItems = [],
    isInitialized: areTaskRunsInitialized,
    count = 0,
  } = useOrSearchTaskRuns(tenant, taskId, TASK_RUNS_PER_PAGE, currentPage * TASK_RUNS_PER_PAGE, fieldQueries);

  const taskRunIds = taskRunItems.map((taskRun) => taskRun.id);

  const { taskSchema, isInitialized: isTaskSchemaInitialized } = useOrFetchSchema(
    tenant,
    taskId,
    taskSchemaIdFromParams
  );

  const searchTaskRuns = useTaskRuns((state) => state.searchTaskRuns);

  const defaultOperatorsForFields: Record<string, string> = useMemo(() => {
    const result: Record<string, string> = {};
    searchFields?.fields.forEach((field) => {
      if (field.operators.length === 0) return;
      if (field.operators.includes('contains')) {
        result[field.field_name] = 'contains';
      } else if (field.operators.includes('in')) {
        result[field.field_name] = 'in';
      } else if (field.operators.includes('=')) {
        result[field.field_name] = '=';
      } else {
        result[field.field_name] = field.operators[0];
      }
    });
    return result;
  }, [searchFields]);

  const { [TASK_RUN_ID_PARAM]: runId } = useParsedSearchParams(TASK_RUN_ID_PARAM);

  const { versions } = useOrFetchVersions(tenant, taskId);

  const redirectWithParams = useRedirectWithParams();

  const onClose = useCallback(() => {
    redirectWithParams({
      params: { [TASK_RUN_ID_PARAM]: undefined },
    });
    searchTaskRuns({
      tenant,
      taskId,
      limit: TASK_RUNS_PER_PAGE,
      offset: currentPage * TASK_RUNS_PER_PAGE,
      fieldQueries: fieldQueries,
    });
  }, [redirectWithParams, searchTaskRuns, tenant, taskId, fieldQueries, currentPage]);

  const numberOfPages = Math.ceil(count / TASK_RUNS_PER_PAGE);

  const onPageSelected = useCallback(
    (number: number) => {
      redirectWithParams({
        params: { page: number },
      });
    },
    [redirectWithParams]
  );

  const lastPageZeroingParamsRef = useRef('');

  useEffect(() => {
    let newPageZeroingParams = 'none';
    fieldParamsArray.forEach((fieldParam) => {
      if (!!fieldParam.fieldName && !!fieldParam.operator && !!fieldParam.value) {
        newPageZeroingParams += `&field_name=${fieldParam.fieldName}&operator=${fieldParam.operator}&value=${fieldParam.value}`;
      }
    });

    if (newPageZeroingParams !== lastPageZeroingParamsRef.current) {
      lastPageZeroingParamsRef.current = newPageZeroingParams;
      onPageSelected(0);
    }
  }, [onPageSelected, fieldParamsArray]);

  const { task } = useOrFetchTask(tenant, taskId);

  const versionsDictionary = useMemo(() => {
    return getVersionsDictionary(versions);
  }, [versions]);

  if (!taskSchema) {
    return <div className='h-full w-full flex items-center justify-center'>No task schema found</div>;
  }

  return (
    <PageContainer
      task={task}
      name='Runs'
      showCopyLink={true}
      showSchema={false}
      documentationLink='https://docs.workflowai.com/concepts/runs'
      isInitialized={isTaskSchemaInitialized && !!task}
    >
      <div className='flex flex-col h-full w-full p-4'>
        <TaskRunSearchField
          className='mb-2'
          searchFields={searchFields}
          defaultOperatorsForFields={defaultOperatorsForFields}
        />

        {!!taskRunItems.length && (
          <>
            <TaskRunTableHeader />

            <TaskRunTableContent
              runItems={taskRunItems}
              versionsDictionary={versionsDictionary}
              redirectWithParams={redirectWithParams}
              isInitialized={areTaskRunsInitialized}
            />
          </>
        )}

        {!taskRunItems.length && areTaskRunsInitialized && (
          <TaskRunEmptyView
            title={!!fieldQueries && fieldQueries.length > 0 ? 'No runs match your search' : 'No runs yet'}
            subtitle={
              !!fieldQueries && fieldQueries.length > 0
                ? 'Try again with another search criteria'
                : 'When runs are created, they will be displayed here.'
            }
          />
        )}

        <Paging
          numberOfPages={numberOfPages}
          currentPage={currentPage}
          onPageSelected={onPageSelected}
          className='mt-4 py-2'
        />

        <TaskRunModal
          onClose={onClose}
          open={!!runId}
          showPlaygroundButton
          tenant={tenant}
          taskId={taskId}
          taskRunId={runId ?? ''}
          taskRunIds={taskRunIds}
          taskSchemaIdFromParams={taskSchemaIdFromParams}
        />
      </div>
    </PageContainer>
  );
}
