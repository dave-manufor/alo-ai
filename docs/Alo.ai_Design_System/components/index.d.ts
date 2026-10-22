import type * as React from 'react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** primary = night (the main action); reward = moon (only after a reward); call = coral; done = leaf; secondary; ghost */
  variant?: 'primary' | 'reward' | 'call' | 'done' | 'secondary' | 'ghost';
  /** kid = tap-kid tall with a press edge; grown = tap-grown tall, flat */
  size?: 'kid' | 'grown';
  icon?: 'mic' | 'replay' | 'star' | 'lantern' | 'book' | 'check' | 'ear';
  children?: React.ReactNode;
}
export declare function Button(props: ButtonProps): React.ReactElement;

export interface MicButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  state?: 'idle' | 'listening' | 'thinking';
  /** Spoken-word label under the button; defaults per state */
  label?: string;
}
export declare function MicButton(props: MicButtonProps): React.ReactElement;

export interface SpeechBubbleProps {
  /** say = an ordinary line; call = the "Àlọ́ o!" call, large, in coral */
  tone?: 'say' | 'call';
  speaker?: string;
  children?: React.ReactNode;
}
export declare function SpeechBubble(props: SpeechBubbleProps): React.ReactElement;

export interface ReadingPanelProps {
  title?: string;
  /** One string or a list of sentences */
  text: string | string[];
  /** p1 = ARL 1-2, p3 = ARL 3-6, p5 = ARL 7-12 */
  level?: 'p1' | 'p3' | 'p5';
  lang?: string;
}
export declare function ReadingPanel(props: ReadingPanelProps): React.ReactElement;

export interface MoonProgressProps { steps?: string[]; /** index of the current step */ current?: number }
export declare function MoonProgress(props: MoonProgressProps): React.ReactElement;

export interface RewardBadgeProps { kind?: 'brave' | 'teller' | 'collector' | 'listener'; earned?: boolean }
export declare function RewardBadge(props: RewardBadgeProps): React.ReactElement;

export interface LanternStreakProps { /** one entry per week, oldest first; true = at least one session */ weeks?: boolean[] }
export declare function LanternStreak(props: LanternStreakProps): React.ReactElement;

export interface JapaProps { pose?: 'happy' | 'listening' | 'thinking' | 'cheer'; /** CSS width; default mascot-m */ size?: string }
export declare function Japa(props: JapaProps): React.ReactElement;

export interface ParentReportCardProps {
  title?: string; date?: string; summary?: string;
  stats?: { label: string; value: React.ReactNode }[];
  workingOn?: string; tip?: string; action?: string; onAction?: () => void;
}
export declare function ParentReportCard(props: ParentReportCardProps): React.ReactElement;

export interface ProfilePillProps {
  profile: 'ON_TRACK' | 'UNDERSTANDS_BUILDING_WORD_READING' | 'DECODING_LIMITED' | 'FLUENT_NEEDS_LANGUAGE_SUPPORT'
    | 'NEEDS_SUPPORT_IN_BOTH' | 'COMPREHENSION_STRATEGY_GAP' | 'INSUFFICIENT_EVIDENCE';
  label?: string; provisional?: boolean;
}
export declare function ProfilePill(props: ProfilePillProps): React.ReactElement;

export interface RoundButtonProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'children'> { kind?: 'next' | 'play'; /** read by screen readers; required */ label: string }
export declare function RoundButton(props: RoundButtonProps): React.ReactElement;

export interface PaperProps extends React.HTMLAttributes<HTMLElement> { as?: keyof JSX.IntrinsicElements }
export declare function Paper(props: PaperProps): React.ReactElement;

export interface EyebrowProps extends React.HTMLAttributes<HTMLElement> { as?: keyof JSX.IntrinsicElements }
export declare function Eyebrow(props: EyebrowProps): React.ReactElement;

export interface FieldProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'id'> {
  id: string; label: string; hint?: string; /** renders a select when given */ options?: { value: string; label: string }[];
}
export declare function Field(props: FieldProps): React.ReactElement;

export interface ToggleGroupProps { id: string; label: string; options: { value: string; label: string }[]; value?: string; onChange?: (value: string) => void; className?: string }
export declare function ToggleGroup(props: ToggleGroupProps): React.ReactElement;

export interface BannerProps { tone?: 'good' | 'info' | 'notice'; className?: string; children?: React.ReactNode }
export declare function Banner(props: BannerProps): React.ReactElement;

declare global {
  interface Window {
    Alo: { Button: typeof Button; MicButton: typeof MicButton; SpeechBubble: typeof SpeechBubble; ReadingPanel: typeof ReadingPanel;
      MoonProgress: typeof MoonProgress; RewardBadge: typeof RewardBadge; LanternStreak: typeof LanternStreak; Japa: typeof Japa;
      ParentReportCard: typeof ParentReportCard; ProfilePill: typeof ProfilePill;
      RoundButton: typeof RoundButton; Paper: typeof Paper; Eyebrow: typeof Eyebrow; Field: typeof Field; ToggleGroup: typeof ToggleGroup; Banner: typeof Banner };
  }
}
