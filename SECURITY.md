# Security

## Supported Versions

This project is pre-1.0. Security fixes are made on the default branch.

## Reporting A Vulnerability

Do not open a public issue for suspected secret exposure or filesystem-write
vulnerabilities. Report privately to the repository owner.

If you are unsure who owns the public fork you are using, avoid sharing API keys
or private paths in the report and include only a minimal reproduction.

## Secret And Filesystem Safety

- The tool reads `NARA_API_KEY` from environment variables or local env files.
- API keys should never be committed.
- MCP write tools are disabled unless `NARA_MCP_WRITE_ROOT` is set.
- Download and source-packet commands refuse unsafe overwrites by default.
