import { EventSourceMessage, EventStreamContentType, fetchEventSource } from '@microsoft/fetch-event-source';
import { captureException } from '@sentry/nextjs';
import { StreamError } from '@/types/errors';
import { baseCookieProps } from '../token/anon';

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

export class RequestError extends Error {
  status: number;
  path: string;
  response: Response;

  constructor(status: number, path: string, response: Response) {
    super(`Failed to request ${path}`);

    this.path = path;
    this.status = status;
    this.response = response;
  }

  async humanReadableMessage() {
    try {
      const parsed = await this.response.json();
      return extractErrorMessage(parsed);
    } catch (e) {
      return this.message;
    }
  }
}

export enum Method {
  GET = 'GET',
  POST = 'POST',
  DELETE = 'DELETE',
  PUT = 'PUT',
  PATCH = 'PATCH',
}

async function onOpenStream(response: Response) {
  const contentType = response.headers.get('content-type');
  if (!contentType?.startsWith(EventStreamContentType)) {
    // There was an error with the request, we should not have a 200 status code
    let errorMessage = 'An internal error occurred while streaming the response';
    let capture = false;
    let title: string | undefined = undefined;
    switch (response.status) {
      case 200:
        capture = true;
        break;
      case 429:
        title = 'Rate limit exceeded';
        errorMessage =
          'Apologies, our system is currently handling more requests than it can process.\n\nOur team has already been alerted and is working hard to resolve the situation.\nPlease try again shortly.';
        break;
      case 402:
        title = 'Out of LLM Credits';
        errorMessage =
          'You have used all your LLM credits from WorkflowAI.\n\nIn order to continue running tasks with WorkflowAI, you will need to purchase more.';
        break;
      default:
        capture = true;
        break;
    }
    throw new StreamError(errorMessage, capture, {
      status: response.status,
      path: response.url,
      text: await response.text(),
      title,
    });
  }
}

let uniqueAnonIdPromise: Promise<string | undefined> | undefined;

function setCookie(name: string, value: string) {
  const props = baseCookieProps();
  const joined = Object.entries(props)
    .map(([key, value]) => `${key}=${value}`)
    .join('; ');
  document.cookie = `${name}=${value}; ${joined}`;
}

export function getOrCreateUniqueId() {
  // If the cookie is already set, extract and return it.
  const cookieMatch = document.cookie.match(/x-unknown-user-id=([^;]+)/);
  if (cookieMatch) {
    return Promise.resolve(cookieMatch[1]);
  }

  // If generation is already in progress, return the promise.
  if (uniqueAnonIdPromise) {
    return uniqueAnonIdPromise;
  }

  // Otherwise, create the promise and generate the ID.
  uniqueAnonIdPromise = new Promise((resolve) => {
    try {
      const id = crypto.randomUUID();
      setCookie('x-unknown-user-id', id);
      resolve(id);
    } catch (e) {
      captureException(e);
      resolve(undefined);
    }
  });

  return uniqueAnonIdPromise;
}

async function headersWithoutToken(contentType: string | undefined) {
  const headers: Record<string, string> = {
    'x-workflowai-source': 'web',
  };

  if (contentType) {
    headers['Content-Type'] = contentType;
  }

  if (process.env.NEXT_PUBLIC_RELEASE_NAME) {
    headers['x-workflowai-version'] = process.env.NEXT_PUBLIC_RELEASE_NAME;
  }
  const unknownUserId = await getOrCreateUniqueId();
  if (unknownUserId) {
    headers['x-workflowai-unknown-user-id'] = unknownUserId;
  }
  return headers;
}

async function getOrCreateToken() {
  const headers = await headersWithoutToken('application/json');
  const res = await fetch('/api/jwt', headers);
  const raw: { token: string } = await res.json();
  return raw.token;
}

async function requestHeaders(contentType: string | undefined): Promise<Record<string, string>> {
  const headers = await headersWithoutToken(contentType);

  try {
    // TODO: We always refresh the token here
    // which is used when streaming. This is to avoid having to use
    // clerk hooks to validate that the token is valid
    // We will no longer have the issue when we just use the clerk token
    const token = await getOrCreateToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  } catch (e) {
    // This should not happen. If it does, we will let the server handle
    // the token creation
    captureException(e);
  }
  return headers;
}

