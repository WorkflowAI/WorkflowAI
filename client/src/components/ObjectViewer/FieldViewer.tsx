import { captureException } from '@sentry/nextjs';
import { cx } from 'class-variance-authority';
import { get, isEqual } from 'lodash';
import { useCallback, useMemo, useState } from 'react';
import { viewerType } from '@/lib/schemaUtils';
import { ObjectKeyType } from '@/lib/schemaUtils';
import { extractSchemaRefName, getSubSchema } from '@/types';
import { EvaluationButtonView } from './EvaluationButtonView';
import { FieldDescriptionExamples } from './FieldDescriptionExamples';
import { FieldViewerContent } from './FieldViewerContent';
import { FieldViewerError } from './FieldViewerError';
import { FieldViewerLabel } from './FieldViewerLabel';
import { ListItemSideline } from './ListItemSideline';
import { ValueViewerProps } from './utils';

export interface FieldViewerProps extends Omit<ValueViewerProps<unknown>, 'value' | 'referenceValue'> {
  className?: string;
  defaultExpanded?: boolean;
  fieldKey: string;
  fieldValue: unknown;
  fieldReferenceValue?: unknown;
  isLast?: boolean;
  handleNullToggle: (isNull: boolean) => void;
  textColor?: string;
  flatFieldBasedConfigDict?: Record<string, ObjectKeyType>;
  errorsByKeypath?: Map<string, string>;
  flatFieldBasedConfigMode?: 'editable' | 'readonly' | 'evaluation';
  arrayIndex: number | undefined;
  onRemove: (() => void) | undefined;
}

