import { captureException } from '@sentry/nextjs';
import { NextRequest, NextResponse } from 'next/server';
import { serverFetch } from '@/lib/api/serverAPIClient';

const proxyHandler = async (req: NextRequest) => {
  try {
    const incomingUrl = new URL(req.url, `http://${req.headers.get('host')}`);
    const prefixToRemove = '/api/data';
    const pathWithoutPrefix = incomingUrl.pathname.replace(prefixToRemove, '');

    const targetUrl = `${pathWithoutPrefix}${incomingUrl.search}`;

    try {
      const options: RequestInit = {
        method: req.method,
        body: null as string | null,
      };

      if (req.method === 'POST' || req.method === 'PUT' || req.method === 'PATCH' || req.method === 'DELETE') {
        const bodyData = await req.text();
        if (bodyData) {
          options.body = bodyData;
        }
      }
      if (req.headers.get('Content-Type')) {
        options.headers = {
          'Content-Type': req.headers.get('Content-Type') ?? 'application/json',
          ...(options.headers ?? {}),
        };
      }

      const apiResponse = await serverFetch(targetUrl, options, true);
      const data = apiResponse.status === 204 ? null : await apiResponse.text();

      return new NextResponse(data, { status: apiResponse.status });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (error: any) {
      console.error('Error forwarding request', error);
      return new NextResponse(`An error occurred while forwarding the request: ${error?.message}`, {
        status: error?.status || 500,
      });
    }
  } catch (error) {
    console.error('Unknown error', error);
    captureException(error);
    if (error instanceof Error) {
      return new NextResponse(error.message, { status: 500 });
    }
    return new NextResponse('unknown error', { status: 500 });
  }
};

export const GET = proxyHandler;
export const POST = proxyHandler;
export const PUT = proxyHandler;
export const PATCH = proxyHandler;
export const DELETE = proxyHandler;
