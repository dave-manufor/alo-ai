import { ProfilePill } from '../design-system/alo';
import {
  practicePlanByProfile,
  type PreviewChild,
  type ProfileId,
} from './teacherFixture';

/** Groups panel (PRD 4.7): children grouped by profile, with the
 *  section 8 practice plan for each group. */
export default function GroupsPanel({ children }: { children: PreviewChild[] }) {
  const groups = new Map<ProfileId, PreviewChild[]>();
  for (const child of children) {
    const list = groups.get(child.profile) ?? [];
    list.push(child);
    groups.set(child.profile, list);
  }

  return (
    <section className="stack" aria-labelledby="groups-heading">
      <h2 id="groups-heading" className="title">
        Groups for practice
      </h2>
      {[...groups.entries()].map(([profile, members]) => (
        <article key={profile} className="card">
          <ProfilePill profile={profile} />
          <p className="body">{practicePlanByProfile[profile]}</p>
          <p className="body muted">
            {members.map((member) => member.name).join(', ')}
          </p>
        </article>
      ))}
    </section>
  );
}
