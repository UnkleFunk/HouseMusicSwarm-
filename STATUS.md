# Current Status — READ THIS FIRST (Local Claude Code Session)

## The Mission
Get unklefunk.music showing the real Unkle Funk artist hub (dark gold theme,
equalizer animation, SoundCloud/Spotify players, Sunday Slackin' podcast).
All the code is built and deployed — the site is BLOCKED by a Hostinger
server config issue, not a code issue.

## What's Built & Working
- `website/index.html` — full single-page artist hub, all content real
- `website/style.css` — dark/gold theme, vinyl animation, responsive
- `website/main.js` — canvas equalizer, mobile nav, scroll reveal
- `website/.htaccess` — DirectoryIndex + gzip + caching headers
- GitHub Actions deploy: `.github/workflows/deploy-hostinger.yml`
  - Triggers on push to `main` with `paths: ["website/**"]`
  - SCP uploads files to `~/public_html/` on Hostinger
  - Has been successfully deploying (deploy #2 confirmed files on server)

## The Problem
unklefunk.music shows Hostinger's "You Are All Set to Go!" placeholder
(guy on a bike). This is a SERVER-LEVEL block — Hostinger intercepts
traffic before it reaches public_html. Our files are probably in
`~/public_html/` but unconfirmed.

### History of what happened:
1. WordPress was installed on the domain (user never set it up intentionally)
2. WordPress was intercepting all traffic → serving a stock template
3. User deleted WordPress via hPanel → Kodee confirmed deletion
4. Now Hostinger shows their "empty site" placeholder
5. Our deploy has run multiple times since but placeholder persists
6. File Manager shows `public_html/` folder exists but we never confirmed
   what's inside it

## What Needs to Happen
SSH into the server and:
1. Check what's in `~/public_html/` 
2. If our files are there (`index.html`, `style.css`, `main.js`, `.htaccess`) →
   the issue is Hostinger routing. May need to configure domain to serve
   static files, or check if there's a server-level redirect overriding things.
3. If public_html is empty → manually upload files or re-run the deploy.
4. Check `.htaccess` is in place and readable.
5. Possibly check Apache/nginx config or Hostinger-specific config files.

## Server Credentials
- Host: 195.179.239.223
- SSH Port: 65002
- Username: in GitHub Secret `HOSTINGER_SSH_USER`
- Password: in GitHub Secret `HOSTINGER_SSH_PASS`
- Web root: `~/public_html/`

⚠️  The actual credentials are in GitHub Secrets, not stored here.
If you have SSH access locally, the user needs to provide the
username/password, OR you can trigger the GitHub Actions workflow
to deploy (it has the secrets).

## GitHub Actions — How to Trigger Deploy
The workflow has `workflow_dispatch` — you can trigger it manually:
```
gh workflow run deploy-hostinger.yml
```
Or push any change to a `website/**` file on `main`.

## What the Site Should Look Like
- Black background (#09090b), gold (#c9a84c) accents
- Hero: large "UNKLE FUNK" text with animated equalizer bars behind it
- About: spinning vinyl record, bio, stats (16+ years, 2010 podcast, etc.)
- Podcast: Sunday Slackin' embedded Apple Podcasts player (id=406329520)
- Music: SoundCloud embed (unklefunkssounds) + Spotify embed (artist 3OIZINZmZ2lKSYVsmSmrnH)
- Releases: 5 release cards + chart links to Traxsource and Beatport
- Connect: 6 platform cards (SoundCloud, Spotify, Beatport, Apple Podcasts, Facebook, Discogs)

## Repo Structure (relevant)
```
HouseMusicSwarm-/
├── website/              ← the static site
│   ├── index.html
│   ├── style.css
│   ├── main.js
│   └── .htaccess
├── .github/workflows/
│   ├── deploy-hostinger.yml   ← main deploy
│   └── diagnose.yml           ← run this to SSH in and check server state
├── swarm.py              ← the Agency Swarm (separate from website)
├── orchestrator/
├── virtual_assistant/
├── deep_research/
└── ...other swarm agents
```

## Quick Win: Run the Diagnose Workflow
`.github/workflows/diagnose.yml` SSHes in and shows the state of `public_html`.
Running it will immediately tell you if the files are there.
```
gh workflow run diagnose.yml
```
Then check the Actions log.

## Branch
All work is on `main`. The feature branch `claude/build-music-artist-hub-OZuwW`
is stale — ignore it.

## Context
This has been a ~14 hour session across mobile + cloud Claude Code.
The user (Unkle Funk / Glenn) is a Chicago house music DJ/producer.
The swarm is a full OpenSwarm fork (Agency Swarm framework) that is
SEPARATE from the website — the website just lives in the `website/` folder.
See VISION.md for the full music curation swarm roadmap.
