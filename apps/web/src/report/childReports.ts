// Sample reports for the guardian's own children (fixture phase).
//
// Until the Account service serves reports (reports/{session_id}), each child a guardian adds
// gets one sample check built from the first sample report, so Home, Reports and the plan all
// show that child's own name. Copy uses the child's name and "they", never a guessed pronoun.
// Every number is the sample report's; the UI still only displays.

import { sampleReports, type ReadingReport } from './reportFixture';

const SAMPLE_CHECK_ISO = '2026-10-14T09:09:05Z';
const DAYS_BETWEEN_CHECKS = 14;

interface ChildLike {
  child_id: string;
  first_name: string;
  primary_class: number;
}

export function sampleReportFor(child: ChildLike): ReadingReport {
  const name = child.first_name;
  return {
    ...sampleReports[0],
    session_id: `sess_${child.child_id}_1`,
    child_id: child.child_id,
    timestamp_iso: SAMPLE_CHECK_ISO,
    primary_class: child.primary_class,
    parent_reporting: {
      summary_script: `Hello! Kemi here. ${name} read 68 words correctly in a minute today and got most words right. Reading the words is coming along. The main events of the story were there, but explaining why things happened was tricky. This was a short check, so think of it as a first look.`,
      home_practice: `Try a sound hunt: pick a sound from a word ${name} found hard, and find three things at home that start with it.`,
    },
  };
}

/** The sample reports for these children, newest first. */
export function reportsFor(children: ChildLike[]): ReadingReport[] {
  return children
    .map(sampleReportFor)
    .sort((a, b) => b.timestamp_iso.localeCompare(a.timestamp_iso));
}

/** When the next check is due: two weeks after the last one. */
export function nextCheckIso(report: ReadingReport): string {
  const next = new Date(report.timestamp_iso);
  next.setUTCDate(next.getUTCDate() + DAYS_BETWEEN_CHECKS);
  return next.toISOString();
}

/** "14 October", for the Home and plan screens. */
export function formatLongDay(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', timeZone: 'UTC' });
}
