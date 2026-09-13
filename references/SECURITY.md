# Security and Compliance Boundaries

## Public does not mean unrestricted

Before bulk collection, consider:

- service terms,
- robots directives where relevant,
- explicit rate limits,
- privacy expectations,
- jurisdiction,
- data licensing,
- downstream reuse restrictions.

## Credentials

Never print or persist credentials, API keys, cookies, or session tokens in research output.

For authenticated browsing:

- use a user-authorized session;
- keep credentials within the tool's secret/session mechanism;
- minimize access scope;
- do not export cookies into notes or datasets.

## Access controls

Do not:

- defeat authentication,
- exploit access-control bugs,
- bypass paywalls,
- use credential stuffing,
- circumvent a CAPTCHA solely to evade the site's access policy,
- scrape private profiles or private data without authorization.

## Rate limiting

On 429 or throttling:

- reduce concurrency;
- respect Retry-After when available;
- cache retrieved pages;
- use official bulk/export endpoints;
- schedule rather than hammer.

## Personal data

Collect only what is necessary for the user's legitimate task.

Avoid bulk harvesting of sensitive personal information.

## Network-derived clients

If a browser reveals structured requests:

- restrict use to the user's authorized scope;
- do not assume private endpoints are public APIs;
- preserve CSRF/auth boundaries;
- do not replay secrets into logs;
- validate terms/rate limits;
- prefer read-only operations unless the user explicitly asks for an authorized write action.
