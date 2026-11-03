# Smart BethG — Business, Privacy, Security, Legal and Trust Criteria

**Document type:** Standing product and release criteria  
**Created:** 2026-11-01  
**Status:** Working requirements baseline — not a legal opinion, compliance certificate, or release approval  
**Applies to:** Smart BethG web application, APIs, workers, AI features, integrations, data stores, customer operations, marketing, billing, and future products/features  
**Owner decision:** These criteria are mandatory planning and release requirements. They must be reviewed whenever the product, business model, data practices, providers, or target markets materially change.

> **Purpose:** This file is the place to check what Smart BethG must satisfy before launch and as it evolves. A policy page alone does not satisfy a requirement. Each requirement must be matched to the real implementation, actual business operations, evidence, and applicable law.

## 0. How to use this document

For every checklist item, record:
- **Status:** Not assessed / Needs investigation / Gap identified / In progress / Implemented, awaiting test / Tested and verified / Approved for release / Not applicable (with reason).
- **Evidence:** File path, test name/result, configuration, contract, operational record, or review.
- **Owner:** Person responsible for the correction or decision.
- **Date:** Last verified date.
- **Jurisdiction:** Markets/laws to which the finding applies.

Do not mark an item complete because a page, policy, checkbox, or code comment exists. Verify the behavior end-to-end. “Not applicable” requires a written reason and approval; it must not be used to hide an unresolved question.

This document is a criteria register, not a declaration that Smart BethG already meets the criteria. Existing implementation and older documents must be inspected before status is assigned.

## 1. A — Legal identity, business operations and applicable law

### 1.1 Identify the actual operator
- [ ] Decide and document who operates Smart BethG and contracts with users: an individual, registered business name, company, or another legal entity.
- [ ] Record the operator's correct legal name, trading/product name, registration details where applicable, business/contact address, support email, and complaint channel.
- [ ] Identify who owns the domain, code, trademarks, content, customer relationships, payment accounts, and provider accounts.
- [ ] Ensure invoices, payment descriptors, Terms, Privacy Policy, marketing, support replies, and contracts identify the same responsible operator.
- [ ] Do not invent company registration numbers, addresses, regulatory approvals, or business credentials.

### 1.2 Determine the applicable legal framework
- [ ] Assess Nigerian obligations, including the Nigeria Data Protection Act 2023 and current NDPC regulations, directives and guidance.
- [ ] Ask qualified counsel to determine whether NDPC registration, DPCO engagement, compliance audits, a Data Protection Officer, DPIAs, or other formal duties apply to the actual operator and processing.
- [ ] Assess consumer protection, electronic contracting, advertising, intellectual property, copyright, tax, cybersecurity, employment/contractor, and sector-specific obligations relevant to the actual business.
- [ ] Identify countries where Smart BethG is established, marketed, offered, or intentionally used; assess laws triggered by those markets and the people whose data is processed.
- [ ] Do not assume Nigerian law is the only applicable law, and do not copy GDPR wording as a substitute for jurisdiction-specific analysis.
- [ ] Maintain a jurisdiction register with legal source, applicability rationale, required action, reviewer, and review date.
- [ ] Reassess when target markets, business entity, user types, or processing activities change.

### 1.3 Verify actual business practices
- [ ] Map how users discover, register for, pay for, use, cancel, complain about, and leave the service.
- [ ] Document customer support responsibilities, response expectations, escalation, refunds, service suspension, account closure, and dispute handling.
- [ ] Confirm the business can operationally honour every promise in its policies and marketing.
- [ ] Maintain an incident response and customer-notification procedure.
- [ ] Keep records of material policy decisions, approvals, complaints, refunds, incidents, and corrective actions.

## 2. B — Privacy, personal data and user rights

