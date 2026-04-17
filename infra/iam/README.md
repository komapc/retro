# IAM — GitHub Actions → AWS

These are templates for the IAM role that `deploy-oracle.yml` assumes via OIDC. They are not applied automatically; a human runs the setup commands in [`docs/ORACLE_DEPLOY.md`](../../docs/ORACLE_DEPLOY.md#one-time-iam-setup) once, edits the placeholders, and sets the `AWS_DEPLOY_ROLE_ARN` repo variable.

| File | Purpose |
|------|---------|
| `gha-deploy-oracle-trust.json` | Who can assume the role — scoped to GitHub Actions runs from this repo on `main` (plus manual `workflow_dispatch`). |
| `gha-deploy-oracle-policy.json` | What the role can do — `ssm:SendCommand` scoped to the one oracle instance *and* only the `AWS-RunShellScript` document, plus read-only `ssm:Get*/List*Command*` for polling results. See "Why `SendCommand` is two separate statements" below. |

## Placeholders to replace

Before applying:

| Placeholder | Where | What to put |
|-------------|-------|-------------|
| `<ACCOUNT_ID>` | both files | Your 12-digit AWS account ID (`aws sts get-caller-identity --query Account --output text`) |
| `<REGION>` | policy | The region the oracle instance lives in (currently `eu-central-1`) |
| `<INSTANCE_ID>` | policy | The oracle instance ID (currently `i-00ac444b94c5ff9b2`) |

## Scope rationale

- **Trust**: `token.actions.githubusercontent.com` + `repo:komapc/retro:ref:refs/heads/main` means only workflow runs on `main` (and `workflow_dispatch`, which still runs from whatever branch you pick) can assume the role. A PR branch cannot. This matches our deploy trigger.
- **Permissions**: `ssm:SendCommand` is the sharp tool — anyone with it can run arbitrary shell as root on the target instance. We scope it two ways: the instance ARN is restricted to the one oracle box, and the document ARN is restricted to `AWS-RunShellScript` (blocks e.g. `AWS-RunPowerShellScript` or custom documents). `ssm:GetCommandInvocation` / `ssm:ListCommandInvocations` are scoped to the region but not per-command (the command-id is only known after `SendCommand` returns).

### Why `SendCommand` is two separate statements

`ssm:SendCommand` is a [multi-resource action](https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonsystemsmanager.html#amazonsystemsmanager-actions-as-permissions): IAM evaluates it against the **instance** ARN *and* the **document** ARN at the same time, and both must match an `Allow`. We need to express "instance X AND document Y", not "instance X OR document Y".

A single statement with both ARNs in the `Resource` array expresses OR (the semantics of IAM `Resource` lists), which fails the two-resource check. The earlier form of this template did exactly that:

```json
// DO NOT — denied with "no identity-based policy allows the ssm:SendCommand action on resource: instance/..."
"Resource": [
  "arn:aws:ec2:...:instance/<INSTANCE_ID>",
  "arn:aws:ssm:...::document/AWS-RunShellScript"
],
"Condition": { "StringEquals": { "ssm:DocumentName": "AWS-RunShellScript" } }
```

Splitting into two statements (one per resource) gives the evaluator an independent `Allow` for each check, which is the form AWS documents. The `ssm:DocumentName` condition was redundant belt-and-suspenders in the broken form and isn't needed now that the document ARN is scoped directly.

Diagnosed live during the first smoke test of the Tier 4 workflow; see PR #49 comments for context.
