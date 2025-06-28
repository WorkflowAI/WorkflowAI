import { createContext, useContext, useMemo } from 'react';
import { checkSchemaForProxy } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/utils';
import { TaskSchemaResponseWithSchema } from '@/types/task';

const IsProxyContext = createContext<boolean>(false);

export function IsProxyContextProvider({
  children,
  schema,
}: {
  children: React.ReactNode;
  schema: TaskSchemaResponseWithSchema | undefined;
}) {
  const isProxy = useMemo(() => {
    if (!schema) {
      return false;
    }
    return checkSchemaForProxy(schema);
  }, [schema]);

  return <IsProxyContext.Provider value={isProxy}>{children}</IsProxyContext.Provider>;
}

export function useIsProxy() {
  return useContext(IsProxyContext);
}
