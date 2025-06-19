import { captureException } from '@sentry/nextjs';

// Enhanced error handling for Zustand stores
export interface StoreErrorState {
  error?: Error;
  isError: boolean;
  lastErrorTime?: number;
  errorMessage?: string;
}

export interface StoreOperationContext {
  operation: string;
  storeType: string;
  key?: string;
  metadata?: Record<string, unknown>;
}

export class StoreError extends Error {
  constructor(
    message: string,
    public operation: string,
    public storeType: string,
    public context?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'StoreError';
  }
}

export class StoreErrorHandler {
  /**
   * Safe state update wrapper for Zustand stores
   */
  static safeStateUpdate<T>(
    setState: (updater: (state: T) => void) => void,
    updater: (state: T) => void,
    context: StoreOperationContext
  ): void {
    try {
      setState((state) => {
        try {
          updater(state);
        } catch (error) {
          StoreErrorHandler.handleStoreError(error as Error, context);
          // Don't throw - just log and continue with original state
        }
      });
    } catch (error) {
      StoreErrorHandler.handleStoreError(error as Error, context);
    }
  }

  /**
   * Safe async operation wrapper for stores
   */
  static async safeAsyncOperation<T>(
    operation: () => Promise<T>,
    context: StoreOperationContext,
    fallbackValue?: T
  ): Promise<T | undefined> {
    try {
      return await operation();
    } catch (error) {
      StoreErrorHandler.handleStoreError(error as Error, context);
      return fallbackValue;
    }
  }

  /**
   * Safe Map operations to prevent memory leaks
   */
  static safeMapSet<K, V>(
    map: Map<K, V>,
    key: K,
    value: V,
    context: StoreOperationContext
  ): boolean {
    try {
      map.set(key, value);
      return true;
    } catch (error) {
      StoreErrorHandler.handleStoreError(error as Error, {
        ...context,
        operation: `${context.operation}_map_set`,
        key: String(key),
      });
      return false;
    }
  }

  static safeMapGet<K, V>(
    map: Map<K, V>,
    key: K,
    context: StoreOperationContext
  ): V | undefined {
    try {
      return map.get(key);
    } catch (error) {
      StoreErrorHandler.handleStoreError(error as Error, {
        ...context,
        operation: `${context.operation}_map_get`,
        key: String(key),
      });
      return undefined;
    }
  }

  static safeMapDelete<K, V>(
    map: Map<K, V>,
    key: K,
    context: StoreOperationContext
  ): boolean {
    try {
      return map.delete(key);
    } catch (error) {
      StoreErrorHandler.handleStoreError(error as Error, {
        ...context,
        operation: `${context.operation}_map_delete`,
        key: String(key),
      });
      return false;
    }
  }

  /**
   * Safe cleanup for Map-based stores
   */
  static safeMapCleanup<K, V>(
    map: Map<K, V>,
    shouldKeep: (key: K, value: V) => boolean,
    context: StoreOperationContext
  ): number {
    let cleanedCount = 0;
    try {
      const toDelete: K[] = [];
      
      map.forEach((value, key) => {
        try {
          if (!shouldKeep(key, value)) {
            toDelete.push(key);
          }
        } catch (error) {
          // If shouldKeep throws, assume we should delete for safety
          toDelete.push(key);
        }
      });

      toDelete.forEach(key => {
        if (map.delete(key)) {
          cleanedCount++;
        }
      });
    } catch (error) {
      StoreErrorHandler.handleStoreError(error as Error, {
        ...context,
        operation: `${context.operation}_map_cleanup`,
      });
    }
    return cleanedCount;
  }

  /**
   * Handle store errors with enhanced context
   */
  private static handleStoreError(error: Error, context: StoreOperationContext): void {
    const storeError = new StoreError(
      `Store operation failed: ${error.message}`,
      context.operation,
      context.storeType,
      {
        originalError: error.message,
        errorType: error.constructor.name,
        ...context.metadata,
      }
    );

    captureException(storeError, {
      tags: {
        errorType: 'store_error',
        storeType: context.storeType,
        operation: context.operation,
      },
      extra: {
        storeKey: context.key,
        metadata: context.metadata,
        originalError: {
          name: error.name,
          message: error.message,
          stack: error.stack,
        },
      },
    });

    console.error('Store error:', {
      operation: context.operation,
      storeType: context.storeType,
      error: error.message,
      context: context.metadata,
    });
  }

  /**
   * Create error state management helpers
   */
  static createErrorStateHelpers<T extends StoreErrorState>() {
    return {
      setError: (setState: (updater: (state: T) => void) => void, error: Error) => {
        setState((state) => {
          state.error = error;
          state.isError = true;
          state.lastErrorTime = Date.now();
          state.errorMessage = error.message;
        });
      },

      clearError: (setState: (updater: (state: T) => void) => void) => {
        setState((state) => {
          state.error = undefined;
          state.isError = false;
          state.lastErrorTime = undefined;
          state.errorMessage = undefined;
        });
      },

      hasRecentError: (state: T, maxAgeMs: number = 30000): boolean => {
        return !!(
          state.isError &&
          state.lastErrorTime &&
          Date.now() - state.lastErrorTime < maxAgeMs
        );
      },
    };
  }
}

