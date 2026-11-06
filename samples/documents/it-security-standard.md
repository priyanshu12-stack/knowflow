# IT Security Standard — Northwind Labs (synthetic sample)

> Synthetic demo content written for KnowFlow. Northwind Labs is a fictional company.
> Standard ID SEC-STD-3, version 3.1, owner: IT Security.

## Passwords and authentication

Passwords must be at least 14 characters long. Multi-factor authentication (MFA) is mandatory for
email, the VPN and every system that holds customer data. Hardware security keys are required for
administrators. Passwords must never be reused across systems and are stored only in the company
password manager, Vaultline.

## Devices

All laptops use full disk encryption and lock the screen after 5 minutes of inactivity. Personal
devices may access email only through the managed mobile app. USB storage devices are blocked by
default; exceptions are requested through ticket category SEC-USB and expire after 30 days.

## Data classification

Data is classified as Public, Internal, Confidential or Restricted. Restricted data (for example
customer payment data and health information) may only be stored in systems approved by IT
Security and must never be sent by email. Confidential data may be shared externally only through
the approved file-sharing service with links that expire after 14 days.

## Incident reporting

Suspected security incidents, including phishing emails that were clicked, must be reported to
IT Security within 1 hour through the SEC-INCIDENT ticket category or by calling the security
hotline at extension 4444. Do not try to investigate an incident yourself.

## Access reviews

Managers review the system access of their team every quarter. Access for leavers is removed on
their last working day by 18:00.
