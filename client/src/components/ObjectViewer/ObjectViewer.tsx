import { cx } from 'class-variance-authority';
import { cloneDeep, get, isEmpty } from 'lodash';
import { Plus } from 'lucide-react';
import { useCallback, useMemo } from 'react';
import { InitInputFromSchemaMode, initInputFromSchema } from '@/lib/schemaUtils';
import { ObjectKeyType } from '@/lib/schemaUtils';
import { JsonValueSchema, WithPartial, joinKeyPath } from '@/types';
import { CopyButtonWrapper } from '../buttons/CopyTextButton';
import { Button } from '../ui/Button';
import { FieldViewer, FieldViewerProps } from './FieldViewer';
import { ListItemSideline } from './ListItemSideline';
import { ReadonlyValue } from './ReadOnlyValue';
import { ValueViewerProps } from './utils';

type ObjectViewerContentProps = FieldViewerProps & {
  isRoot: boolean;
  isArray: boolean;
  isLast: boolean;
  isFirst: boolean;
};

function ObjectViewerContent(props: ObjectViewerContentProps) {
  const { isRoot, isArray, isLast, isFirst, ...rest } = props;

  return (
    // The FieldViewer is surrounded by spacing divs to add a gap between the fields while maintaining a junction between ListItemSidelines
    <div className='relative'>
      {isFirst && <div className={cx('py-1', { 'border-l border-gray-200': isArray })} />}
      <FieldViewer isLast={rest.editable ? false : isLast} {...rest} />
      <div
        className={cx({
          'border-l border-gray-200': isArray && (rest.editable || !isLast),
          'py-1': isLast,
          'py-2': !isLast,
        })}
      />
      {!isArray && !isRoot && !isLast && (
        <div className='w-full border-b border-gray-200 border-dashed absolute bottom-2' />
      )}
    </div>
  );
}

export type ObjectViewerProps = WithPartial<
  ValueViewerProps<any>, // eslint-disable-line @typescript-eslint/no-explicit-any
  'keyPath'
> & {
  isArray?: boolean;
  textColor?: string;
  flatFieldBasedConfigDict?: Record<string, ObjectKeyType>;
  errorsByKeypath?: Map<string, string>;
  flatFieldBasedConfigMode?: 'editable' | 'readonly' | 'evaluation';
  noOverflow?: boolean;
  blacklistedKeys?: Set<string>;
  prefixSlot?: React.ReactNode;
};

function extractKeys(schema: JsonValueSchema | undefined, value: unknown) {
  if (schema?.type === 'object' && !isEmpty(schema?.properties)) {
    return Object.keys(schema.properties);
  }
  return value ? Object.keys(value) : undefined;
}