/**
 * Memory leak prevention utilities
 */
export class StoreMemoryManager {
  private static readonly DEFAULT_MAX_MAP_SIZE = 1000;
  private static readonly DEFAULT_CLEANUP_INTERVAL = 5 * 60 * 1000; // 5 minutes

  /**
   * Monitor Map size and clean up when needed
   */
  static createMapSizeMonitor<K, V>(
    map: Map<K, V>,
    storeType: string,
    maxSize: number = StoreMemoryManager.DEFAULT_MAX_MAP_SIZE
  ) {
    return {
      checkAndCleanup: (cleanupFn?: (key: K, value: V) => boolean) => {
        if (map.size <= maxSize) return 0;

        const context: StoreOperationContext = {
          operation: 'size_limit_cleanup',
          storeType,
          metadata: { currentSize: map.size, maxSize },
        };

        if (cleanupFn) {
          return StoreErrorHandler.safeMapCleanup(map, cleanupFn, context);
        }

        // Default cleanup: remove oldest entries (assuming insertion order)
        let cleanedCount = 0;
        const targetSize = Math.floor(maxSize * 0.8); // Clean to 80% of max size
        const toDelete = Array.from(map.keys()).slice(0, map.size - targetSize);

        toDelete.forEach(key => {
          if (StoreErrorHandler.safeMapDelete(map, key, context)) {
            cleanedCount++;
          }
        });

        return cleanedCount;
      },
    };
  }

  /**
   * Create automatic cleanup interval
   */
  static createAutoCleanup<K, V>(
    map: Map<K, V>,
    storeType: string,
    cleanupFn: (key: K, value: V) => boolean,
    intervalMs: number = StoreMemoryManager.DEFAULT_CLEANUP_INTERVAL
  ): () => void {
    const interval = setInterval(() => {
      const context: StoreOperationContext = {
        operation: 'auto_cleanup',
        storeType,
        metadata: { currentSize: map.size },
      };

      const cleanedCount = StoreErrorHandler.safeMapCleanup(map, cleanupFn, context);
      
      if (cleanedCount > 0) {
        console.debug(`Auto-cleaned ${cleanedCount} items from ${storeType} store`);
      }
    }, intervalMs);

    // Return cleanup function
    return () => clearInterval(interval);
  }

  /**
   * Time-based cleanup helper
   */
  static createTimeBasedCleanup(maxAgeMs: number) {
    return <T extends { timestamp?: number }>(key: unknown, value: T): boolean => {
      if (!value.timestamp) return false; // Keep items without timestamp
      return Date.now() - value.timestamp < maxAgeMs;
    };
  }

  /**
   * LRU-based cleanup helper
   */
  static createLRUCleanup(maxSize: number) {
    const accessTimes = new Map<unknown, number>();

    return <T>(key: unknown, value: T): boolean => {
      accessTimes.set(key, Date.now());
      
      // If we're under the limit, keep everything
      if (accessTimes.size <= maxSize) return true;

      // Remove oldest access times first
      const sortedByAccess = Array.from(accessTimes.entries())
        .sort(([, a], [, b]) => b - a); // Sort by access time descending

      const shouldKeep = sortedByAccess.slice(0, maxSize).map(([k]) => k);
      const keep = shouldKeep.includes(key);

      // Clean up access times for items we're not keeping
      if (!keep) {
        accessTimes.delete(key);
      }

      return keep;
    };
  }
}

/**
 * Store debugging utilities
 */
export class StoreDebugger {
  static logStoreState<T>(storeName: string, state: T, operation?: string): void {
    if (process.env.NODE_ENV !== 'development') return;

    console.group(`🏪 Store Debug: ${storeName}${operation ? ` (${operation})` : ''}`);
    console.log('State:', state);
    
    // Log Map sizes if present
    Object.entries(state as Record<string, unknown>).forEach(([key, value]) => {
      if (value instanceof Map) {
        console.log(`${key} size:`, value.size);
      }
    });
    
    console.groupEnd();
  }

  static createPerformanceMonitor(storeName: string) {
    const operationTimes = new Map<string, number[]>();

    return {
      start: (operation: string): (() => void) => {
        const startTime = performance.now();
        
        return () => {
          const duration = performance.now() - startTime;
          
          if (!operationTimes.has(operation)) {
            operationTimes.set(operation, []);
          }
          
          const times = operationTimes.get(operation)!;
          times.push(duration);
          
          // Keep only last 100 measurements
          if (times.length > 100) {
            times.shift();
          }
          
          // Log slow operations in development
          if (process.env.NODE_ENV === 'development' && duration > 100) {
            console.warn(
              `⚠️  Slow store operation: ${storeName}.${operation} took ${duration.toFixed(2)}ms`
            );
          }
        };
      },

      getStats: () => {
        const stats: Record<string, { avg: number; max: number; count: number }> = {};
        
        operationTimes.forEach((times, operation) => {
          const avg = times.reduce((sum, time) => sum + time, 0) / times.length;
          const max = Math.max(...times);
          
          stats[operation] = { avg, max, count: times.length };
        });
        
        return stats;
      },
    };
  }
}