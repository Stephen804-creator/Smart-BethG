# Public Launch Legal and Privacy Checklist

**Created:** 2026-10-10 UTC  
**Last updated:** 2026-10-10 UTC  
**Status:** Planning checklist, not legal advice or an approved policy.

## What must be written now

Smart BethG is designed for public launch and processes prompts, conversations, files, generated artifacts, account information, provider usage records, and OAuth connections. Draft the Terms of Service and Privacy Policy during development, before public registration—not after launch. The current draft versions are tracked separately in the production-readiness PR; they must be reconciled with the actual product and reviewed before publication.

### Terms of Service should cover
- The legal operator and support/contact details.
- What the service does and what is experimental or unavailable.
- User accounts, security, acceptable use, abuse reporting, suspension and termination.
- User content, intellectual property, generated outputs, and the limited permissions needed to operate the service.
- AI accuracy limitations and the user's responsibility to review generated code/content before executing or publishing.
- Tool and connector permissions, the meaning and limits of user approvals, and prohibited actions.
- Third-party providers and the fact that their terms, pricing, availability, and data handling also apply.
- Pricing/billing/refunds if paid plans are introduced.
- Service availability, complaints, governing law, dispute process, and legally reviewed disclaimers/limitations.

### Privacy Policy should cover
- The actual legal entity/controller and a working privacy contact.
- Account data, prompts/conversations, uploaded files, memories, artifacts, logs, security events, and connector metadata.
- Each purpose and lawful basis for processing; consent is not the only possible lawful basis, and it must not be used as a blanket substitute for legal analysis.
- Every AI/search/storage/social provider that receives user data, what is sent, and where processing occurs.
- Retention/deletion schedules for accounts, conversations, files, logs, backups, and connector credentials.
- User rights and how to request access, correction, deletion, export, restriction, objection, or consent withdrawal.
- Security measures, incident/breach handling, cookies/sessions, international transfers, children/age eligibility, and changes to the policy.
- Separate opt-in consent for optional model-training use. Training export remains disabled until consent is recorded, versioned, and revocable.

## Who approves or reviews these documents?

There is no single universal government body that pre-approves every Terms of Service or Privacy Policy. The operator is responsible for making the documents accurate and publishing them; qualified legal counsel should review them for the jurisdictions and business model involved.

For Nigeria:
- Review the Nigeria Data Protection Act 2023 and current Nigeria Data Protection Commission (NDPC) guidance.
- Determine with qualified counsel or a licensed data-protection professional whether Smart BethG is a data controller/processor of major importance and whether NDPC registration, a Data Protection Officer, a compliance audit, or a Data Protection Compliance Organization (DPCO) is required for the actual processing scale and category.
- The NDPA provides for registration of controllers/processors of major importance. NDPC's current guidance defines relevant categories and thresholds; do not decide registration status from a generic checklist alone.
- If registration or an audit filing is required, follow the NDPC process and applicable DPCO requirements. Registration is not a substitute for a compliant Privacy Policy or secure implementation.
- If Smart BethG later serves users in other countries, assess the laws that apply there too; Nigerian incorporation does not automatically remove foreign obligations.

Official references:
- Nigeria Data Protection Act 2023: https://ndpc.gov.ng/download/nigeria-data-protection-act-2023
- NDPC official website and services: https://ndpc.gov.ng/
- NDPC registration guidance / resources: https://ndpc.gov.ng/resources/
- NDPC DPCO registration requirements: https://ftp.ndpc.gov.ng/dpco-registration-requirements/

## Product implementation required before publication

- [ ] Add Terms and Privacy links to registration/login and account settings.
- [ ] Store the accepted Terms version and timestamp; keep optional training consent separate.
- [ ] Add account data export/deletion and a documented deletion propagation process for files, artifacts, memories, conversations, provider-held data where possible, and backups.
- [ ] Publish a current subprocessor/provider list and data-flow map.
- [ ] Set and test retention periods and backup expiration.
- [ ] Configure privacy/security contact, complaint process, and incident response.
- [ ] Complete a data-protection risk assessment/DPIA where appropriate.
- [ ] Verify the NDPC/DPCO obligations with a qualified professional before deciding whether registration or audit filings are required.
- [ ] Have counsel review the final policy against the actual deployed application, not only a template.
- [ ] Do not describe a draft as “approved,” “certified,” or “compliant” until the relevant review or formal process has actually occurred.
