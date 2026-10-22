import { ApiError, type ApiClient } from '../api/client';
import type { ChildProfile, ConsentRecord } from './store';

// Children and consent through the Account API (D2; services/account:
// GET/POST /v1/children, GET /v1/children/{id}/consent). The server
// writes the attestation text itself, so the browser only sends the
// tick. Takes the client as a parameter so tests need no network.

interface ServerChild {
  child_id: string;
  first_name: string;
  primary_class: number;
  birth_year: number;
  class_confirmed_year: number;
}

function toProfile(child: ServerChild): ChildProfile {
  return {
    child_id: child.child_id,
    first_name: child.first_name,
    primary_class: child.primary_class,
    birth_year: child.birth_year,
    class_confirmed_year: child.class_confirmed_year,
  };
}

export async function loadAccount(
  api: ApiClient,
): Promise<{ children: ChildProfile[]; consents: ConsentRecord[] }> {
  const { children } = await api.get<{ children: ServerChild[] }>('/v1/children');
  const consents = await Promise.all(
    children.map(async (child) => {
      try {
        return await api.get<ConsentRecord>(`/v1/children/${encodeURIComponent(child.child_id)}/consent`);
      } catch (error) {
        // A child with no consent on file simply has none (the mic gate stays closed).
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }
    }),
  );
  return {
    children: children.map(toProfile),
    consents: consents.filter((consent): consent is ConsentRecord => consent !== null),
  };
}

export async function createChild(
  api: ApiClient,
  input: {
    firstName: string;
    primaryClass: number;
    birthYear: number;
    attested: boolean;
    trainingOptIn: boolean;
  },
): Promise<{ child: ChildProfile; consent: ConsentRecord }> {
  const saved = await api.post<{ child_id: string; child: ServerChild; consent: ConsentRecord }>(
    '/v1/children',
    {
      first_name: input.firstName.trim(),
      primary_class: input.primaryClass,
      birth_year: input.birthYear,
      attested: input.attested,
      training_opt_in: input.trainingOptIn,
    },
  );
  return {
    child: toProfile({ ...saved.child, child_id: saved.child_id }),
    consent: saved.consent,
  };
}
