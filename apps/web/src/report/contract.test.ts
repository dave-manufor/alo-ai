import { describe, expect, it } from 'vitest';
import realPlan from '../../../../fixtures/contracts/guardian_plan.sess_demo_001.json';
import realReport from '../../../../fixtures/contracts/reading_report.sess_demo_001.json';
import { samplePlanFor } from './plan';
import { sampleReports } from './reportFixture';

// The web app's sample report and plan are views of the real contracts (schemas/
// reading_report.schema.json, guardian_plan.schema.json). These tests read the shared
// fixtures the Grader and the Account API are checked against, so a field the screens read
// that the real document does not have, or a version that has moved on, fails here.

/** Paths in `mine` that the real document does not have, or holds as another kind of value.
 *  A null on either side is compatible with anything (a missing result is null). */
function drift(mine: unknown, real: unknown, path = ''): string[] {
  if (mine === null || real === null) return [];
  if (Array.isArray(mine)) {
    if (!Array.isArray(real)) return [`${path}: not a list in the real document`];
    return mine.length > 0 && real.length > 0 ? drift(mine[0], real[0], `${path}[0]`) : [];
  }
  if (typeof mine === 'object') {
    if (typeof real !== 'object' || Array.isArray(real)) return [`${path}: not an object in the real document`];
    return Object.entries(mine as Record<string, unknown>).flatMap(([key, value]) =>
      key in (real as object)
        ? drift(value, (real as Record<string, unknown>)[key], path ? `${path}.${key}` : key)
        : [`${path ? `${path}.` : ''}${key}: not in the real document`],
    );
  }
  return typeof mine === typeof real ? [] : [`${path}: ${typeof mine} here, ${typeof real} there`];
}

describe('the sample report is a view of the real ReadingReport', () => {
  it('has the real schema_version', () => {
    for (const report of sampleReports) expect(report.schema_version).toBe(realReport.schema_version);
  });

  it('reads only fields the real report has, of the same kind', () => {
    for (const report of sampleReports) expect(drift(report, realReport)).toEqual([]);
  });

  it('would notice a field that is not in the real report', () => {
    expect(drift({ ...sampleReports[0], invented: 1 }, realReport)).toEqual(['invented: not in the real document']);
    expect(drift({ ...sampleReports[0], schema_version: 'two' }, realReport)).toEqual([
      'schema_version: string here, number there',
    ]);
  });
});

describe('the sample plan is a view of the real GuardianPlan', () => {
  it('has the real schema_version and shape', () => {
    const plan = samplePlanFor(sampleReports[0]);
    expect(plan.schema_version).toBe(realPlan.schema_version);
    expect(drift(plan, realPlan)).toEqual([]);
    expect(plan.books.length).toBeGreaterThan(0);
  });

  it('carries each book with its licence and attribution', () => {
    for (const book of samplePlanFor(sampleReports[0]).books) {
      expect(book.licence).not.toBe('');
      expect(book.attribution).not.toBe('');
    }
  });
});
