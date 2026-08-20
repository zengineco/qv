# QV — QikVote v0.5.0 ("Ballot Box")

**Live ballots. One tap, one vote, live needle. The ballot comes to you.**

A QV ballot is a yes/no (or this/that) question anyone can vote on in one tap —
no account, no app required. The result is a live needle that moves the moment
anyone anywhere votes. Subscribe to channels (#food, #politics, #ohio, whatever)
and new ballots land in your notifications — on Chrome, Edge, Firefox, and
Android you vote **from the notification's buttons without opening anything**.

An F-Keys product. Home: qv.f-keys.com

## What's in this folder

| File | What it is |
|---|---|
| `index.html` | The feed — vote on ballots in place, filter by channel, page through; plus notifications opt-in and "apply to be a creator" |
| `b.html?id=…` | A ballot — vote, change your vote, watch the live needle, copy link/embed |
| `e.html?id=…` | Compact ballot used inside embeds (iframes) |
| `qv.js` | The embed loader — one script tag puts a live ballot on any website |
| `sw.js` | Service worker — shows push notifications and records votes from their buttons |
| `creator.html` | Creator terminal — publish/close ballots, watch tallies (needs a creator key) |
| `manifest.json`, `icon.svg` | PWA bits (required for iPhone notifications via Add to Home Screen) |
| `pollcreator.py` | Seeds ballots in bulk from `seeds/*.json` — silent by default |
| `seeds/*.json` | Curated question sets by channel (food, vision, math, ciphers, games, general) |

Surfaces a ballot reaches: the web page, any site via one script tag, a browser
notification with vote buttons, and a Telegram channel post.

## Embed a ballot anywhere

```html
<script src="https://qv.f-keys.com/qv.js" data-ballot="BALLOT_ID" async></script>
```

## Question reconciliation (v0.2.0)

Two people asking the same question in two ballots splits the tally and makes both
answers worse. Before a ballot is created, QV reconciles the question against every
live ballot:

- **Exact match** (after lowercasing, stripping punctuation and leading filler like
  "should we" / "do you think") → creation is blocked and the live ballot is offered
  instead, with its current vote count.
- **Near match** (trigram word-overlap ≥ 0.55) → related ballots are shown as a
  warning; the creator can publish anyway.

Word order is never sorted away. *"Is coffee better than tea"* and *"Is tea better
than coffee"* contain identical words but have opposite answers, so they are flagged
as related and never auto-merged — the exact-match tier compares the ordered string,
and the overlap score is labeled as word overlap, not meaning.

## Telegram channel adapter (v0.3.0)

Publishing a ballot also posts it to a Telegram channel with two vote buttons.
**One API call reaches every subscriber** — a channel has no subscriber cap, and
posts notify with sound by default, so this sidesteps the ~30 messages/second
broadcast limit that makes direct-message fanout useless (100,000 DMs takes about
56 minutes; one channel post takes one call).

A tap votes through the *same* `qv_cast_vote` function the web uses, so a ballot
has one tally no matter where the vote came from. The voter gets a private toast
with the live split; nobody else sees who voted. The public post redraws its
needle at most once every 5 seconds, because Telegram throttles edits to roughly
one per second per chat and a vote burst would otherwise hit the limit.

Telegram user identities are hashed into their own namespace (`tg:<id>`), so the
same person voting on the web and in Telegram counts twice. That is a deliberate,
documented limit — linking them would require asking people to connect accounts,
which costs the anonymity that is the point.

**Honest limitation:** Telegram notifications cannot carry buttons — the push
payload format has no field for them. So Telegram is *tap notification → chat
opens → tap vote*: two taps. True one-tap-from-the-notification voting exists only
on web push (Chrome/Edge/Firefox desktop, Chrome Android), which QV already has.

### Setup (one time)

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token.
2. Create a Telegram channel, then add the bot as an **administrator** with
   "Post Messages" and "Edit Messages of Others" permission.
3. Store the token and channel in `qv_config` (`telegram_bot_token`,
   `telegram_channel` — the channel as `@yourchannel`).
4. Point Telegram at the webhook, including the secret from `qv_config`:

```
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://ihclxurachkewtgnrldc.supabase.co/functions/v1/qv-telegram&secret_token=<SECRET>&allowed_updates=["callback_query"]
```

The webhook **fails closed** — if the secret is missing from config, the endpoint
refuses every update rather than trusting an unauthenticated caller.

## The feed

The home page is the product. Ballots are **votable in the list** — tap a side,
the needle moves, keep scrolling. Clicking into a page for every ballot is
filing, not voting. Channel chips filter the board, and paging loads 25 at a
time.

## Seeding ballots in bulk

A ballot platform with nothing to vote on is a dead page. `pollcreator.py` fills
it from curated question sets — no dependencies, standard library only.

```bash
python pollcreator.py --dry-run          # see everything that would publish
python pollcreator.py food               # publish one set
python pollcreator.py                    # publish every set
```

The creator key comes from `QV_CREATOR_KEY` (never commit it):

```
PowerShell:  $env:QV_CREATOR_KEY = 'qvc_...'
bash:        export QV_CREATOR_KEY=qvc_...
```

**Seeding is silent.** Publishing normally fires a push notification to every
subscriber of that channel — so creating 40 ballots at once would fire 40
notifications at every person. The seeder passes `notify:false` and
`telegram:false` unless you explicitly pass `--notify` / `--telegram`.

Re-running a seed file is safe: question reconciliation returns each ballot as a
duplicate and points at the live one rather than splitting its tally.

Adding your own is one JSON object:

```json
{ "question": "Spaghetti or rigatoni?", "label_a": "SPAGHETTI",
  "label_b": "RIGATONI", "channel": "food", "detail": "optional context" }
```

## How trust works (honest by design)

- Voting is anonymous. Your choice is stored on your device; the server keeps a
  salted hash, never an identity.
- One vote per browser, enforced by a database constraint — changing your vote
  updates the same row, it never adds one.
- Every result carries its label: **casual integrity, self-selected sample**.
  QV never claims a ballot is a scientific poll.
- Anti-stuffing: votes flow through one server function, per-network caps apply,
  and counts are never taken from the browser's word.

## Backend (Supabase project `ihclxurachkewtgnrldc`)

- Tables (all RLS): `qv_polls` (public read, `question_norm` generated column + GIN trigram index), `qv_votes`, `qv_push_subs`,
  `qv_creators`, `qv_creator_apps`, `qv_config` (service-role only)
- RPC `qv_find_similar` — question reconciliation (service role only)
- RPC `qv_cast_vote` — atomic vote/change + tally + realtime broadcast; callable
  by service role only
- Edge functions: `qv-vote`, `qv-subscribe`, `qv-publish` (creator key gated,
  fans out to web push + Telegram), `qv-apply`, `qv-telegram` (webhook)
- Live needle = Supabase Realtime **broadcast** (topic `poll:{id}`, event
  `tally`) sent from inside the vote transaction — no per-vote row streaming

## Platform truth for notification voting

| Surface | One-tap vote from notification? |
|---|---|
| Chrome / Edge desktop | ✅ buttons on the notification |
| Android Chrome | ✅ buttons on the notification |
| Firefox 152+ | ✅ |
| iPhone (Safari web push) | ⚠️ requires Add to Home Screen; tap opens the ballot (Apple allows no buttons on web notifications) |
| iOS native app | future — buttons work there (behind long-press) |

## Planned Features

- Cloudflare Turnstile on first vote per device (raise the bot cost, keep zero login)
- OG result cards per ballot (needs an edge renderer; static hosting can't do per-URL meta)
- Creator application review flow in the terminal (approve → key issued)
- Verified-channel tiers and integrity labels beyond "casual"
- Dedicated Supabase project + VAPID keys in function secrets (currently in `qv_config`, service-role locked)
- npm package for the embed (`qv-embed`) + GitHub-discoverable widget repo

---

QV v0.5.0 · www.f-keys.com | © 2026 F-Keys™