export function FieldViewer(props: FieldViewerProps) {
  const {
    className,
    defaultExpanded = true,
    defs,
    editable,
    fieldKey,
    fieldValue,
    fieldReferenceValue,
    handleNullToggle,
    keyPath,
    onEdit,
    onTypeChange,
    schema,
    isLast = false,
    textColor,
    flatFieldBasedConfigDict,
    errorsByKeypath,
    flatFieldBasedConfigMode,
    arrayIndex,
    onRemove,
    ...rest
  } = props;

  const isRoot = fieldKey === '';

  const fieldKeyPath = useMemo(() => {
    if (keyPath) {
      return keyPath + '.' + fieldKey;
    }
    return fieldKey;
  }, [fieldKey, keyPath]);

  const fieldKeyError = errorsByKeypath?.get(fieldKeyPath);
  const isError = !!fieldKeyError;

  const isValueOverriden = useMemo(
    () => !!rest.originalVal && !isEqual(get(rest.originalVal, fieldKeyPath), fieldValue),
    [fieldValue, rest.originalVal, fieldKeyPath]
  );

  const subSchema = useMemo(() => {
    if (!schema) {
      return undefined;
    }
    try {
      return getSubSchema(schema, defs, fieldKey);
    } catch (e) {
      console.error(e);
      captureException(e, {
        extra: {
          fieldKey,
          schema,
          defs,
        },
      });
      return undefined;
    }
  }, [schema, defs, fieldKey]);

  const subSchemaFieldType = useMemo(() => {
    if (!subSchema) {
      return undefined;
    }
    return viewerType(subSchema, defs, fieldValue);
  }, [subSchema, defs, fieldValue]);

  const isArrayObject = subSchemaFieldType === 'object' && arrayIndex !== undefined;

  const isRequired = useMemo(() => {
    if (schema && 'required' in schema) {
      return schema.required?.includes(fieldKey) || false;
    }
    return false;
  }, [schema, fieldKey]);

  const schemaRefName = useMemo(() => extractSchemaRefName(schema, fieldKey), [schema, fieldKey]);

  const isExpandable = useMemo(
    () => !!subSchemaFieldType && ['object', 'array'].includes(subSchemaFieldType),
    [subSchemaFieldType]
  );

  const [isValueVisible, setIsValueVisible] = useState(isExpandable ? defaultExpanded : true);

  const toggleValueVisible = useCallback(() => {
    setIsValueVisible((prev) => !prev);
  }, []);

  const isNull = fieldValue === null || fieldValue === undefined;
  const onNullClick = useCallback(() => {
    handleNullToggle(!isNull);
  }, [isNull, handleNullToggle]);
  const textColorToUse = isValueOverriden ? 'text-red-400' : textColor ?? 'text-gray-600';

  const columnLayout = isExpandable || !rest.showTypes;
  const isParentArray = arrayIndex !== undefined;

  const [isHovering, setIsHovering] = useState(false);

  const fieldViewerLabel = (
    <FieldViewerLabel
      textColor={textColorToUse}
      toggleValueVisible={toggleValueVisible}
      showDescriptionExamples={rest.showDescriptionExamples}
      isValueVisible={isValueVisible}
      isNull={isNull}
      onNullClick={rest.allowNullToggle ? onNullClick : undefined}
      fieldKey={fieldKey}
      fieldKeyPath={fieldKeyPath}
      editable={editable}
      isRequired={isRequired}
      subSchemaFieldType={subSchemaFieldType}
      subSchema={subSchema}
      isParentArray={isParentArray}
      isArrayObject={isArrayObject}
      onRemove={isArrayObject ? onRemove : undefined}
      handleFieldKeyPositionChange={rest.handleFieldKeyPositionChange}
      isError={isError}
      showExamplesHints={rest.showExamplesHints}
      showTypes={!!rest.showTypes}
      onShowEditSchemaModal={rest.onShowEditSchemaModal}
      onShowEditDescriptionModal={rest.onShowEditDescriptionModal}
      showDescriptionPopover={rest.showDescriptionPopover !== false}
      onTypeChange={onTypeChange}
      schemaRefName={schemaRefName}
      isHoveringOverValue={isHovering}
    />
  );

  const [evaluationEditOn, setEvaluationEditOn] = useState(false);

  const showExamples = rest.showDescriptionExamples === 'all';

  return (
    <div>
      <div className={cx(className, 'flex items-stretch')}>
        <ListItemSideline arrayIndex={arrayIndex} isRoot={isRoot} isLast={isLast} showTypes={!!rest.showTypes} />
        <div className='px-3 flex items-start w-full'>
          {columnLayout ? (
            <div
              className='flex-1 flex flex-col w-full items-start'
              onMouseEnter={() => setIsHovering(true)}
              onMouseLeave={() => setIsHovering(false)}
            >
              {fieldViewerLabel}
              {rest.showDescriptionExamples && (
                <FieldDescriptionExamples
                  schema={subSchema}
                  fieldType={subSchemaFieldType}
                  className={cx('w-full px-3 py-2', {
                    'pl-7': subSchemaFieldType === 'array',
                    'bg-white border-l border-r border-gray-200': subSchemaFieldType === 'object',
                  })}
                  showExamples={showExamples}
                  onShowEditDescriptionModal={rest.onShowEditDescriptionModal}
                />
              )}
              {isValueVisible && (
                <FieldViewerContent
                  value={fieldValue}
                  referenceValue={fieldReferenceValue}
                  editable={editable}
                  onEdit={onEdit}
                  schema={subSchema}
                  subSchemaFieldType={subSchemaFieldType}
                  isRoot={isRoot}
                  defs={defs}
                  keyPath={fieldKeyPath}
                  schemaRefName={schemaRefName}
                  defaultExpanded={defaultExpanded}
                  textColor={textColorToUse}
                  isArrayObject={isArrayObject}
                  onRemove={!isArrayObject ? onRemove : undefined}
                  flatFieldBasedConfigDict={flatFieldBasedConfigDict}
                  errorsByKeypath={errorsByKeypath}
                  flatFieldBasedConfigMode={flatFieldBasedConfigMode}
                  className='w-full text-[13px]'
                  columnDisplay
                  {...rest}
                  isError={isError}
                  onTypeChange={onTypeChange}
                />
              )}
            </div>
          ) : (
            <div className='flex-1 flex flex-col w-full'>
              <div className='flex-1 flex flex-row w-full items-center'>
                {fieldViewerLabel}
                {isValueVisible && (
                  <div className='flex flex-row w-full'>
                    <div
                      onMouseEnter={() => setIsHovering(true)}
                      onMouseLeave={() => setIsHovering(false)}
                      className={cx('flex items-center w-full')}
                    >
                      <FieldViewerContent
                        value={fieldValue}
                        referenceValue={fieldReferenceValue}
                        editable={editable || evaluationEditOn}
                        onEdit={onEdit}
                        schema={subSchema}
                        subSchemaFieldType={subSchemaFieldType}
                        isRoot={isRoot}
                        className='text-[13px]'
                        defs={defs}
                        keyPath={fieldKeyPath}
                        schemaRefName={schemaRefName}
                        defaultExpanded={defaultExpanded}
                        textColor={textColorToUse}
                        onRemove={!isArrayObject ? onRemove : undefined}
                        isParentArray={isParentArray}
                        flatFieldBasedConfigDict={flatFieldBasedConfigDict}
                        errorsByKeypath={errorsByKeypath}
                        {...rest}
                        isError={isError}
                        onTypeChange={onTypeChange}
                      />
                    </div>

                    <EvaluationButtonView
                      fieldValue={fieldValue}
                      fieldKey={fieldKey}
                      keyPath={keyPath}
                      flatFieldBasedConfigDict={flatFieldBasedConfigDict}
                      flatFieldBasedConfigMode={flatFieldBasedConfigMode}
                      isHovering={isHovering}
                      onEdit={onEdit}
                      updateEditMode={setEvaluationEditOn}
                      isEditModeOn={evaluationEditOn}
                    />
                  </div>
                )}
              </div>
              {rest.showDescriptionExamples && (
                <FieldDescriptionExamples
                  schema={subSchema}
                  className='pt-2'
                  fieldType={subSchemaFieldType}
                  showExamples={showExamples}
                  onShowEditDescriptionModal={rest.onShowEditDescriptionModal}
                />
              )}
            </div>
          )}
        </div>
      </div>
      <FieldViewerError error={fieldKeyError} />
    </div>
  );
}