### 2.1 Data inventory and minimization
- [ ] Inventory every data category collected or generated: account details, contact information, authentication/session data, conversations, prompts/responses, files, memory, knowledge, projects, missions, workflows, artifacts, research, logs, telemetry, payment/support records, and device/browser data.
- [ ] For each category, document purpose, necessity, lawful basis, collection point, access roles, recipients, storage location, retention period, deletion behavior, and cross-border transfers.
- [ ] Collect only information needed for a specified, legitimate purpose. Remove unused form fields, analytics, identifiers, permissions, and SDK collection.
- [ ] Do not reuse information for a materially different purpose without assessing and meeting the applicable transparency and lawful-basis requirements.
- [ ] Separate required service processing from optional analytics, marketing, personalization, and model-improvement activities.
- [ ] Do not put sensitive information into logs, analytics, URLs, error reports, or third-party tools without a documented need and safeguards.

### 2.2 Lawful basis, notices and consent
- [ ] Identify and document a valid lawful basis for each processing purpose; do not treat consent as the universal basis for all processing.
- [ ] Explain material processing at the point where it occurs, in plain language and before the relevant choice or action.
- [ ] Record the applicable notice/policy version, timestamp, account or subject reference, choice, purpose, and withdrawal where consent is relied upon.
- [ ] Make optional choices genuinely optional and separate from acceptance required to use the core service.
- [ ] Do not bundle consent into general Terms, hide it in long documents, preselect a consent checkbox where prohibited, or use manipulative wording.
- [ ] Provide a clear way to change preferences and withdraw consent; ensure withdrawal stops future processing that depended on that consent.
- [ ] Keep evidence of notices and choices without retaining unnecessary personal data.

### 2.3 Data subject rights and lifecycle
- [ ] Provide a practical workflow for access, correction, portability/export where applicable, objection/restriction where applicable, deletion, consent withdrawal, and complaints.
- [ ] Verify requesters proportionately without collecting excessive identity documents.
- [ ] Define response ownership, statutory timelines, identity checks, exceptions, escalation, and evidence retention.
- [ ] Implement account closure and deletion across PostgreSQL records, conversations, files, memories, knowledge chunks, projects, missions, workflows, artifacts, research, evidence, caches, search indexes, logs, backups, and subprocessors as applicable.
- [ ] Document what can be deleted immediately, what expires through backup rotation, what must be retained by law, and what cannot be recalled from a third party.
- [ ] Do not promise immediate or universal deletion unless every relevant system and provider can actually deliver it.
- [ ] Provide an export of a user's own data as a user-initiated rights/product feature, with authentication, authorization, scope, secure delivery, expiry, and audit controls.
- [ ] Keep the export of a user's own data distinct from exporting user data for AI training or product improvement.

### 2.4 Retention, transfers and incidents
- [ ] Define retention periods by data category and purpose; implement scheduled deletion and verify it.
- [ ] Document data residency, international transfers, transfer safeguards, and provider locations.
- [ ] Maintain a breach response plan covering detection, containment, evidence preservation, risk assessment, legally required notifications, affected-user communication, and post-incident remediation.
- [ ] Test backup restoration and deletion/retention behavior against real deployment infrastructure.
- [ ] Maintain a current data-flow diagram and records of processing.

## 3. C — AI, memory, model improvement and training-data governance

This section separates three different concepts. They must never be conflated in UI, policy, implementation, or marketing.

1. **Memory/personalization:** Information retained to personalize a user's own experience. It has its own purpose, controls, retention and deletion behavior.
2. **User data export:** A user-initiated copy of their own information for access, portability, or download. It is not permission to train models.
3. **Training/model-improvement contribution:** Use of eligible user content to evaluate, improve, or train AI systems. This is a separate processing purpose with separate transparency, legal analysis, controls, and records.

