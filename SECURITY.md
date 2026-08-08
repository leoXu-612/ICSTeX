# Security Policy

## Supported releases

Security fixes are provided for the latest published prerelease or stable
release. Older builds may no longer receive fixes.

## Reporting a vulnerability

Do not open a public issue containing exploit details or private document
content. Use GitHub's **Report a vulnerability** form in the repository's
Security tab. Include the affected version, reproduction steps, and the minimum
test fixture needed to demonstrate the issue.

ICSTeX is local-first. Never attach a real thesis, bibliography, PDF, log, or
screenshot when a reduced synthetic fixture can reproduce the problem.

## Compilation boundary

Published builds disable project-local latexmk configuration and TeX shell
escape. Projects that require executable build hooks are outside the supported
security boundary.
