# IAM — GitHub Actions → AWS

These are templates for the IAM role that `deploy-oracle.yml` assumes via OIDC. They are not applied automatically; a human runs the setup commands in [`docs/ORACLE_DEPLOY.md`](../../docs/ORACLE_DEPLOY.md#one-time-iam-setup) once, edits the placeholders, and sets the `AWS_DEPLOY_ROLE_ARN` repo variable.

| File | Purpose |
|------|---------|
| `gha-deploy-oracle-trust.json` | Who can assume the role — scoped to GitHub Actions runs from this repo on `main` (plus manual `workflow_dispatch`). |
| `gha-deploy-oracle-policy.json` | What the role can do — only `ssm:SendCommand` / `ssm:GetCommandInvocation` / `ssm:ListCommandInvocations` on the one oracle instance, and only with the `AWS-RunShellScript` document. |

## Placeholders to replace

Before applying:

| Placeholder | Where | What to put |
|-------------|-------|-------------|
| `<ACCOUNT_ID>` | both files | Your 12-digit AWS account ID (`aws sts get-caller-identity --query Account --output text`) |
| `<REGION>` | policy | The region the oracle instance lives in (currently `eu-central-1`) |
| `<INSTANCE_ID>` | policy | The oracle instance ID (currently `i-00ac444b94c5ff9b2`) |

## Scope rationale

- **Trust**: `token.actions.githubusercontent.com` + `repo:komapc/retro:ref:refs/heads/main` means only workflow runs on `main` (and `workflow_dispatch`, which still runs from whatever branch you pick) can assume the role. A PR branch cannot. This matches our deploy trigger.
- **Permissions**: `ssm:SendCommand` is the sharp tool — anyone with it can run arbitrary shell as root on the target instance. We scope it three ways: (a) resource ARN restricted to the one instance, (b) `ssm:DocumentName` condition restricting to `AWS-RunShellScript` (blocks e.g. `AWS-RunPowerShellScript` or custom documents), (c) no wildcard on the resource. `ssm:GetCommandInvocation` / `ssm:ListCommandInvocations` are scoped to the region but not per-command (the command-id is only known after `SendCommand` returns).
