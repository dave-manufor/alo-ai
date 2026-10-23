// Paystack's inline popup (PRD 11.1), for a transaction the Account service has already started:
// the browser gets only the access code, so it can change neither the amount nor the plan. The
// package is loaded only when a guardian pays, so it is not in the app's first download.

export type PopupOutcome = 'success' | 'cancelled';
export type OpenPopup = (accessCode: string) => Promise<PopupOutcome>;

export const openPaystackPopup: OpenPopup = async (accessCode) => {
  const { default: PaystackPop } = await import('@paystack/inline-js');
  return new Promise<PopupOutcome>((resolve, reject) => {
    new PaystackPop().resumeTransaction(accessCode, {
      onSuccess: () => resolve('success'),
      onCancel: () => resolve('cancelled'),
      onError: () => reject(new Error('The Paystack checkout could not open.')),
    });
  });
};
