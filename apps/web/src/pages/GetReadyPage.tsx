import { useEffect, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { useAccount } from '../account/store';
import { Button } from '../design-system/alo';
import Icon from '../ui/Icon';
import { BackLink, Notice, SectionLabel } from '../ui/primitives';

// Get ready (wireframe 5): three plain tips, who is reading, and a connection check, then the
// phone goes to the child. The session itself (a separate, full-screen route) starts when
// the child taps Start.
export default function GetReadyPage() {
  const { childId } = useParams();
  const navigate = useNavigate();
  const { children } = useAccount();
  const [selected, setSelected] = useState(childId);
  const online = useOnline();

  const child = children.find((item) => item.child_id === selected);
  if (!child) return <Navigate to="/home" replace />;

  return (
    <div className="page">
      <BackLink to="/home" />
      <div className="page-stack">
        <div className="step">
          <h1 className="display-m">Get ready</h1>
          <p className="body muted">
            The check takes about four minutes. {child.first_name} talks with Kemi; you do not need to help.
          </p>
        </div>

        {children.length > 1 ? (
          <div className="step">
            <SectionLabel id="who">Who&apos;s reading?</SectionLabel>
            <div className="ui-chips" role="group" aria-labelledby="who">
              {children.map((item) => (
                <button
                  key={item.child_id}
                  type="button"
                  className="ui-chip"
                  aria-pressed={item.child_id === child.child_id}
                  onClick={() => setSelected(item.child_id)}
                >
                  {item.first_name}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        <ul className="ui-check-list body">
          <li>
            <Icon name="check" />
            Find a quiet spot.
          </li>
          <li>
            <Icon name="check" />
            Hold the phone about a hand&apos;s length from {child.first_name}.
          </li>
          <li>
            <Icon name="check" />
            Let {child.first_name} answer alone, even if they are stuck.
          </li>
        </ul>

        {online ? (
          <Notice tone="leaf" role="status">
            <Icon name="check" />
            Your connection is good enough for a check.
          </Notice>
        ) : (
          <Notice tone="sky" role="status">
            You are offline. Connect to the internet to start the check.
          </Notice>
        )}

        <div className="form__footer">
          <Button
            variant="primary"
            size="grown"
            disabled={!online}
            onClick={() => navigate(`/session/${child.child_id}`)}
            style={{ width: '100%' }}
          >
            Hand the phone to {child.first_name}
          </Button>
          <p className="caption muted ui-center">The screen goes full screen when {child.first_name} taps Start.</p>
        </div>
      </div>
    </div>
  );
}

function useOnline(): boolean {
  const [online, setOnline] = useState(() => (typeof navigator === 'undefined' ? true : navigator.onLine));
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener('online', update);
    window.addEventListener('offline', update);
    return () => {
      window.removeEventListener('online', update);
      window.removeEventListener('offline', update);
    };
  }, []);
  return online;
}
