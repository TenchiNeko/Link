# Security policy

Do not report suspected vulnerabilities, exposed credentials, or private-data leaks in a public issue.

Until a dedicated private security contact is configured, contact the repository owner through the private GitHub security-reporting channel or another private channel already established with the owner. Include reproduction details, affected paths, and a safe contact method. Do not include live secrets in the report.

## Local safety rules

- Keep provider keys in environment variables or a local secret manager.
- Do not commit `.env` files, browser profiles, model weights, archives, logs, receipts, or private research inputs.
- Treat any credential found in repository history as compromised and rotate it immediately.
- Keep network endpoints loopback-only unless a deployment explicitly requires otherwise.
