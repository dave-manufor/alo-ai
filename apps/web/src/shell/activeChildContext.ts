import { createContext, useContext } from 'react';
import type { ChildProfile } from '../account/store';

// Which of the guardian's children the Home, Plan and report screens are about. It lives in
// memory for the visit: a child's name never goes into browser storage on a shared phone.
export interface ActiveChild {
  child: ChildProfile | undefined;
  children: ChildProfile[];
  setChildId: (childId: string) => void;
}

export const ActiveChildContext = createContext<ActiveChild>({
  child: undefined,
  children: [],
  setChildId: () => undefined,
});

export function useActiveChild(): ActiveChild {
  return useContext(ActiveChildContext);
}
