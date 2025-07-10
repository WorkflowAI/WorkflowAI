import { CurrencyInput } from './CurrencyInput';

type AmountToAddSectionProps = {
  amountToAdd: number | undefined;
  setAmountToAdd: (amount: number | undefined) => void;
};

export function AmountToAddSection(props: AmountToAddSectionProps) {
  const { amountToAdd, setAmountToAdd } = props;

  return (
    <div className='flex flex-col px-4 py-2 gap-1'>
      <div className='flex flex-col gap-1'>
        <div className='text-gray-900 font-medium text-[13px]'>Amount to Add</div>
        <CurrencyInput amount={amountToAdd} setAmount={setAmountToAdd} />
        <div className='text-gray-500 font-normal text-[12px]'>Enter an amount between $5 and $5000</div>
      </div>
    </div>
  );
}
