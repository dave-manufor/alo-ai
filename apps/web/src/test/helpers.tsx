import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { accountStore } from '../account/store';
import App from '../App';
import { sampleReportFor } from '../report/childReports';

/** Signs in a sample guardian and adds one child with consent. */
export function signInWithChild(firstName = 'Adaeze') {
  accountStore.resetForTests();
  accountStore.signIn('email_code', 'parent@example.com');
  const { child } = accountStore.addChildWithConsent({
    firstName,
    primaryClass: 3,
    birthYear: 2018,
    attested: true,
    trainingOptIn: false,
  });
  return { child, report: sampleReportFor(child) };
}

/** The whole app, starting at a path. */
export function renderApp(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}