### 3.1 Owner's requested product direction — default ON with prominent notice
- [ ] Product direction requested by the owner: model-improvement/training contribution should be **ON by default**, with a clear, prominent, plain-language notice and an easy-to-find control to turn it off.
- [ ] This is a product preference, **not yet a legal approval or permission to enable training**. Before default-ON is activated, qualified counsel must assess the lawful basis, fairness, transparency, user expectations, user categories, data types, provider contracts, and every target jurisdiction.
- [ ] If applicable law, regulator guidance, provider contract, customer contract, or the nature of the data requires prior affirmative consent/opt-in, the affected processing must be OFF until that valid opt-in is obtained. The owner's default-ON preference cannot override a legal requirement.
- [ ] If default-ON is approved for a defined context, show the notice at an appropriate first-use/collection point, before eligible data is used; do not bury it in Terms or rely on users reading long agreements.
- [ ] The notice must state what content is eligible, what is excluded, the purposes, whether humans may review it, whether external providers receive it, retention, withdrawal, and realistic limits on removing data already used.
- [ ] Provide a persistent, accessible, straightforward control in account/privacy settings. Turning it off must not require contacting support or navigating an obstructive flow.
- [ ] Keep a visible status and record the applicable notice version, default state, user change, timestamp, and processing scope.
- [ ] Never infer agreement to training from account creation, general Terms acceptance, use of Memory, or a user-initiated data export.
- [ ] Apply stricter rules or disable contribution for children, sensitive/special-category information, confidential workspace content, secrets, third-party personal data, and any category not approved by legal and security review.
- [ ] Do not use a default setting to override contractual confidentiality, enterprise/workspace controls, or a provider's prohibition.

### 3.2 Training pipeline safeguards
- [ ] Keep the existing training export/contribution pipeline disabled until the notice, preference controls, legal review, eligibility filters, audit trail, security controls, and withdrawal behavior are implemented and tested.
- [ ] Define exact eligible sources, fields, content types, user/account types, and purposes. No broad “everything in the database” export.
- [ ] Exclude passwords, credentials, API keys, tokens, payment data, authentication secrets, private keys, highly sensitive information, and other prohibited content before any export.
- [ ] Detect and exclude or appropriately handle third-party personal data and confidential information that the user may have pasted or uploaded.
- [ ] Minimize, redact, pseudonymize, or anonymize data where appropriate; do not claim data is anonymous if re-identification remains reasonably possible.
- [ ] Separate identity/consent records from training content and use least-privilege access.
- [ ] Encrypt data in transit and at rest; use controlled storage, short-lived export links where relevant, integrity checks, access logs, retention limits, and deletion controls.
- [ ] Require review/approval for dataset creation, transfer, access, and provider delivery. Log who performed the operation and which dataset version was created without copying raw content into audit logs.
- [ ] Maintain dataset lineage: source categories, policy/notice version, eligibility rules, transformation, destination, date, retention, and deletion/withdrawal status.
- [ ] Review each AI provider's training, retention, human review, region, subprocessors, and contractual terms. Do not send data for a provider's independent training unless separately assessed, disclosed, and lawfully authorized.
- [ ] Define what withdrawal means for queued exports, stored datasets, derived datasets, evaluation sets, fine-tuning jobs, and models already trained. Do not promise machine unlearning or recall where it is not technically available.
- [ ] If deletion from an already-created dataset or trained model is not feasible, explain that limitation before the relevant choice and assess whether the processing should be offered at all.
- [ ] Provide an auditable pause/kill switch that stops new selection, export, transfer, and training jobs.
- [ ] Test cross-user isolation, exclusion filters, consent/preference enforcement, revocation, worker crashes, duplicate jobs, and secure deletion.

### 3.3 AI transparency and user protection
- [ ] Explain which AI providers may process prompts/files and whether content is sent outside Smart BethG infrastructure.
- [ ] Describe relevant limitations, human review, output uncertainty, and user responsibilities accurately.
- [ ] Do not claim a model is private, local, confidential, unbiased, fully accurate, or trained only on specified data unless verified.
- [ ] Separate Smart BethG's own model-improvement use from third-party provider processing and provider training settings.
- [ ] Document human access to conversations and support/admin workflows, including purpose, authorization, and audit.

## 4. D — Customer rights, commercial terms and fair business practices

