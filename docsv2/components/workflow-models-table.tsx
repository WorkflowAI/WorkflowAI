'use client';

interface ModelSupports {
  input_image: boolean;
  input_pdf: boolean;
  input_audio: boolean;
  output_image: boolean;
  output_text: boolean;
  audio_only: boolean;
  support_input_schema: boolean;
  parallel_tool_calls: boolean;
  tool_calling: boolean;
}

interface Model {
  id: string;
  object: string;
  created: number;
  owned_by: string;
  display_name: string;
  icon_url: string;
  supports: ModelSupports;
}

interface WorkflowModelsTableProps {
  models: Model[];
}

export function WorkflowModelsTable({ models }: WorkflowModelsTableProps) {
  const FeatureIcon = ({ supported }: { supported: boolean }) =>
    supported ? (
      <span className='text-green-600 dark:text-green-400'>✓</span>
    ) : (
      <span className='text-gray-400 dark:text-gray-600'>—</span>
    );

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <div className='overflow-x-auto'>
      <table className='w-full border-collapse'>
        <thead>
          <tr className='border-b border-border'>
            <th className='text-left p-2 font-semibold'>Model</th>
            <th className='text-left p-2 font-semibold'>Provider</th>
            <th className='text-left p-2 font-semibold'>Released</th>
            <th className='text-center p-2 font-semibold' title='Input Image'>
              🖼️
            </th>
            <th className='text-center p-2 font-semibold' title='Input PDF'>
              📄
            </th>
            <th className='text-center p-2 font-semibold' title='Input Audio'>
              🎵
            </th>
            <th className='text-center p-2 font-semibold' title='Output Image'>
              🎨
            </th>
            <th className='text-center p-2 font-semibold' title='Output Text'>
              💬
            </th>
            <th className='text-center p-2 font-semibold' title='Tool Calling'>
              🔧
            </th>
          </tr>
        </thead>
        <tbody>
          {models.map((model) => (
            <tr key={model.id} className='border-b border-border hover:bg-accent/50 transition-colors'>
              <td className='p-2'>
                <div className='flex items-center gap-2'>
                  {model.icon_url && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={model.icon_url} alt={model.owned_by} className='w-5 h-5' />
                  )}
                  <div>
                    <div className='font-medium'>{model.display_name}</div>
                    <div className='text-xs text-muted-foreground'>{model.id}</div>
                  </div>
                </div>
              </td>
              <td className='p-2 text-sm'>{model.owned_by}</td>
              <td className='p-2 text-sm text-muted-foreground'>{formatDate(model.created)}</td>
              <td className='text-center p-2'>
                <FeatureIcon supported={model.supports.input_image} />
              </td>
              <td className='text-center p-2'>
                <FeatureIcon supported={model.supports.input_pdf} />
              </td>
              <td className='text-center p-2'>
                <FeatureIcon supported={model.supports.input_audio} />
              </td>
              <td className='text-center p-2'>
                <FeatureIcon supported={model.supports.output_image} />
              </td>
              <td className='text-center p-2'>
                <FeatureIcon supported={model.supports.output_text} />
              </td>
              <td className='text-center p-2'>
                <FeatureIcon supported={model.supports.tool_calling} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className='mt-4 p-4 bg-muted rounded-lg'>
        <h4 className='font-semibold mb-2'>Legend:</h4>
        <div className='grid grid-cols-2 md:grid-cols-4 gap-2 text-sm'>
          <div>🖼️ Input Image</div>
          <div>📄 Input PDF</div>
          <div>🎵 Input Audio</div>
          <div>🎨 Output Image</div>
          <div>💬 Output Text</div>
          <div>🔧 Tool Calling</div>
        </div>
      </div>
    </div>
  );
}
