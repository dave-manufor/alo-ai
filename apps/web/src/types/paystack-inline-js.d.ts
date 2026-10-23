// @paystack/inline-js ships no types. Only what src/plan/paystackPopup.ts uses (the package's
// README: PaystackPop.resumeTransaction(accessCode, callbacks)).
declare module '@paystack/inline-js' {
  export interface ResumeCallbacks {
    onSuccess?: (transaction: { id: number; reference: string; message: string }) => void;
    onCancel?: () => void;
    onLoad?: (transaction: { id: number; accessCode: string }) => void;
    onError?: (error: { message: string }) => void;
  }
  export default class PaystackPop {
    resumeTransaction(accessCode: string, callbacks?: ResumeCallbacks): unknown;
  }
}
