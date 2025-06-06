import { DeviceEq16Regular, Document16Regular, Image16Regular, Text16Regular } from '@fluentui/react-icons';
import { FieldType } from '@/lib/schemaUtils';
import { cn } from '@/lib/utils';

function iconForType(type: FieldType) {
  switch (type) {
    case 'string':
      return Text16Regular;
    case 'image':
      return Image16Regular;
    case 'document':
      return Document16Regular;
    case 'audio':
      return DeviceEq16Regular;
  }
  return undefined;
}

type TypeSelectorItemProps = {
  type: FieldType;
  isSelected: boolean;
  onClick: () => void;
};

function TypeSelectorItem(props: TypeSelectorItemProps) {
  const { type, isSelected, onClick } = props;
  const Icon = iconForType(type);

  return (
    <div
      className={cn(
        'flex items-center justify-center rounded-[2px] w-[30px] h-5 cursor-pointer text-gray-500 hover:text-gray-900',
        isSelected && 'bg-white border border-gray-300 shadow-sm text-gray-900'
      )}
      onClick={onClick}
    >
      {Icon && <Icon className='w-4 h-4' />}
    </div>
  );
}

type TypeSelectorProps = {
  keyPath: string;
  type: FieldType;
  onTypeChange: (keyPath: string, newType: FieldType) => void;
};

export function TypeSelector(props: TypeSelectorProps) {
  const { type, keyPath, onTypeChange } = props;

  const types: FieldType[] = ['string', 'image', 'document', 'audio'];

  return (
    <div className='flex flex-row h-7 items-center p-1 bg-gray-100/50 rounded-[2px] border border-gray-300'>
      {types.map((item) => (
        <TypeSelectorItem
          key={item}
          type={item}
          isSelected={item === type}
          onClick={() => onTypeChange(keyPath, item)}
        />
      ))}
    </div>
  );
}
