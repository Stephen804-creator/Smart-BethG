# Smart BethG age eligibility policy

**Decision date:** 2026-11-01  
**Initial-release minimum age:** 18

Smart BethG's initial release is for adults aged 18 and older. People under 18 are not eligible to create or use an account. This is a product eligibility restriction, not an age rating such as 13+ or 16+.

## Application behaviour

- The registration screen requires an explicit confirmation that the registrant is at least 18.
- The server records the age declaration together with the accepted Terms and Privacy Policy versions.
- The current policy version is required at login and on protected application/API routes.
- Existing accounts with older policy acceptance are placed in a restricted session and must review and accept the current policies before accessing protected features.
- Google sign-in is subject to the same policy gate; it does not bypass the age and policy requirements.
- Accounts may be restricted or suspended where there is credible evidence that the age requirement is not met.

## Important verification limitation

The current registration flow records a user-declared age confirmation. It does **not** independently establish a person's identity or age. A checkbox, email address, Google account, or self-entered date of birth must not be described as independent age verification.

Before unrestricted public launch, the product owner must select and integrate an appropriate age-assurance method, assess its privacy and data-minimisation implications, and test the process end to end. The verification provider must be compatible with the platform's jurisdictions and must not conflict with the terms of the AI model/API providers used by Smart BethG. Do not collect or retain identity documents directly unless a documented legal and security assessment justifies doing so.

## AI provider eligibility

Provider rules apply independently of Smart BethG's own age policy. A provider's consumer application age limit does not establish permission to embed that provider's API in a product used by the same age group. Before launch, maintain a provider-by-provider record of minimum age, permitted application audience, safety requirements, data-processing terms, and any verification obligations. If a provider does not permit the intended use, do not route requests from Smart BethG to that provider.

## Release gate

This implementation establishes an 18+ product rule and server-side policy re-acceptance. It is not a legal compliance certificate or an independent age-verification system. Public launch remains subject to age-assurance integration, provider-term review, and qualified legal/privacy review.
