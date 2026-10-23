import { useNavigate } from 'react-router-dom';
import { accountStore, useAccount } from '../account/store';
import { dataMode } from '../api';
import { Button } from '../design-system/alo';
import NavButton from '../design-system/NavButton';
import { PLAN_PRICE, PLAN_PRICE_PERIOD } from '../plan/price';
import { useActiveChild } from '../shell/activeChildContext';
import Icon from '../ui/Icon';
import { BackLink } from '../ui/primitives';

// Upgrade (wireframe 21). Payment happens on Paystack's own page, opened from a transaction
// the Account service starts; the amount is never set here. In the sample build a clearly
// labelled button stands in for a paid plan so the rest of the app can be seen.
export default function UpgradePage() {
  const navigate = useNavigate();
  const { guardian } = useAccount();
  const { child } = useActiveChild();
  const name = child?.first_name ?? 'your child';
  const already = guardian !== null && accountStore.hasActiveSubscription();

  return (
    <div className="page page--mid">
      <BackLink to="/plan" />
      <h1 className="display-m">Get {name}&apos;s weekly plan</h1>

      <div className="ui-card price-card">
        <div className="price">
          <span className="price__amount">{PLAN_PRICE}</span>
          <span className="body muted card-title">{PLAN_PRICE_PERIOD}</span>
        </div>
        <ul className="ui-check-list ui-check-list--leaf body">
          <li>
            <Icon name="check" />A plan for home after every check
          </li>
          <li>
            <Icon name="check" />
            Books matched to {name}&apos;s level and interests
          </li>
          <li>
            <Icon name="check" />A new story at each check
          </li>
        </ul>
      </div>

      <div className="form__footer">
        {already ? (
          <NavButton variant="primary" size="grown" to="/plan" style={{ width: '100%' }}>
            You have the plan. Open it
          </NavButton>
        ) : (
          <NavButton variant="primary" size="grown" to="/plan/checkout" style={{ width: '100%' }}>
            Continue to payment
          </NavButton>
        )}
        <p className="caption muted ui-center">
          You will pay by card on Paystack&apos;s secure page. Paystack never receives anything about {name}.
        </p>
        <p className="caption muted ui-center">Prices are drafts.</p>
        {dataMode !== 'live' && !already ? (
          <Button
            variant="ghost"
            size="grown"
            onClick={() => {
              accountStore.activateSampleSubscription();
              navigate('/plan');
            }}
          >
            Sample build: switch the plan on
          </Button>
        ) : null}
      </div>
    </div>
  );
}
