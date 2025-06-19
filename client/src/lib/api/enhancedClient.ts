import { EventSourceMessage, EventStreamContentType, fetchEventSource } from '@microsoft/fetch-event-source';
import { captureException } from '@sentry/nextjs';
import { StreamError } from '@/types/errors';
import { baseCookieProps } from '../token/anon';

interface RetryOptions {
  maxRetries?: number;
  initialDelay?: number;
  maxDelay?: number;
  backoffFactor?: number;
}

interface SSEOptions {
  timeout?: number;
  retryOptions?: RetryOptions;
  signal?: AbortSignal;
}

function extractErrorMessage(parsed: unknown) {
  if (typeof parsed !== 'object' || !parsed) {
    return undefined;
  }

  if ('error' in parsed) {
    if (typeof parsed.error === 'string') {
      return parsed.error;
    }
    if (
      typeof parsed.error === 'object' &&
      !!parsed.error &&
      'message' in parsed.error &&
      typeof parsed.error?.message === 'string'
    ) {
      return parsed.error.message;
    }
    return undefined;
  }
}

class EnhancedAPIError extends Error {
  constructor(
    message: string,
    public code?: string,
    public status?: number,
    public context?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'EnhancedAPIError';
  }
}

async function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function withRetry<T>(
  operation: () => Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  const {
    maxRetries = 3,
    initialDelay = 1000,
    maxDelay = 10000,
    backoffFactor = 2
  } = options;

  let lastError: Error;
  let currentDelay = initialDelay;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = error as Error;
      
      if (attempt === maxRetries) {
        break;
      }

      // Don't retry on certain error types
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw error;
      }

      await delay(Math.min(currentDelay, maxDelay));
      currentDelay *= backoffFactor;
    }
  }

  throw lastError!;
}

function parseSSEEvent(eventData: string, context?: Record<string, unknown>) {
  let parsed: unknown;

  try {
    parsed = JSON.parse(eventData);
  } catch (error) {
    const parseError = new EnhancedAPIError(
      'Failed to parse SSE event data',
      'SSE_PARSE_ERROR',
      undefined,
      { eventData, originalError: error, ...context }
    );
    
    captureException(parseError, {
      tags: { errorType: 'sse_parse_error' },
      extra: { eventData: eventData.substring(0, 1000), context }
    });
    
    throw parseError;
  }

  if (typeof parsed !== 'object' || !parsed) {
    throw new EnhancedAPIError(
      'Invalid SSE event format',
      'SSE_INVALID_FORMAT',
      undefined,
      { eventData, parsed, ...context }
    );
  }

  if ('error' in parsed) {
    const msg = extractErrorMessage(parsed);
    const errorContext = {
      eventData,
      parsed,
      runId: 'task_run_id' in parsed ? parsed.task_run_id : undefined,
      ...context
    };

    if ('task_run_id' in parsed && !!parsed.task_run_id) {
      throw new StreamError(msg ?? 'An unknown error occurred', msg === undefined, {
        ...errorContext,
        runId: parsed.task_run_id,
      });
    } else {
      throw new StreamError(msg ?? 'An unknown error occurred', msg === undefined, errorContext);
    }
  }

  return parsed;
}

export async function enhancedSSEClient<R, T>(
  path: string,
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  body: R,
  onMessage?: (ev: T) => void,
  options: SSEOptions = {}
): Promise<T> {
  const { timeout = 30000, retryOptions, signal } = options;
  
  let lastMessage: T | undefined;
  let timeoutId: NodeJS.Timeout | undefined;
  let abortController: AbortController | undefined;

  // Create abort controller for timeout
  if (timeout && !signal) {
    abortController = new AbortController();
    timeoutId = setTimeout(() => {
      abortController?.abort();
    }, timeout);
  }

  const effectiveSignal = signal || abortController?.signal;

  if (effectiveSignal?.aborted) {
    throw new EnhancedAPIError('Request was aborted', 'ABORTED');
  }

  try {
    const result = await withRetry(async () => {
      const headers = await requestHeaders('application/json');
      
      return new Promise<T>((resolve, reject) => {
        const eventSource = fetchEventSource(path, {
          onopen: async (response) => {
            if (response.ok && response.headers.get('content-type')?.includes(EventStreamContentType)) {
              return;
            }
            
            const error = new EnhancedAPIError(
              `SSE connection failed: ${response.status} ${response.statusText}`,
              'SSE_CONNECTION_FAILED',
              response.status,
              { path, method, headers: Object.fromEntries(response.headers.entries()) }
            );
            
            reject(error);
          },
          onmessage: (event: EventSourceMessage) => {
            try {
              const parsed = parseSSEEvent(event.data, { path, method }) as T;
              lastMessage = parsed;
              onMessage?.(parsed);
            } catch (error) {
              reject(error);
            }
          },
          onerror: (error: unknown) => {
            if (error instanceof StreamError || error instanceof EnhancedAPIError) {
              if (error instanceof StreamError && error.capture) {
                captureException(error, { 
                  extra: { ...error.extra, path, method },
                  tags: { errorType: 'sse_stream_error' }
                });
              }
              reject(error);
            } else {
              const enhancedError = new EnhancedAPIError(
                'SSE stream error',
                'SSE_STREAM_ERROR',
                undefined,
                { originalError: error, path, method }
              );
              
              captureException(enhancedError, {
                tags: { errorType: 'sse_unknown_error' },
                extra: { path, method }
              });
              
              reject(enhancedError);
            }
          },
          onclose: () => {
            if (lastMessage) {
              resolve(lastMessage);
            } else {
              reject(new EnhancedAPIError(
                'SSE stream closed without receiving any messages',
                'SSE_NO_MESSAGES',
                undefined,
                { path, method }
              ));
            }
          },
          method,
          headers,
          body: method !== 'GET' ? JSON.stringify({ ...body, stream: true }) : undefined,
          openWhenHidden: true,
          keepalive: false,
          signal: effectiveSignal,
        });
      });
    }, retryOptions);

    return result;
  } finally {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  }
}

// Placeholder for requestHeaders function - should be imported from existing code
async function requestHeaders(contentType: string): Promise<Record<string, string>> {
  // This should be implemented based on existing authentication logic
  return {
    'Content-Type': contentType,
    // Add other headers as needed
  };
}