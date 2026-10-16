# ops: things configured outside Terraform (W1, reviewed by W2 or W3)

`paystack/` (script + config for plans and webhook URL, test mode) and `README.md` (everything configured by hand: LiveKit and email provider accounts, Firebase Auth providers, secret values).

- Keep `ops/README.md` the complete record of out-of-Terraform setup. Record any new manual step here in the same PR.
- Never commit secret values, API keys or webhook secrets. Paystack stays in **test mode**.