### 4.1 Pricing, payments and refunds
- [ ] Display the full price, currency, billing interval, taxes/mandatory charges where known, usage limits, renewal behavior, and additional fees before purchase.
- [ ] No hidden fees, misleading discounts, deceptive countdowns, fake scarcity, or preselected paid add-ons.
- [ ] Explain free trials, automatic renewals, failed payments, grace periods, suspension, cancellation, refunds, chargebacks, and credit expiry before the user commits.
- [ ] Make cancellation accessible and no more difficult than signup/payment, subject to legitimate security checks.
- [ ] Implement refund policy promises in the payment, wallet, support and accounting workflows; test duplicate charges, failed webhooks, partial refunds, reversals, and disputes.
- [ ] Do not publish a blanket “no refunds” statement without legal review and consideration of mandatory consumer rights.
- [ ] Reconcile payment provider records with Smart BethG account entitlements and maintain an auditable ledger.

### 4.2 Honest presentation and marketing
- [ ] Remove fake reviews, fabricated testimonials, undisclosed incentivized endorsements, and misleading ratings.
- [ ] Do not publish unsupported claims about security, privacy, uptime, accuracy, integrations, model capabilities, certifications, customer numbers, or performance.
- [ ] Distinguish available, beta, planned, experimental, and unavailable features.
- [ ] Ensure screenshots, demos, landing pages, onboarding, pricing pages, and sales material reflect actual product behavior.
- [ ] Do not use dark patterns, forced consent, confusing cancellation, deceptive defaults, or obstructive account deletion.
- [ ] Provide a usable complaint and support route and handle complaints consistently with published commitments.

### 4.3 Email and communications
- [ ] Classify transactional, security, service, and marketing emails separately.
- [ ] Include a working unsubscribe mechanism in marketing emails and honour it within applicable legal timelines.
- [ ] Do not make unsubscribe dependent on login or unnecessary data collection.
- [ ] Record communication preferences and suppress opted-out recipients from future marketing sends.
- [ ] Identify the sender and provide a valid contact method.

## 5. E — Cookies, tracking, SDKs and third parties

### 5.1 Cookie and browser-storage inventory
- [ ] Inventory cookies, local/session storage, pixels, analytics, advertising tags, embedded content, fingerprinting, and similar technologies.
- [ ] Classify each by purpose and whether it is strictly necessary or optional under applicable law.
- [ ] Document provider, data received, expiry, location, recipients, opt-out behavior, and retention.
- [ ] Do not load optional non-essential tracking before the required consent where applicable.
- [ ] Implement a clear cookie banner with meaningful accept/reject/customize choices; rejecting optional cookies must be as easy as accepting them.
- [ ] Provide a persistent way to revisit and change cookie preferences.
- [ ] Ensure the Cookie Policy matches observed browser behavior and actual tag firing.

### 5.2 Third-party SDKs and subprocessors
- [ ] Maintain a current inventory of every SDK, library, analytics tool, AI provider, search provider, payment service, email service, hosting provider, monitoring service, and integration.
- [ ] For each, review purpose, permissions, data collected, data sent, retention, location, subprocessors, security posture, privacy terms, contract/DPA, and deletion support.
- [ ] Remove unused SDKs, packages, trackers, permissions, and endpoints.
- [ ] Configure privacy/security settings rather than assuming vendor defaults are appropriate.
- [ ] Maintain a public subprocessor disclosure where required and notify users of material changes as required by law/contract.
- [ ] Review provider terms before integration and periodically after changes.
- [ ] Do not claim an integration is active when it is only a catalog entry or planned adapter.

## 6. F — Application, API, infrastructure and operational security

### 6.1 Authentication and authorization
- [ ] Protect admin routes and privileged actions on the server; hiding a button or route link is not authorization.
- [ ] Enforce role, ownership, organization/workspace membership, and object-level permissions on every relevant API and background job.
- [ ] Ensure users can access only their own records unless a deliberate, authorized sharing model grants access.
- [ ] Apply PostgreSQL Row-Level Security where appropriate as defence in depth, with tests for both application and direct database access paths.
- [ ] Verify email addresses where required by account-risk and product design.
- [ ] Hash passwords with a modern password-hashing algorithm and safe parameters; never store plaintext or reversibly encrypted passwords.
- [ ] Protect sessions and tokens; use secure, HttpOnly, SameSite cookies where appropriate, rotate/invalidate sessions correctly, and keep secrets out of insecure browser storage.
- [ ] Add appropriate MFA and recovery protections for administrators and high-risk actions.
- [ ] Test account enumeration, credential stuffing, session fixation, privilege escalation, IDOR/BOLA, CSRF, and unauthorized role changes.

