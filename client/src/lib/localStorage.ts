const STORAGE_QUOTA_EXCEEDED_ERRORS = [
  'QuotaExceededError',
  'NS_ERROR_DOM_QUOTA_REACHED',
  'QUOTA_EXCEEDED_ERR',
];

function isQuotaExceededError(error: Error): boolean {
  return STORAGE_QUOTA_EXCEEDED_ERRORS.some(
    (errorName) => error.name === errorName || error.message?.includes(errorName)
  );
}

function clearLocalStorage(): void {
  try {
    localStorage.clear();
    console.warn('localStorage cleared due to quota exceeded');
  } catch (error) {
    console.error('Failed to clear localStorage:', error);
  }
}

export function safeLocalStorageSetItem(key: string, value: string): boolean {
  try {
    localStorage.setItem(key, value);
    return true;
  } catch (error) {
    if (error instanceof Error && isQuotaExceededError(error)) {
      console.warn('localStorage quota exceeded, clearing storage and retrying');
      clearLocalStorage();
      
      try {
        localStorage.setItem(key, value);
        return true;
      } catch (retryError) {
        console.error('Failed to set localStorage item after clearing:', retryError);
        return false;
      }
    }
    
    console.error('Failed to set localStorage item:', error);
    return false;
  }
}

export function safeLocalStorageGetItem(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch (error) {
    console.error('Failed to get localStorage item:', error);
    return null;
  }
}

export function safeLocalStorageRemoveItem(key: string): boolean {
  try {
    localStorage.removeItem(key);
    return true;
  } catch (error) {
    console.error('Failed to remove localStorage item:', error);
    return false;
  }
}