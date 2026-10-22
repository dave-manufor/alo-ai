// Small line icons for the grown-up navigation. The design system ships six icons
// (book, check, lantern, mic, replay, star) and none for Home, Reports, Plan or Account,
// so these few match the wireframes' own inline icons: 24px box, 2.5 stroke, round caps,
// `currentColor`. Recorded as a design-system deviation in the PR; the system should adopt them.

export type IconName =
  | 'home'
  | 'reports'
  | 'plan'
  | 'account'
  | 'back'
  | 'check'
  | 'book'
  | 'child'
  | 'school';

const paths: Record<IconName, string[]> = {
  home: ['M4 11l8-7 8 7', 'M6 10v10h12V10', 'M10 20v-6h4v6'],
  reports: ['M7 3h8l4 4v14H7z', 'M14 3v5h5', 'M10 13h6', 'M10 17h6'],
  plan: ['M5 5h14v15H5z', 'M5 9h14', 'M9 3v4', 'M15 3v4', 'M9 14l2 2 4-4'],
  account: ['M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z', 'M4 21c0-4 3.6-7 8-7s8 3 8 7'],
  back: ['M15 5l-7 7 7 7'],
  check: ['M5 12l5 5 9-10'],
  book: ['M4 5a2 2 0 0 1 2-2h12v16H6a2 2 0 0 0-2 2z', 'M4 21V5'],
  child: ['M12 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z', 'M5 20c0-3.5 3-6 7-6s7 2.5 7 6'],
  school: ['M3 9l9-5 9 5-9 5z', 'M7 11.5V16c0 1.5 2.2 3 5 3s5-1.5 5-3v-4.5', 'M21 9v6'],
};

export default function Icon({ name, size = 24 }: { name: IconName; size?: number }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="icon"
    >
      {paths[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