### 6.2 Secrets and source control
- [ ] Keep API keys, signing secrets, database passwords, OAuth secrets, webhook secrets, and private keys on the server or in an approved secret manager.
- [ ] Check environment variable names, required values, production configuration, secret rotation, and fail-closed behavior.
- [ ] Ensure .env files, credentials, dumps, private keys, and secret-bearing artifacts are excluded from Git.
- [ ] Scan the current tree and full Git history for leaked secrets; revoke/rotate any exposed credential. Removing a secret from the latest commit does not make a leaked credential safe.
- [ ] Restrict secret access by service/worker role; do not give file or execution workers unrelated provider keys.
- [ ] Never include secrets in logs, error messages, client bundles, source maps, screenshots, or issue reports.

### 6.3 Input, API and browser security
- [ ] Use parameterized database queries and safe ORM/query construction.
- [ ] Validate and normalize inputs server-side; apply context-appropriate output encoding and sanitization.
- [ ] Protect against XSS, SQL/NoSQL injection, CSRF, SSRF, path traversal, request smuggling, open redirects, and unsafe deserialization as applicable.
- [ ] Validate file uploads by size, type/signature, content, archive structure, malware scan, storage destination, and access policy; never trust the client MIME type or filename.
- [ ] Verify webhook signatures, timestamps/replay protections, event authenticity, idempotency, and amount/currency/account details.
- [ ] Rate limit authentication, password reset, sensitive APIs, uploads, exports, webhooks, expensive AI actions, and administrative operations.
- [ ] Add appropriate security headers, including a tested Content Security Policy, HSTS in HTTPS production, nosniff, and suitable frame/referrer policies.
- [ ] Restrict CORS to exact required origins; do not use wildcard credentialed access.
- [ ] Secure API endpoints with authentication, authorization, schema validation, quotas, and consistent error handling.
- [ ] Turn off debug mode and verbose exception disclosure in production.
- [ ] Scan exposed files, directory listings, backups, debug endpoints, admin interfaces, source maps, and accidental public storage.

### 6.4 Database, storage, workers and dependencies
- [ ] Lock down database roles, network access, TLS, privileges, backups, migrations, and administrative access.
- [ ] Ensure private storage buckets/objects and owner-scoped file access; test signed URL scope and expiry.
- [ ] Keep dependencies patched; review advisories, lockfiles, transitive dependencies, abandoned packages, and unnecessary packages.
- [ ] Maintain SBOM/dependency inventory and repeatable dependency/security scans.
- [ ] Separate web, file-inspection, AI/provider, and untrusted-code workers according to least privilege and threat model.
- [ ] Enforce resource limits, job authorization, durable state, retry limits, idempotency, cancellation, cleanup, and crash recovery.
- [ ] Keep sensitive data out of logs; set access controls and retention for logs, traces, metrics, and backups.
- [ ] Monitor suspicious access and privileged operations without collecting unnecessary user content.

### 6.5 Mandatory hostile-input and isolated-host release gate
The following tests are mandatory for relevant file-processing and untrusted-code execution capabilities. They must be performed on the **actual isolated execution host** before public execution is enabled; CI or a developer laptop alone cannot certify host isolation.