export function ObjectViewer(props: ObjectViewerProps) {
  const {
    value: rawValue,
    referenceValue,
    className,
    isArray: rawIsArray,
    keyPath = '',
    onEdit,
    schema,
    editable,
    noOverflow,
    showTypes,
    blacklistedKeys,
    prefixSlot,
    ...rest
  } = props;

  const isArray = useMemo(() => {
    if (typeof rawIsArray === 'boolean') {
      return rawIsArray;
    }
    return Array.isArray(rawValue);
  }, [rawIsArray, rawValue]);

  const isRawValueNoKey = useMemo(() => {
    return typeof rawValue === 'string' && keyPath === '';
  }, [rawValue, keyPath]);

  const value = useMemo(() => {
    if (typeof rawValue === 'string') {
      return { content: rawValue };
    }
    if (
      !rawValue &&
      !editable &&
      (!!showTypes || !!rest.showDescriptionExamples) &&
      schema &&
      ('properties' in schema || 'items' in schema)
    ) {
      // It's a new mode only for the input and output schemas on Version page
      const onlyShowDescriptionsAndExamplesAndHideTypes = !showTypes && !!rest.showDescriptionExamples;

      return initInputFromSchema(
        schema,
        rest.defs,
        onlyShowDescriptionsAndExamplesAndHideTypes ? InitInputFromSchemaMode.NOTHING : InitInputFromSchemaMode.TYPE
      );
    }
    return rawValue;
  }, [rawValue, schema, rest.defs, editable, showTypes, rest.showDescriptionExamples]);

  const keys = useMemo(() => {
    const keys = extractKeys(schema, value);
    if (!blacklistedKeys) return keys;
    return keys?.filter((key) => !blacklistedKeys.has(key));
  }, [schema, value, blacklistedKeys]);

  const showArrayButtons = useMemo(() => isArray && editable, [isArray, editable]);

  const onAdd = useCallback(() => {
    const itemValue = rest.voidValue ? get(rest.voidValue, `${keyPath}[0]`) : null;
    const copiedItemValue = !!itemValue ? cloneDeep(itemValue) : itemValue;
    const newValue = [...(value || []), copiedItemValue];
    props.onEdit?.(keyPath, newValue);
  }, [keyPath, props, value, rest.voidValue]);

  const onRemoveItem = useCallback(
    (index: number) => {
      const newValue = [...value];
      newValue.splice(index, 1);
      props.onEdit?.(keyPath, newValue);
    },
    [keyPath, props, value]
  );

  const handleNullToggle = useCallback(
    (fieldKeyPath: string, isNull: boolean) => {
      const newValue = isNull ? undefined : cloneDeep(get(rest.voidValue, fieldKeyPath));
      props.onEdit?.(fieldKeyPath, newValue);
    },
    [props, rest.voidValue]
  );

  if ((schema?.type === 'object' || schema?.type === 'array') && typeof value !== 'object') {
    return (
      <ReadonlyValue
        {...props}
        // If the empty tag is rendered on its own in the Object card, we need to add some margin to it
        className={cx(className, { 'm-2': value === undefined })}
      />
    );
  }

  const isRoot = keyPath === '';

  if (isRoot && isRawValueNoKey) {
    if (props.hideCopyValue) {
      return (
        <div
          className={cx(className, 'flex-1 w-full h-full flex-col', {
            'overflow-auto': !noOverflow,
          })}
        >
          {prefixSlot}
          <div className='flex flex-col min-w-fit'>
            <div className='flex-1 whitespace-pre-wrap text-gray-700 text-[13px] px-3 py-2'>{rawValue}</div>
          </div>
        </div>
      );
    }
    return (
      <div
        className={cx(className, 'flex-1 w-full h-full flex-col', {
          'overflow-auto': !noOverflow,
        })}
      >
        {prefixSlot}
        <div className='flex flex-col min-w-fit'>
          <CopyButtonWrapper text={rawValue}>
            <div className='flex-1 whitespace-pre-wrap text-gray-700 text-[13px] px-3 py-2'>{rawValue}</div>
          </CopyButtonWrapper>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cx(className, 'flex-1 w-full h-full flex-col', {
        'overflow-auto': !noOverflow,
      })}
    >
      {prefixSlot}
      <div className={cx('flex flex-col min-w-fit', { 'px-1': isRoot && !isRawValueNoKey })}>
        {keys?.map((key, index) => (
          <ObjectViewerContent
            key={key}
            fieldKey={key}
            fieldValue={value?.[key]}
            fieldReferenceValue={referenceValue?.[key]}
            keyPath={keyPath}
            handleNullToggle={(isNull: boolean) => handleNullToggle(joinKeyPath(keyPath, key), isNull)}
            onEdit={onEdit}
            schema={schema}
            showTypes={showTypes}
            editable={editable}
            arrayIndex={isArray ? index : undefined}
            onRemove={showArrayButtons ? () => onRemoveItem(index) : undefined}
            isRoot={isRoot}
            isArray={isArray}
            isFirst={index === 0}
            isLast={index === keys.length - 1}
            {...rest}
          />
        ))}
        {showArrayButtons && (
          <div className='w-full flex gap-3 items-stretch pr-3'>
            <ListItemSideline isRoot={false} isLast arrayIndex={keys?.length ?? 0} />
            <Button lucideIcon={Plus} onClick={onAdd} variant='newDesign' className='w-full'>
              Add Item
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
