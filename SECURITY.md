# Security Policy for Stack4Things v2.0

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.0.x   | :white_check_mark: |
| < 2.0   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security vulnerability, please follow these steps:

### 1. **DO NOT** create a public GitHub issue

### 2. Email Security Team

Send an email to: **security@stack4things.io**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### 3. Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Depends on severity

### 4. Severity Levels

- **Critical**: Remote code execution, authentication bypass
- **High**: SQL injection, XSS, privilege escalation
- **Medium**: Information disclosure, CSRF
- **Low**: Information leakage, minor issues

### 5. Disclosure Policy

- We will acknowledge receipt of your report
- We will keep you informed of the progress
- We will credit you in the security advisory (if desired)
- We will notify you when the vulnerability is fixed

## Security Best Practices

### For Developers

1. **Never commit secrets**: Use environment variables or secret management
2. **Keep dependencies updated**: Run `poetry update` regularly
3. **Run security scans**: Use Bandit, Safety, Snyk before committing
4. **Follow secure coding practices**: OWASP Top 10 guidelines
5. **Review code**: All PRs require security review

### For Users

1. **Keep Stack4Things updated**: Always use the latest version
2. **Use strong passwords**: Enable MFA when available
3. **Limit access**: Follow principle of least privilege
4. **Monitor logs**: Check for suspicious activity
5. **Report issues**: Use the security email above

## Security Scanning

We use automated security scanning:

- **Bandit**: Static analysis for Python
- **Safety**: Dependency vulnerability checking
- **Snyk**: Comprehensive security scanning
- **Trivy**: Container image scanning
- **Dependabot**: Automated dependency updates

## Security Updates

Security updates are released:
- **Critical**: Immediately
- **High**: Within 7 days
- **Medium**: Within 30 days
- **Low**: Next release cycle

## Contact

For security concerns: **security@stack4things.io**

For general questions: See [CONTRIBUTING.md](../CONTRIBUTING.md)