- [ ] Hostile code: malicious programs, sandbox escape attempts, privilege escalation, unauthorized filesystem access, and attempts to read another user's files/secrets.
- [ ] Malicious uploads: executable payloads, malformed files, oversized requests, spoofed MIME types, scanner outages/timeouts, and fail-closed behavior.
- [ ] Archive attacks: ZIP bombs, path traversal, symlinks/special files, duplicate paths, encrypted/nested archives, decompression exhaustion, and expansion limits.
- [ ] Cross-user access: attempts to read, change, export, execute, or delete another user's files, projects, jobs, logs, outputs, and artifacts.
- [ ] Network restrictions: internet egress, internal services, cloud metadata endpoints, private networks, DNS, and unauthorized destinations.
- [ ] Resource exhaustion: CPU, memory, swap, disk, process/PID, file descriptors, output size, concurrency, and execution-time limits.
- [ ] Worker crashes: terminate workers during inspection and execution; verify leases, retries, reconciliation, no unauthorized duplicate work, and recovery.
- [ ] Docker cleanup: verify containers, mounts, temporary files, volumes, processes, and other resources are removed after success, failure, timeout, cancellation, and crash.
- [ ] Demonstrate backup/restore and operational recovery for the services involved.
- [ ] Record test environment, host configuration, attack case, expected result, actual result, evidence, tester, date, and remediation.
- [ ] Require all applicable tests to pass, operational recovery to be demonstrated, and an authorized operator to approve release. Any unresolved critical/high-risk finding blocks release unless a documented, legally acceptable exception is approved by the designated risk owner.

## 7. G — Accessibility, content, intellectual property and responsible design

### 7.1 Accessibility
- [ ] Provide meaningful alt text for informative images; decorative images must be ignored by assistive technology.
- [ ] Use semantic headings, landmarks, labels, buttons, links, tables, and form controls.
- [ ] Ensure all functionality is operable by keyboard, with logical focus order, visible focus, no keyboard traps, and accessible dialogs/menus.
- [ ] Meet WCAG 2.2 AA as the target baseline unless a stricter applicable requirement applies.
- [ ] Verify text and interface color contrast, including hover, disabled, focus, error, placeholder, and dark-mode states.
- [ ] Provide accessible validation errors, status announcements, captions/transcripts where relevant, scalable text, and responsive layouts.
- [ ] Test with keyboard-only navigation and representative screen readers; automated scans alone are insufficient.

### 7.2 Content, claims and design integrity
- [ ] Remove dark patterns, misleading interface labels, fake reviews, unsupported claims, hidden fees, false urgency, and deceptive defaults.
- [ ] Distinguish generated/AI content from human-authored endorsements where material.
- [ ] Make consent, cancellation, privacy settings, data export, and deletion discoverable and usable.
- [ ] Keep product documentation, screenshots, onboarding and marketing aligned with real functionality.

### 7.3 Fonts, images, code and other licences
- [ ] Maintain an asset and software licence register covering fonts, images, icons, illustrations, templates, datasets, code, models, runtimes, SDKs, and bundled libraries.
- [ ] Record asset/source, creator/vendor, exact version, SPDX or licence identifier where available, licence text/URL, commercial-use permission, attribution, modification, redistribution, sublicensing, copyleft/source obligations, and required notices.
- [ ] Check the licence of the asset itself and its bundled dependencies; do not assume a tool's main licence covers all assets or plugins.
- [ ] Obtain a valid licence or documented permission before using commercial/restricted assets.
- [ ] Keep copies of receipts, licence files, permissions, notices, and source provenance.
- [ ] Do not use assets whose commercial terms require a separate permission agreement unless the operator has reviewed and obtained that agreement.
- [ ] Review generated content and user-uploaded content rights; do not promise ownership or unrestricted commercial use without checking the applicable provider and source terms.

## 8. H — Policies, notices and customer-facing documentation

The following documents must be drafted from verified product behavior and actual business operations. They are drafts until reviewed and approved; publishing them does not itself establish compliance.

- [ ] Privacy Policy.
- [ ] Terms of Service / Terms of Use.
- [ ] Refund, cancellation, renewal and payment policy (when payment features are offered).
- [ ] Cookie Policy and cookie preference/consent notice.
- [ ] AI data use, memory and model-improvement transparency notice.
- [ ] Separate training/model-improvement notice and preference explanation.
- [ ] Data access, export, correction and deletion request instructions.
- [ ] Security and vulnerability disclosure policy/contact.
- [ ] Acceptable Use Policy.
- [ ] Third-party provider/subprocessor disclosure.
- [ ] Email and marketing communication policy/preferences.
- [ ] Accessibility statement and contact route.
- [ ] Business identity, support, complaints and legal contact information.
- [ ] Any required child-safety/age-assurance and parental-consent notices if the service lawfully serves children or collects children's data.

