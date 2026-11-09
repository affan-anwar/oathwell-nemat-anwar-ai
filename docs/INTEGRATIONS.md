# Integration inventory
Status words: **Implemented** = code exists. **Mock-tested** = tested only against a fake server in this project. **Verified with provider** = tested with a real account (none yet). Provider rules change: check the linked documentation before building.

## Implemented in code (all Mock-tested, none Verified with provider)
| Integration | Official docs | Credential (server environment, never in the browser) | How it is used | How to verify |
|---|---|---|---|---|
| OpenAI | https://platform.openai.com/docs/api-reference | `OPENAI_API_KEY` | `GET /v1/models` (model list) and `POST /v1/responses` (text) | Owner Console > AI Providers > Test connection. Shows Connected only if the provider answered |
| Anthropic Claude | https://docs.anthropic.com/en/api | `ANTHROPIC_API_KEY` | `GET /v1/models`, `POST /v1/messages` | Same |
| Google Gemini | https://ai.google.dev/api | `GEMINI_API_KEY` | `GET /v1beta/models`, `POST /v1beta/models/{model}:generateContent` (key sent in a header) | Same |
| WordPress | https://developer.wordpress.org/rest-api/ | Application Password stored encrypted per integration | `POST /wp-json/wp/v2/posts` with a deterministic slug, slug lookup to reconcile | Integrations > Test connection |

Model IDs differ between accounts. The app never assumes one: you run the test, pick from the list your key returns, and only then can it be saved. Names such as "GPT-6.1 Sol" or "GPT-6 Luna" are not hard-coded because their availability for your account is unknown.
Optional prices for cost estimates: `AI_PRICES={"openai:<model-id>": {"in": <USD per million input tokens>, "out": <USD per million output tokens>}}`.

## Not implemented (setup guide only; do not treat as working)
Common to all: each needs a developer app, OAuth 2.0 consent from the account owner, and (for most) provider review or business verification before posting to other people's accounts. Redirect URI for local testing would be `http://localhost:5173/oauth/<provider>/callback` (not built yet). Webhooks, quotas and scopes below must be confirmed in each provider's current documentation.
| Channel | Official API | Typical requirement (verify) |
|---|---|---|
| LinkedIn | LinkedIn Marketing / Community Management APIs | App with approved products; member or organisation posting scopes; review |
| Instagram and Facebook | Meta Graph API (Instagram Graph API, Pages API) | Business account linked to a Facebook Page; Meta app review and business verification for publishing scopes |
| X (Twitter) | X API v2 | Paid access tier for posting; OAuth 2.0 |
| YouTube | YouTube Data API v3 | Google Cloud project, OAuth consent, daily quota units; uploads may need an audit |
| TikTok | TikTok Content Posting API | App review; unaudited apps may post only as private |
| WhatsApp / WhatsApp Business | WhatsApp Business Platform (Cloud API) | Business verification, approved message templates, user opt-in; unsolicited messaging is not allowed |
| Snapchat | Snap Marketing API / Public Profile API | Business account and approval; features are limited |
| Google Analytics / Search Console | Analytics Data API, Search Console API | OAuth read-only scopes |
| Job boards (Naukri, Internshala, LinkedIn Jobs, Indeed, Glassdoor, etc.) | Few offer public APIs | Use official feeds, partner APIs or manual import. Do not scrape against site terms |

Until a real account is connected, these show "Not available yet" in the app and nothing is simulated.
