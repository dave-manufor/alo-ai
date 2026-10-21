import { useNavigate } from 'react-router-dom';
import { Button, type ButtonProps } from './alo';

// Navigation that looks like a design-system Button without nesting a
// <button> inside an <a> (invalid HTML, two tab stops, and aria-label
// mismatches against the visible text — WCAG 2.5.3). The visible label
// stays the accessible name.
export interface NavButtonProps extends Omit<ButtonProps, 'onClick'> {
  to: string;
}

export default function NavButton({ to, children, ...props }: NavButtonProps) {
  const navigate = useNavigate();
  return (
    <Button {...props} onClick={() => navigate(to)}>
      {children}
    </Button>
  );
}
