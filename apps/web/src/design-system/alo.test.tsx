import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Button, Japa, MicButton, ProfilePill, SpeechBubble } from './alo';

// The design-system bundle must load through the one consumption layer
// (alo.tsx) and render with the bundle's own props.
describe('design system consumption layer', () => {
  it('renders the Alo Button with kid sizing by default', () => {
    render(<Button icon="mic">Start reading</Button>);
    const button = screen.getByRole('button', { name: /start reading/i });
    expect(button.className).toContain('alo-btn--kid');
  });

  it('renders Auntie Kemi speech and Japa poses', () => {
    render(
      <>
        <SpeechBubble>Take your time.</SpeechBubble>
        <Japa pose="listening" />
      </>,
    );
    expect(screen.getByText('Take your time.')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /jàpá/i })).toBeInTheDocument();
  });

  it('renders a grown-up mic button and plain-language profile pill', () => {
    render(
      <>
        <MicButton state="listening" />
        <ProfilePill profile="ON_TRACK" />
      </>,
    );
    expect(screen.getByRole('button')).toBeInTheDocument();
    expect(screen.getByText('On track')).toBeInTheDocument();
  });
});
