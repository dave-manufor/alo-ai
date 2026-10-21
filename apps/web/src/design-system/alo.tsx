// The one place the app imports the design-system components.
// Source of truth: docs/Alo.ai_Design_System/ — synced verbatim into
// ./vendor by scripts/sync-design-system.mjs. Never edit the vendor copies;
// never import them from anywhere else. See ./README.md.
import './react-global';
import './vendor/tokens.css';
import './vendor/bundle.css';
import './vendor/bundle.js';
import type {
  ButtonProps,
  JapaProps,
  LanternStreakProps,
  MicButtonProps,
  MoonProgressProps,
  ParentReportCardProps,
  ProfilePillProps,
  ReadingPanelProps,
  RewardBadgeProps,
  SpeechBubbleProps,
} from './vendor/index.d';
import type { ComponentType } from 'react';

const Alo = window.Alo;

export const Button = Alo.Button as ComponentType<ButtonProps>;
export const MicButton = Alo.MicButton as ComponentType<MicButtonProps>;
export const SpeechBubble = Alo.SpeechBubble as ComponentType<SpeechBubbleProps>;
export const ReadingPanel = Alo.ReadingPanel as ComponentType<ReadingPanelProps>;
export const MoonProgress = Alo.MoonProgress as ComponentType<MoonProgressProps>;
export const RewardBadge = Alo.RewardBadge as ComponentType<RewardBadgeProps>;
export const LanternStreak = Alo.LanternStreak as ComponentType<LanternStreakProps>;
export const Japa = Alo.Japa as ComponentType<JapaProps>;
export const ParentReportCard = Alo.ParentReportCard as ComponentType<ParentReportCardProps>;
export const ProfilePill = Alo.ProfilePill as ComponentType<ProfilePillProps>;

export type {
  ButtonProps,
  JapaProps,
  LanternStreakProps,
  MicButtonProps,
  MoonProgressProps,
  ParentReportCardProps,
  ProfilePillProps,
  ReadingPanelProps,
  RewardBadgeProps,
  SpeechBubbleProps,
};
