import { captureException } from '@sentry/nextjs';

export class BaseError extends Error {
  capture: boolean;
  extra: Record<string, unknown> | undefined;

  constructor(message: string, capture: boolean = false, extra: Record<string, unknown> | undefined = undefined) {
    super(message);

    this.capture = capture;
    this.extra = extra;
    if (extra?.title && typeof extra.title === 'string') {
      this.name = extra.title;
    }
  }

  getStatusCode(): number | undefined {
    const status = this.extra?.status;
    if (typeof status !== 'number') {
      return undefined;
    }
    return status;
  }
}

export class StreamError extends BaseError {}

export function captureIfNeeded(error: unknown) {
  if (!(error instanceof BaseError)) {
    captureException(error);
    return;
  }

  if (error.capture) {
    captureException(error);
  }
}

export function isPaymentError(error: unknown): boolean {
  if (!(error instanceof StreamError)) {
    return false;
  }
  return error.getStatusCode() === 402;
}
