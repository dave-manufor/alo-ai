import { useMemo, useState, type ReactNode } from 'react';
import { useAccount } from '../account/store';
import { ActiveChildContext, type ActiveChild } from './activeChildContext';

export function ActiveChildProvider({ children: content }: { children: ReactNode }) {
  const { children } = useAccount();
  const [chosen, setChosen] = useState<string | null>(null);
  const value = useMemo<ActiveChild>(() => {
    const child = children.find((item) => item.child_id === chosen) ?? children[0];
    return { child, children, setChildId: setChosen };
  }, [children, chosen]);
  return <ActiveChildContext.Provider value={value}>{content}</ActiveChildContext.Provider>;
}
