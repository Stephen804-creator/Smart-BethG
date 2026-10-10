# Smart BethG Legal and Privacy Review Checklist

**Created:** 2026-10-10 20:30 UTC  
**Last updated:** 2026-10-10 20:30 UTC  
**Status:** Internal checklist only — not legal advice, not a compliance certificate, and not a legal approval.

## What must happen before publication

Smart BethG's Terms of Service and Privacy Policy drafts are starting points for a qualified reviewer. Do not simply paste the drafts into the live website and call them approved. The legal text must describe the real deployed system and the actual company/operator.

### 1. Confirm the operator
- [ ] Decide whether Smart BethG is operated by an individual, registered business name, or incorporated company.
- [ ] Use the exact legal name, contact address, support email, and privacy contact that users can actually reach.
- [ ] Do not claim the product is operated by a company until that entity exists and the details are accurate.

**Separate the company-registration question from the legal-policy question.** If you choose to register a business name or incorporate a company in Nigeria, the Corporate Affairs Commission (CAC) is the official business registry. CAC registration does not approve your Terms of Service or Privacy Policy, and legal-policy review does not itself register your business. See the [CAC overview](https://www.cac.gov.ng/about), [business-name registration](https://www.cac.gov.ng/services/business-name), and [company-registration process](https://www.cac.gov.ng/services/company-registration).

### 2. Prepare a data map with the developer
Document every category of personal data, where it comes from, where it is stored, who can access it, how long it is retained, and where it is sent. Include accounts, session/version data, prompts, conversations, uploads, generated files, memory, knowledge chunks, projects, missions, audit/security logs, provider usage, backups, and third-party AI/search providers. Identify data that is sent to a third-party provider to answer a prompt.

### 3. Ask a qualified Nigerian technology/privacy lawyer to review both drafts
Request a written review covering:
- Nigeria Data Protection Act 2023 and applicable NDPC guidance.
- Contract terms for an AI service, acceptable-use policy, user content, generated output, third-party providers, disclaimers, liability, suspension, complaints, disputes, and termination.
- Privacy lawful bases, notices, data-subject rights, retention, account deletion/export, international transfers, security incidents/breach handling, cookies/sessions, and any children/age policy.
- Whether the operator's actual processing activities trigger registration, audit, DPCO engagement, or other obligations under current NDPC rules.
- Whether target users outside Nigeria require additional terms, privacy disclosures, or local-law review.

Ask the lawyer to identify any facts that the operator must decide rather than inventing them in legal language. Agree the review scope and fee before work begins.

### 4. Check whether a licensed Data Protection Compliance Organisation (DPCO) is needed
The Nigeria Data Protection Commission (NDPC) is the regulator, not a general document-approval service that stamps every website's Terms and Privacy Policy. The NDPC publishes the Nigeria Data Protection Act, guidance, registration information, and lists of licensed DPCOs. Its current guidance identifies categories of data controllers/processors of major importance, including certain data-volume and ICT-service criteria; whether Smart BethG falls into a category depends on its actual processing and must be checked against current NDPC guidance. Ask qualified counsel or a licensed DPCO whether Smart BethG's scale and processing activities require DPCO support, audit, registration, or other formal compliance steps. Do not assume every early-stage app automatically requires the same registration; verify the applicable category and current rules.

Official starting points:
- NDPC official website: https://ndpc.gov.ng/
- NDPC resources and NDP Act: https://ndpc.gov.ng/resources/
- NDPC FAQ: https://ndpc.gov.ng/faqs/
- NDP Act page: https://www.ndpc.gov.ng/ndp-act-2023/

### 5. Implement product controls that make the policy true
- [ ] Keep public registration closed until security/privacy release gates pass.
- [ ] Keep training export disabled until informed, opt-in, recorded and revocable consent is implemented and tested.
- [ ] Add versioned acceptance records for the exact Terms/Privacy versions, with timestamps, for account creation or other appropriate points.
- [ ] Add account data export and deletion workflows; document backup-retention behavior and any exceptions.
- [ ] Provide a working privacy contact and a process to receive, verify, track, and answer rights requests.
- [ ] Inventory subprocessors/providers and link to their official privacy terms.
- [ ] Ensure logs do not contain passwords, API keys, raw prompts beyond documented need, or unnecessary sensitive data.
- [ ] Test that actual cookie/session, security, storage, and retention behavior matches the published statements.

### 6. Approve and publish a version
- [ ] Lawyer provides written comments or a final reviewed version.
- [ ] Operator resolves comments and confirms every factual statement matches the implementation.
- [ ] Record reviewer, version, review date, effective date, and operator approval in the change history.
- [ ] Publish the final documents at stable routes such as `/terms` and `/privacy`, link them from registration and account settings, and retain old versions needed to explain past acceptance.
- [ ] Re-review after material changes to providers, data collection, training use, hosting regions, retention, or product functionality.

## What does not count as legal approval

- Copying a generic template from another website.
- Asking an AI system to draft the document.
- Adding the draft to GitHub or linking it from the footer.
- Receiving a green CI/security scan.
- Receiving a regulator's general guidance page.
- Having a lawyer review the text without reconciling it against the real data flows and product behavior.

**Release gate:** The documents remain drafts until qualified review is completed, operator details are verified, product controls exist, and the final version is approved for publication.
