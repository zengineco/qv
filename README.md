# QV — QikVote v0.1.0 ("Ballot Box")

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
| `index.html` | Home — open ballots, channel notifications opt-in, "apply to be a creator" |
| `b.html?id=…` | A ballot — vote, change your vote, watch the live needle, copy link/embed |
| `e.html?id=…` | Compact ballot used inside embeds (iframes) |
| `qv.js` | The embed loader — one script tag puts a live ballot on any website |
| `sw.js` | Service worker — shows push notifications and records votes from their buttons |
| `creator.html` | Creator terminal — publish/close ballots, watch tallies (needs a creator key) |
| `manifest.json`, `icon.svg` | PWA bits (required for iPhone notifications via Add to Home Screen) |

## Embed a ballot anywhere

```html
<script src="https://qv.f-keys.com/qv.js" data-ballot="BALLOT_ID" async></script>
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

- Tables (all RLS): `qv_polls` (public read), `qv_votes`, `qv_push_subs`,
  `qv_creators`, `qv_creator_apps`, `qv_config` (service-role only)
- RPC `qv_cast_vote` — atomic vote/change + tally + realtime broadcast; callable
  by service role only
- Edge functions: `qv-vote`, `qv-subscribe`, `qv-publish` (creator key gated,
  sends web push), `qv-apply`
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

QV v0.1.0 · www.f-keys.com | © 2026 F-Keys™
