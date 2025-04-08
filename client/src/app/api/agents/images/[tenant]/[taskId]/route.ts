import { ImageResponse } from 'next/og';
import { NextResponse } from 'next/server';
import React from 'react';
import { BACKEND_API_URL } from '@/lib/constants';
import { JsonSchema } from '@/types/json_schema';
import { RunV1 } from '@/types/workflowAI';

export const runtime = 'edge';

const lato = fetch(new URL('@/app/fonts/Lato/Lato-Regular.ttf', import.meta.url)).then((res) => res.arrayBuffer());

function getEntriesFromOutput(output: JsonSchema, parentKey = ''): { key: string; value: string }[] {
  const entries: { key: string; value: string }[] = [];

  if (typeof output === 'string' || typeof output === 'number' || typeof output === 'boolean') {
    entries.push({
      key: parentKey + ':',
      value: String(output),
    });
    return entries;
  }

  if (!output || typeof output !== 'object') {
    return entries;
  }

  if (Array.isArray(output)) {
    output.forEach((item, index) => {
      entries.push(...getEntriesFromOutput(item, `${parentKey}[${index}]`));
    });
    return entries;
  }

  Object.entries(output).forEach(([key, value]) => {
    const currentKey = parentKey ? `${parentKey}.${key}` : key;

    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      entries.push({
        key: key + ':',
        value: String(value),
      });
    } else if (value && typeof value === 'object') {
      entries.push(...getEntriesFromOutput(value as JsonSchema, currentKey));
    }
  });

  return entries;
}

export async function GET(request: Request, { params }: { params: { tenant: string; taskId: string } }) {
  const { tenant, taskId } = params;

  const urlForLatestRun = `${BACKEND_API_URL}/v1/${tenant}/agents/${taskId}/runs/latest?is_success=true`;

  try {
    const run: RunV1 = await fetch(urlForLatestRun).then((res) => res.json());
    const entries = getEntriesFromOutput(run.task_output);

    if (entries.length === 0) {
      return new NextResponse('No entries found', {
        status: 404,
      });
    }

    const lineClamp = entries.length > 2 ? '2' : '10';

    return new ImageResponse(
      React.createElement(
        'div',
        {
          style: {
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'flex-start',
            flexDirection: 'column',
            justifyContent: 'flex-start',
            backgroundImage:
              'url(https://workflowai.blob.core.windows.net/workflowai-public/MetaLinkPreviewBackground.jpg)',
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            backgroundRepeat: 'no-repeat',
            paddingTop: '60px',
            paddingLeft: '130px',
            paddingRight: '130px',
            overflow: 'hidden',
            fontFamily: 'Lato',
            WebkitFontSmoothing: 'antialiased',
            MozOsxFontSmoothing: 'grayscale',
          },
        },
        React.createElement(
          'div',
          {
            style: {
              width: '100%',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'flex-start',
              alignItems: 'flex-start',
              overflow: 'hidden',
              gap: '13px',
              fontSize: '2.1875rem',
            },
          },
          // Entry 0
          React.createElement(
            'div',
            { style: { color: '#6B7280', zIndex: 1, textAlign: 'left', paddingTop: '30px' } },
            entries[0]?.key || ''
          ),
          React.createElement(
            'div',
            {
              style: {
                color: '#374151',
                zIndex: 1,
                textAlign: 'left',
                display: '-webkit-box',
                WebkitLineClamp: lineClamp,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                lineHeight: '1.5',
              },
            },
            entries[0]?.value || ''
          ),

          // Entry 1
          React.createElement(
            'div',
            {
              style: {
                color: '#6B7280',
                zIndex: 1,
                textAlign: 'left',
                paddingTop: '30px',
              },
            },
            entries[1]?.key || ''
          ),
          React.createElement(
            'div',
            {
              style: {
                color: '#374151',
                zIndex: 1,
                textAlign: 'left',
                display: '-webkit-box',
                WebkitLineClamp: lineClamp,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                lineHeight: '1.5',
              },
            },
            entries[1]?.value || ''
          ),

          // Entry 2
          React.createElement(
            'div',
            {
              style: {
                color: '#6B7280',
                zIndex: 1,
                textAlign: 'left',
                paddingTop: '30px',
              },
            },
            entries[2]?.key || ''
          ),
          React.createElement(
            'div',
            {
              style: {
                color: '#374151',
                zIndex: 1,
                textAlign: 'left',
                display: '-webkit-box',
                WebkitLineClamp: lineClamp,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                lineHeight: '1.5',
              },
            },
            entries[2]?.value || ''
          ),

          // Entry 3
          React.createElement(
            'div',
            {
              style: {
                color: '#6B7280',
                zIndex: 1,
                textAlign: 'left',
                paddingTop: '30px',
              },
            },
            entries[3]?.key || ''
          ),
          React.createElement(
            'div',
            {
              style: {
                color: '#374151',
                zIndex: 1,
                textAlign: 'left',
                display: '-webkit-box',
                WebkitLineClamp: lineClamp,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                lineHeight: '1.5',
              },
            },
            entries[3]?.value || ''
          )
        )
      ),
      {
        width: 1200,
        height: 630,
        fonts: [
          {
            name: 'Lato',
            data: await lato,
            style: 'normal',
            weight: 400,
          },
        ],
      }
    );
  } catch {
    return new NextResponse('Error fetching agent run', {
      status: 500,
    });
  }
}
