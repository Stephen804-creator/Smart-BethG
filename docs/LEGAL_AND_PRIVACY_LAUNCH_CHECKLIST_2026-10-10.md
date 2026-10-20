# Smart BethG Legal and Privacy Launch Checklist

**Created:** 2026-10-10 UTC  
**Last updated:** 2026-10-10 UTC  
**Status:** Planning checklist; not legal advice and not a compliance certificate  
**Product target:** Public launch  
**Initial operating jurisdiction to assess:** Nigeria; users and providers may introduce additional jurisdictions.

## 1. Do not treat a copied template as an approved legal document

Smart BethG has draft Terms of Service and a draft Privacy Policy in this directory. They are internal working documents, not approved policies. They contain placeholders because the legal operator, exact data flows, retention periods, service providers, and launch jurisdictions must be confirmed first.

The owner may prepare the first draft. A qualified lawyer with Nigerian technology, contract, privacy/data-protection, and consumer-law experience should review and revise the documents before public launch. A government agency does not normally pre-approve every website's Terms of Service or Privacy Policy. Regulatory registration, notifications, audits, or other obligations may still apply depending on the operator's activities, scale, data, and legal classification. Do not describe a lawyer-reviewed document as “government approved” unless a specific authority has actually issued that approval.

## 2. Nigerian legal and regulatory review

Use official sources and ask counsel to assess the actual business model and current rules.

- **Nigeria Data Protection Act 2023 and NDPC guidance:** Start with the Nigeria Data Protection Commission (NDPC) website and the official Act. Determine Smart BethG's role as a data controller/processor, lawful bases for each purpose, data-subject rights, security measures, retention/deletion, breach response, data transfers, and whether registration or compliance-audit requirements apply. Do not assume every small developer automatically needs the same registration; equally, do not assume that being a startup or having few users automatically exempts the service. Ask counsel or a licensed Data Protection Compliance Organisation (DPCO) to determine classification and obligations using the current NDPC General Application and Implementation Directive.
- **Company/business identity:** If the product is offered commercially, decide which legal person operates it and who contracts with users. Check whether and when business-name or company registration is appropriate through the Corporate Affairs Commission (CAC). A product brand/domain alone does not establish the legal contracting entity.
- **Other applicable laws:** Have counsel assess consumer protection, electronic transactions/contracts, intellectual property/copyright, tax, advertising/marketing, cybersecurity, and any sector-specific obligations relevant to the final features and target users.
- **Other jurisdictions:** If Smart BethG deliberately targets people in the EU/UK, US states, or other jurisdictions, obtain advice on the laws triggered by those users and processing activities. Do not copy GDPR wording and assume it automatically makes the product compliant everywhere.

Official starting points (verify the current versions before relying on them):
- NDPC: https://ndpc.gov.ng/
- Nigeria Data Protection Act 2023: https://www.ndpc.gov.ng/ndp-act-2023/
- NDPC resources and guidance: https://ndpc.gov.ng/resources/
- NDPC DPCO registration/requirements: https://ftp.ndpc.gov.ng/dpco-registration-requirements/
- Corporate Affairs Commission: https://www.cac.gov.ng/
- CAC company registration: https://www.cac.gov.ng/services/company-registration

## 3. Evidence to prepare before asking for legal review

Prepare these items so counsel reviews the real service rather than generic wording:

- A data-flow map for registration, login/OAuth, conversations, prompts/responses, files, memory, projects, missions, research, artifacts, logs, backups, support requests, and account deletion.
- A list of AI/search and infrastructure providers, what data is sent to each, their configured retention/training options, and their applicable contractual terms.
- A data inventory with purpose, lawful basis, access roles, storage location, retention period, deletion behavior, and whether data is transferred internationally.
- A security control summary covering PostgreSQL, secrets, sessions/CSRF, authorization, rate limits, logs, backups, incident response, and current unresolved risks.
- A data-subject request workflow for access, correction, export, objection/restriction where applicable, deletion, and complaints.
- A clear explanation of AI output limitations, user responsibilities, tool approvals, external side effects, and the limits of reversibility.
- A documented training-data policy. Training export stays disabled until explicit, informed, recorded, revocable opt-in is implemented. Admin access is not user consent.
- The actual legal operator name, contact address/email, support channel, and planned countries of operation.
- Proposed account age rules, acceptable-use enforcement, suspension/termination, refunds/payment terms if payments are introduced, and dispute-handling process.

## 4. Required product controls before publication

- [ ] Keep registration available for controlled testing, with rate limits and abuse monitoring. Do not describe the service as public-launch-ready until the remaining security and privacy gates are signed off.
- [ ] Show the current Terms and Privacy Policy at registration and in account settings.
- [ ] Record which policy version a user accepted and when; do not bundle optional training consent into required service acceptance.
- [ ] Provide a separate opt-in training consent with purpose, scope, withdrawal, and consequences clearly explained.
- [ ] Implement account/data export and deletion, including related conversations, files, memories, knowledge chunks, artifacts, projects, research, evidence, provider records, and retention rules for backups.
- [ ] Document and implement retention/deletion schedules; do not promise immediate deletion from backups or third-party providers unless the system can deliver it.
- [ ] Identify subprocessors and explain when prompts/files are sent to external AI or search providers.
- [ ] Establish a privacy/security contact and incident/breach escalation procedure.
- [ ] Review the actual public domain, HTTPS, cookie behavior, security headers, backup restore, and deployment configuration.
- [ ] Obtain legal review of the final text and preserve the approved version and effective date.
- [ ] Re-review after material changes to data use, providers, payment features, target jurisdictions, or training policy.

## 5. Release decision

A document is ready to publish only after the operator and counsel confirm that it accurately describes the implemented product and applicable obligations. Store final policies separately from drafts, use version numbers/effective dates, and preserve prior versions for audit. This checklist does not certify compliance and does not replace advice from qualified counsel or a licensed DPCO where one is required.