async function fetchWrapper<T, R = unknown>(
  path: string,
  {
    method,
    body,
    signal,
  }: {
    method: Method;
    body?: T;
    signal?: AbortSignal;
  }
): Promise<R> {
  // We don't compute a token here
  // It will be added server side automatically. What's important is that
  // the anon user id is unique.
  // This will change when we start using clerk tokens directly
  const headers = await headersWithoutToken('application/json');

  const res = await fetch(path, {
    method,
    headers,
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    const error = new RequestError(res.status, path, res);
    captureException(error, {
      tags: { path },
      extra: { path, status: res.status, raw: await res.text() },
    });
    throw error;
  }
  if (res.status === 204) {
    return undefined as R;
  }
  const toJSON = await res.json();
  return toJSON;
}

export async function get<T>(path: string, query?: URLSearchParams): Promise<T> {
  const url = query ? `${path}?${query.toString()}` : path;

  return fetchWrapper(url, { method: Method.GET });
}

export async function post<T, R = unknown>(path: string, body: T, signal?: AbortSignal): Promise<R> {
  return fetchWrapper(path, { method: Method.POST, body, signal });
}

export async function put<T, R = unknown>(path: string, body: T): Promise<R> {
  return fetchWrapper(path, { method: Method.PUT, body });
}

export async function patch<T, R = unknown>(path: string, body: T): Promise<R> {
  return fetchWrapper(path, { method: Method.PATCH, body });
}

export async function del<T = undefined, R = unknown>(path: string, body?: T): Promise<R> {
  return fetchWrapper(path, { method: Method.DELETE, body });
}

export async function uploadFile<R = unknown>(
  path: string,
  body: FormData,
  onProgress?: (progress: number) => void
): Promise<R> {
  return new Promise(async (resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const headers = await requestHeaders(undefined);

    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable && !!onProgress) {
        const percentComplete = event.loaded / event.total;
        onProgress(percentComplete);
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const response = JSON.parse(xhr.responseText);
          resolve(response);
        } catch (e) {
          reject(new Error('Invalid response format'));
        }
      } else {
        reject(new Error(`Upload failed with status ${xhr.status}`));
      }
    });

    xhr.addEventListener('error', () => reject(new Error('Upload failed')));
    xhr.addEventListener('abort', () => reject(new Error('Upload aborted')));

    xhr.open('POST', path);
    Object.entries(headers).forEach(([key, value]) => {
      xhr.setRequestHeader(key, value);
    });
    xhr.send(body);
  });
}

function parseSSEEvent(eventData: string) {
  let parsed: unknown;

  try {
    parsed = JSON.parse(eventData);
  } catch (e) {
    throw new StreamError('Failed to parse event source message', true, {
      eventData,
    });
  }

  if (typeof parsed !== 'object' || !parsed) {
    throw new StreamError('Invalid event source message', true, { eventData });
  }

  if ('error' in parsed) {
    const msg = extractErrorMessage(parsed);
    if ('task_run_id' in parsed && !!parsed.task_run_id) {
      throw new StreamError(msg ?? 'An unknown error occurred', msg === undefined, {
        eventData,
        runId: parsed.task_run_id,
      });
    } else {
      throw new StreamError(msg ?? 'An unknown error occurred', msg === undefined, { eventData });
    }
  }

  return parsed;
}

export async function SSEClient<R, T>(
  path: string,
  method: Method,
  body: R,
  onMessage?: (ev: T) => void,
  signal?: AbortSignal
): Promise<T> {
  let lastMessage: T | undefined;
  const headers = await requestHeaders('application/json');

  if (signal?.aborted) {
    return undefined as T;
  }

  await fetchEventSource(path, {
    onopen: onOpenStream,
    onmessage: (event: EventSourceMessage) => {
      lastMessage = parseSSEEvent(event.data) as T;
      onMessage?.(lastMessage);
    },
    onerror: (e: unknown) => {
      if (e instanceof StreamError) {
        if (e.capture) {
          captureException(e, { extra: { ...e.extra, path } });
        }
      } else {
        captureException(e);
      }
      throw e;
    },
    method,
    headers,
    body: method !== Method.GET ? JSON.stringify({ ...body, stream: true }) : undefined,
    openWhenHidden: true,
    // We should not keepalive because we noticed that running audio tasks
    // with keepalive enabled causes unexpected "Failed to fetch" errors.
    keepalive: false,
    signal,
  });

  if (!lastMessage) {
    const err = new Error('No message received');
    captureException(err, { extra: { path } });
    throw err;
  }
  return lastMessage!;
}
