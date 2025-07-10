type Props = {
  title: string;
  description?: string;
  number: number;
};

export function ProxyNewAgentSectionHeader(props: Props) {
  const { title, description, number } = props;
  return (
    <div className='flex flex-col w-full'>
      <div className='flex flex-row items-center gap-4'>
        <div className='w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center text-gray-500 text-[12px]'>
          {number}
        </div>
        <div className='text-gray-900 text-[18px] font-semibold font-lato'>{title}</div>
      </div>
      {description && (
        <div className='flex text-gray-500 text-[13px] font-normal font-lato pl-12 pt-2'>{description}</div>
      )}
    </div>
  );
}
