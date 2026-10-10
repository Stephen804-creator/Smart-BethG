# Smart BethG Privacy Policy — Draft

**Status:** Draft for product and legal review; not approved for public launch  
**Created:** 2026-10-10 UTC  
**Last reviewed:** 2026-10-10 UTC  
**Important:** This is a planning draft, not legal advice. It must be reconciled with the actual deployed data flows and reviewed by qualified counsel before publication.

## 1. Who operates the service
**Operator identity and contact:** To be completed before launch. The final policy must identify the legal entity/person responsible for the service and provide a working privacy contact.

## 2. Data the service may process
Depending on features used, Smart BethG may process:
- Account identifiers, authentication/session data, and account status.
- Prompts, responses, conversation history, and selected conversation metadata.
- Files uploaded by users, extracted text, knowledge chunks, memories, project/workflow data, generated artifacts, and task records.
- Provider/model selections, token usage, operational logs, security events, and rate-limit events.
- Data users choose to send to connected AI/search providers or other integrations.

The final policy must verify every category against the current schema, logs, provider integrations, and deployment configuration.

## 3. Purposes
Potential purposes include account operation, responding to user requests, storing user-requested history and memories, processing files, preventing abuse, securing the service, debugging reliability, measuring usage, and fulfilling legal obligations. Any use for model training or improvement must be disclosed separately and must require explicit opt-in consent.

## 4. AI providers and other recipients
A prompt or selected file content may be sent to the AI/search provider needed to fulfill a request. Before launch, publish a current list of providers, document what data each feature sends, link to provider policies, and explain any relevant provider retention or training settings. Do not claim that data stays exclusively within Smart BethG if an external provider receives it.

## 5. Training and model improvement
Conversation data must not be included in training exports by default. Training export remains disabled until the product implements informed opt-in consent, a recorded consent version/timestamp, withdrawal, and a way to exclude withdrawn users' eligible data from future exports. Admin authorization is not user consent. Withdrawal cannot reverse a model already trained on data; the final policy must clearly explain any such limitation before asking for consent.

## 6. Storage, security, and retention
The service should use production PostgreSQL, appropriate access controls, secret management, TLS in transit, provider-supported encryption at rest, independent backups, and tested restoration. The final policy must state actual retention periods for accounts, conversations, uploads, logs, backups, and deleted data. Do not promise encryption or deletion behavior until it has been verified in the deployed environment.

## 7. User choices and rights
The product should provide appropriate access, correction, export, deletion, and consent-withdrawal controls. Exact rights, timelines, and lawful bases depend on applicable law and must be confirmed for target jurisdictions. The final policy must provide a clear way to exercise these rights and explain identity verification.

## 8. Cookies and sessions
Smart BethG uses a signed session cookie for authentication. The final policy must explain the cookie's purpose, lifetime, security attributes, and any other cookies or analytics actually deployed. Do not claim analytics are used unless they are enabled.

## 9. Children and age requirements
The operator must decide and legally review age eligibility, parental-consent requirements, and controls for children before public launch. This draft does not set a final age threshold.

## 10. International transfers and legal requests
The final policy must explain hosting regions, external-provider processing locations, relevant transfer safeguards, and how legally valid requests are handled.

## 11. Changes and contact
Add a policy version, effective date, change log, and working privacy contact before publication.

## Publication checklist
- [ ] Map every database table, file-storage path, log, cookie, provider call, and backup.
- [ ] Decide and document retention/deletion periods.
- [ ] Implement user data export and deletion, including files, chunks, memories, conversations, and generated artifacts.
- [ ] Implement training opt-in, consent records, and withdrawal.
- [ ] Identify subprocessors and provider data-handling terms.
- [ ] Verify deployed TLS, access control, encryption, backups, and restore procedures.
- [ ] Have counsel review requirements in target jurisdictions.
- [ ] Publish a versioned policy and link it from registration and account settings.