For each published document:
- [ ] Identify the responsible legal operator.
- [ ] Use accurate, plain language and avoid unsupported claims.
- [ ] Include version, effective date, scope, contact, and relevant user choices.
- [ ] Link it at the relevant decision point and make the current version accessible from account/settings pages.
- [ ] Preserve prior versions and acceptance records where legally appropriate.
- [ ] Obtain qualified legal review for relevant jurisdictions before public launch.
- [ ] Confirm that the product and customer-support operations can fulfil every promise.
- [ ] Re-review after material changes and notify users where required.

## 9. Children and age-appropriate safeguards

- [ ] Decide and document the intended minimum age and whether children are permitted to use Smart BethG.
- [ ] Do not knowingly collect children's personal data without first assessing applicable age thresholds, lawful basis, parental/guardian authorization requirements, and child-protection obligations.
- [ ] If children are not an intended audience, implement proportionate age/eligibility controls and a process for handling discovered child accounts/data.
- [ ] If children are lawfully served, implement age-appropriate notices, parental/guardian consent and verification where required, minimization, safety defaults, access controls, retention, and deletion.
- [ ] Do not use children's data for training/model improvement by default; require a separate legal and safety assessment and any required valid authorization.
- [ ] Provide a parent/guardian contact and request process where applicable.

## 10. Operational evidence, governance and recurring review

- [ ] Maintain the data inventory, data-flow map, provider/subprocessor register, asset/licence register, jurisdiction register, policy versions, security test evidence, and risk register.
- [ ] Assign an accountable owner to each requirement and risk.
- [ ] Review access privileges and provider integrations periodically and when staff/contractors leave or roles change.
- [ ] Re-run dependency, secret, security, privacy, accessibility, and licence checks on a defined schedule and after material changes.
- [ ] Add a privacy/security/legal impact review to feature planning and pull-request review for changes involving data, providers, payments, user permissions, tracking, AI training, or external effects.
- [ ] Maintain incident, complaint, deletion, consent withdrawal, refund, and data-subject request records with appropriate access and retention.
- [ ] Make compliance status visible to release decision-makers; do not rely on informal chat history as the only record.

## 11. Release gate and sign-off

Smart BethG must not be described as fully compliant, legally approved, secure, or ready for unrestricted public launch merely because this document or policy pages exist.

A release that introduces or materially changes data processing, payments, AI training, external integrations, file handling, untrusted execution, or public access must have an impact review.

Before unrestricted public launch:
- [ ] All applicable requirements in A–H and the children/operational sections have an evidence-backed status.
- [ ] Critical/high risks are resolved or have a documented, legally acceptable exception approved by the designated risk owner.
- [ ] Actual business practices match the policies and public claims.
- [ ] Applicable legal/regulatory duties have been assessed by qualified counsel and relevant specialists.
- [ ] Security, privacy, accessibility, data lifecycle, and operational recovery tests have passed at the required environments.
- [ ] Training/model-improvement behavior matches the legally approved default, notice, preference, eligibility, withdrawal, and provider arrangements.
- [ ] The operator explicitly approves release and the approval is recorded with date, scope, evidence, and unresolved limitations.

## 12. Owner acquisition and setup register

This section records things the operator may need to obtain, register, purchase, subscribe to, or arrange. **Do not purchase everything automatically.** First confirm the business model, legal entity, actual technical need, price, terms, and whether a free/open-source alternative is suitable.

