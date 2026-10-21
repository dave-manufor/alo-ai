# ops: things done outside Terraform

The complete record of out-of-Terraform setup. Add any new manual step here in the same PR. Never put secret values in this file.

## Delete one child's data (`delete_child.py`)

A guardian can ask for their child's data to be deleted at any time (PRD 12). Until the delete-child screen exists, a person runs this script.

**What it removes:** the child's sessions and everything under them (turns, quick grades, the final grading, Phase 1 telemetry, errors), the reading audio and any plan summary audio, the report, plan and story request for each session, a story written for the child (only a generated one, never a bank passage), every consent record, and the child. It writes one `audit_log` entry that holds the operator and counts, and the child id only as a hash. It does not touch the guardian's own record, other children, or the shared clips.

**Steps**
1. Confirm the request comes from the guardian who owns the child (reply to the email they signed in with). Get the child id from the guardian, or from the Cosmos `children` documents for that `guardian_id`.
2. Point at the right cloud with the usual environment (`CLOUD=azure`, `AZURE_COSMOS_ENDPOINT`, `AZURE_STORAGE_ACCOUNT`, signed in with `az login` as someone with data access; see `infra/azure/README.md`).
3. Dry run first. It prints counts only:
   ```
   PYTHONPATH=libs/aloai:. python -m ops.delete_child --child-id <child id> --operator <your name>
   ```
4. If the counts look right, delete:
   ```
   PYTHONPATH=libs/aloai:. python -m ops.delete_child --child-id <child id> --operator <your name> --yes
   ```
5. Run the dry run again. It should say "nothing found". If a run stopped part way, run it again; audio is removed first and the child document last, so it is safe to repeat.
6. Tell the guardian it is done.

**Tested against** in-memory stores only (`pytest -c ops/pyproject.toml ops`). It has not been run against a real Cosmos DB or storage account: do the first real run on a test child (made through the Account API) and check the counts.

**Not covered:** the script does not delete clips in the shared clip store (including any made for a generated story), and it only finds a child's data through the child's sessions and consents. Anything stored under another key would need adding here.
