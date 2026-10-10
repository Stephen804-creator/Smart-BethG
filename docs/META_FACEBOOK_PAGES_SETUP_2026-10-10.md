# Facebook Pages Connector Setup

**Created:** 2026-10-10 UTC  
**Last updated:** 2026-10-10 UTC  
**Status:** Setup instructions; actual publishing must be tested against an operator-owned Meta app and test Page.

## What this connector currently supports

- OAuth authorization for Facebook Page access.
- Discovery of eligible Pages that the signed-in user can manage.
- Encrypted storage of Page access tokens.
- Explicit per-Page activation and disconnection.
- Text-only Facebook Page feed posts through the Meta Graph API.
- Durable publication jobs handled by the separate social publisher worker.

It does not currently publish Instagram content, videos, images, Reels, stories, comments, DMs, or other account actions. A successful OAuth connection does not mean Meta has approved the app for general public use.

## Create and configure the Meta app

1. The operator must create and own the app in Meta for Developers and select the login/product configuration required by the official Meta documentation.
2. Configure the exact callback URL ending in /connectors/meta/callback. It must match the registered redirect URI exactly.
3. Request only the permissions needed for the implemented Page workflow: pages_show_list, pages_read_engagement, and pages_manage_posts.
4. Add test users/testers and a test Facebook Page while the app is in development mode.
5. Complete Meta's current app review/business verification requirements before enabling public users. Do not assume a successful test with app-role users proves general-user access.
6. Confirm the current Graph API version and publishing requirements in Meta's official documentation before deployment.

Official references:
- Meta's Instagram API documentation in the official Meta Postman workspace: https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api
- Meta Graph API Page reference: https://developers.facebook.com/docs/graph-api/reference/page/
- Meta permissions documentation: https://developers.facebook.com/docs/permissions/
- Meta Facebook Login documentation: https://developers.facebook.com/docs/facebook-login/

## Required server environment

Set these in the deployment secret manager/environment; never commit them:

- SMART_BETHG_META_APP_ID — Meta app ID.
- SMART_BETHG_META_APP_SECRET — Meta app secret.
- SMART_BETHG_META_REDIRECT_URI — full HTTPS callback URL registered in the Meta app.
- SMART_BETHG_META_API_VERSION — reviewed Graph API version, for example v26.0 only if that is the version currently supported by the app.
- SMART_BETHG_TOKEN_ENCRYPTION_KEY — a valid Fernet key used to encrypt tokens stored in PostgreSQL.
- SMART_BETHG_META_PUBLISHING_ENABLED — leave unset/false during development; set to true only after the app, permission review, test account, deployment TLS, and worker have been verified.

Generate a Fernet key in a secure environment with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Copy it directly to the secret manager. Do not print it into chat, commit it, or place it in a public deployment file. Keep a securely backed-up copy: losing the key makes stored tokens undecryptable. Rotation is not yet automated; plan a controlled credential reconnection/re-encryption procedure before rotating the key.

## Connection and publication flow

1. The user signs in to Smart BethG and chooses Connect Facebook Pages.
2. Smart BethG stores a random OAuth state in the signed session and redirects to Meta.
3. The callback verifies state and user identity, exchanges the code, checks the granted permissions, and discovers eligible Pages.
4. Page tokens are encrypted in the credential vault. Page rows start as pending.
5. The user activates only the Pages they intend Smart BethG to use. The server decrypts the credential and verifies the Page identity with Meta.
6. The user creates a campaign, generates a content plan, and reviews each post or explicitly authorizes the bounded campaign for automatic publishing.
7. Campaign activation is blocked unless the corresponding publisher adapter and active Page connection are configured.
8. Run the separate worker process using python -m workers.social_publisher. Monitor logs and database job states; never treat a queued job as a published post.
9. Test successful publication, permission revocation, token invalidation, page removal, rate limiting, API errors, and timeouts. Unknown provider outcomes are marked indeterminate and must be reconciled before retrying.

## Security notes

- Access tokens are encrypted at rest; the social account table stores only a vault reference.
- The callback does not log provider tokens or exception bodies.
- Disconnecting blocks pending jobs and revokes the local vault credential. Users should also revoke the app from their Meta account settings when they want to withdraw the provider grant completely.
- The Meta API does not give this text-post endpoint a general idempotency guarantee. A timeout can mean a post succeeded even if the worker did not receive the ID. The worker therefore marks unknown outcomes indeterminate rather than blindly retrying.
- Keep the worker under process supervision, run one or more replicas only with PostgreSQL and shared artifact storage, and alert on indeterminate/blocked jobs.
