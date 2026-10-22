import { Link, Navigate } from 'react-router-dom';
import { useAccount } from '../account/store';
import Icon from '../ui/Icon';

// The first screen: who are you here as? A parent signs in to the real app; a school goes
// straight to the teacher view preview (sample data, no sign-in). Someone already signed in
// is sent on to their Home.
export default function WelcomePage() {
  const { guardian, children } = useAccount();
  if (guardian) return <Navigate to={children.length === 0 ? '/onboarding/consent' : '/home'} replace />;

  return (
    <div className="page page--wide">
      <section className="welcome">
        <div className="welcome__hero">
          <h1 className="display-l">Stories that listen back</h1>
          <p className="body welcome__lede">
            A reading check your child does out loud, in about four minutes. Parents get a plain
            report and a plan for home.
          </p>
        </div>
        <div className="welcome__choices">
          <h2 className="label ui-section-label">I am a</h2>
          <Link to="/signin" className="role-card">
            <span className="role-card__icon">
              <Icon name="child" />
            </span>
            <span className="role-card__text">
              <span className="body role-card__title">Parent or guardian</span>
              <span className="caption muted">Check how your child reads and get a plan for home.</span>
            </span>
            <span className="role-card__chevron">
              <Icon name="back" size={20} />
            </span>
          </Link>
          <Link to="/schools" className="role-card">
            <span className="role-card__icon">
              <Icon name="school" />
            </span>
            <span className="role-card__text">
              <span className="body role-card__title">School or teacher</span>
              <span className="caption muted">See what a class view looks like. Sample data only.</span>
            </span>
            <span className="role-card__chevron">
              <Icon name="back" size={20} />
            </span>
          </Link>
        </div>
      </section>
    </div>
  );
}
