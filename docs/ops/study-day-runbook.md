# Study-day runbook (J2)

For the person running a session day. Read `docs/ops/go-live.md` first if the site has not been put live yet. Nothing here needs the portal; every command is `az` from a terminal that is logged in (`az login`) with Owner or the operator roles.

Never write a child's name, an audio file, a transcript or a report into a chat, an issue or a PR. Refer to a session by its id (`sess_...`) and a child by `child_...`.

## The day before

- [ ] The adult rehearsal (go-live step 6) passed on the study phone and venue network.
- [ ] Every family has signed the printed consent form and has the information sheet (`docs/consent/`). The contact person and the study team's access are filled in on the sheet (its `TODO(team)` lines).
- [ ] Settings are the study ones: `terraform -chdir=infra/azure plan` shows no changes; `agent_on = true`, `session_profile = "standard"`, `voice_mode = "cache_first"`, `second_transcript = "off"` (W3 has confirmed the single-transcript rule).
- [ ] The seed job succeeded after the last image or clip change.
- [ ] No deploy is planned during the day. A deploy ends a running session.

## Morning, before the first child

1. `az containerapp list -g aloai-rg -o table`: every app `Running`. The Session Agent is warm (min replicas 1 while `agent_on` is true).
2. `curl -s https://<account_url>/healthz` answers `ok`.
3. Both dead-letter queues are empty (see "Looking at it" below). If not, find out why before children arrive.
4. Run the smoke test (go-live step 5) once with the fictional child.

## While children read

- A grown-up stays with the child. The child can stop at any time; a stopped or dropped session simply has no report.
- One session at a time per phone. If a phone loses the connection the app rejoins by itself for about a minute (the same session). After that it says the check was saved early.
- Look at the dead-letter queues and the Session Agent log between children, not during a session.

## Looking at it (no alerts are set up yet: J1 is later work, so look by hand)

Dead-letter queues (should be 0). Each message that failed five times ends here:

```
az servicebus queue show -g aloai-rg --namespace-name <namespace> --name core-events --query countDetails.deadLetterMessageCount
az servicebus queue show -g aloai-rg --namespace-name <namespace> --name scorer-events --query countDetails.deadLetterMessageCount
```

(`<namespace>` is in `terraform output`.) Logs (Log Analytics; the workspace is in `aloai-rg`): in the portal's Logs for the workspace, or `az monitor log-analytics query --workspace <workspace id> --analytics-query "ContainerAppConsoleLogs_CL | where ContainerAppName_s == '<app>' | top 50 by TimeGenerated desc | project TimeGenerated, Log_s"`. Logs are meant to hold ids and error classes only, never names or words (rule I7; it has not been audited yet, so look for it); if you see a child's words in a log, stop and tell the team.

Where a session has got to, by id: the app's reports screen, or Cosmos Data Explorer, `docs` container: `sessions/<id>` (status), `reports/<id>`, `plans/plan_<id>`.

## When something is wrong

| What you see | Likely cause | Do this |
|---|---|---|
| The child's screen says it could not start | Account app cold or LiveKit unreachable | Wait 30 s, try once more. `healthz`, then the Account app log. If LiveKit Cloud is down, stop for the day |
| It starts, but Kemi never speaks | No clips (seed not run) or the agent is not in the room | Seed job status; Session Agent log (`session <id> starting`?); `az containerapp show` replica count |
| "Report is being made" for more than 10 minutes | A message in a dead-letter queue, or the Scorer/Core is down | Dead-letter counts; the Core and Reading Scorer logs; do not re-send until you know why |
| `core-events` dead letters grow | Core failing on an event | Read one message (portal Service Bus Explorer, peek), find the error in the Core log, fix, then re-send from the DLQ |
| The check "stopped before the end" | The child stopped, or the connection dropped for over 30 s | Nothing to fix. There is no report for it; start a new check |
| A guardian cannot sign in | The code email is late, or the Entra settings changed | Ask them to wait a minute and ask for a new code; check the Entra user flow still offers only the email code |
| A guardian says their child's name or data is wrong | Edit it in the app (Account) | If the data must go: the deletion section below |
| Anything about a child's data you did not expect | | Stop the sessions (`agent_on = false` PR, or tell families to wait), tell the team, write down what happened with ids only |

## After the day

- [ ] Dead-letter queues are 0.
- [ ] Hand counts and hand scores are done for validation (L4) without exporting audio: work in the cloud, not on laptops.
- [ ] `agent_on = false` again in `terraform.tfvars` if no more sessions are planned (a one-line `chore/infra-...` PR; the agent runs all day while it is true).
- [ ] The 90-day audio rule: audio is moved to cool storage after 30 days and deleted after 90 by the storage lifecycle policy (`infra/azure/main.tf`; I4 still has to confirm it on the live account, so run `az storage account management-policy show` once and keep the output). Transcripts and reports stay until a guardian asks for deletion.

## Deleting a child's data (a guardian asks)

The app does not delete; the study team does, on request, with `ops/delete_child.py` (it removes the audio, the sessions and everything under them, the report, plan and story request, the consents, the session records and the child, and writes one audit entry without the id or a name):

```
CLOUD=azure AZURE_COSMOS_ENDPOINT=... AZURE_STORAGE_ACCOUNT=... \
PYTHONPATH=libs/aloai:. python -m ops.delete_child --child-id <child id> --operator <your name>
```

It is a dry run and lists counts only. Check the counts, then add `--yes` to delete. Tell the guardian when it is done. The child id is in the guardian's account (the child's page); never ask for it in a message that also holds a name. The script has not been run against real Cosmos and Storage yet: run it first on the fictional child from the rehearsal.

## Who to call

Fill in before the day (this page is in Git, so use roles, not phone numbers; keep the numbers on the study team's private sheet): the person running the day, the technical contact (David), the data-protection contact named on the information sheet, and the Azure and LiveKit account owners.