| Item to arrange | When it is needed | Evidence to retain |
|---|---|---|
| Legal advice from a Nigerian technology/privacy/consumer-law lawyer | Before final policy approval and public commercial launch; earlier for material data/training decisions | Engagement, written advice/review, approved policy versions |
| Business-name or company registration through CAC | When the chosen operating structure and legal advice indicate it is appropriate/required | Registration certificate and official records |
| NDPC/DPCO assessment or services | If current law/rules and Smart BethG's classification require them | Written classification, filings, audit or DPCO records |
| Domain and business email | Before public-facing customer operations | Registration/renewal records, DNS and email security settings |
| Payment-provider merchant account | Before accepting payments | Merchant agreement, KYC, fee schedule, webhook/security setup |
| AI/hosting/storage/email/monitoring provider agreements | Before sending production data to each provider | Current terms, DPA where applicable, settings, subprocessor and transfer records |
| Commercial font/image/icon licences | Only for assets whose selected licence requires purchase or specific permission | Invoice, licence, attribution and asset inventory |
| Trademark search/registration advice | When the brand is ready for protection in selected markets | Search report, application and registration records |
| Security testing/penetration testing | Before unrestricted launch and after major security changes, proportionate to risk | Scope, report, remediation evidence and retest |
| Accessibility testing/support | Before public launch and for ongoing releases | Audit findings, test evidence and remediation records |
| Backup/storage/monitoring capacity | Before production data is accepted | Configuration, restore evidence, retention and alert tests |

### Individual first, company later — decision record required

- [ ] Compare operating initially as an individual/sole proprietor with registering a business name or limited company before commercial launch.
- [ ] Ask a qualified Nigerian lawyer/accountant about liability, tax, contracts, intellectual property ownership, banking/payment-provider onboarding, regulatory duties, and the cost/administration of each structure.
- [ ] Confirm whether the selected payment, hosting, AI, app-store, or enterprise providers require a registered business entity.
- [ ] If starting as an individual is legally and commercially suitable, make sure contracts, privacy notices, invoices and accounts accurately identify the individual operator; do not imply that an unregistered brand is a limited company.
- [ ] If a company is later formed, plan the transfer/assignment or licensing of domain, code, IP, customer contracts, provider accounts, data-controller responsibilities, and liabilities. Update policies, invoices, payment accounts, and customer notices where required.
- [ ] Do not assume a later company automatically inherits personal assets, contracts, licences, customer permissions, or data-processing authority.

## 13. Relationship to existing Smart BethG records

This document is the consolidated A–H criteria baseline requested by the product owner. It supplements, and must be reconciled with, existing records including:

- `docs/LEGAL_AND_PRIVACY_LAUNCH_CHECKLIST_2026-10-10.md` — earlier legal/privacy planning checklist.
- `README.md` — current product status and known launch limitations.
- `docs/PRODUCTION_LAUNCH_CHECKLIST_2026-10-26.md` and related production/security runbooks, if present on the active branch.
- The execution-platform architecture, threat model, quarantine intake, sandbox, and host-isolation release gates.

Known repository context at the time this file was created:
- The README says Smart BethG is in active development and is not cleared for unrestricted public launch.
- The README says training export remains disabled until consent controls exist.
- The earlier legal/privacy checklist calls for explicit, informed, recorded, revocable opt-in to training export.
- The product owner has now requested a different product direction: default-ON model-improvement contribution with a prominent notice and easy opt-out. This is recorded here as a proposed direction requiring legal assessment; it does not silently change the current code, enable the pipeline, or erase the earlier checklist. Reconcile and update the older documents only after the lawful product design is decided.
- User data export, Memory/personalization, and model-improvement/training contribution are separate features and must have separate descriptions and controls.
- The execution-platform security acceptance gate requires actual-host adversarial testing, demonstrated recovery, and operator approval.

Do not treat any item above as proof that the feature or control is already implemented. Inspect the active code, deployment, provider settings and operational practice before assigning a status.

## 14. Change history

| Date | Change |
|---|---|
| 2026-11-01 | Initial A–H business, privacy, legal, security, AI training, consumer, accessibility, licensing and acquisition criteria created. Recorded requested default-ON training direction as subject to legal review and implementation gates. |
