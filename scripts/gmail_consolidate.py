#!/usr/bin/env python3
"""
Gmail Label Consolidation + Inbox Archiver
==========================================
Consolidates 184 labels into 5, then archives the entire inbox.

Setup:
  1. Go to https://console.cloud.google.com
  2. Create a project > Enable Gmail API
  3. OAuth > Desktop app > Download credentials.json
  4. Place credentials.json in the same directory as this script
  5. pip install google-auth google-auth-oauthlib google-api-python-client
  6. python gmail_consolidate.py

The first run opens a browser for OAuth. Token is cached in token.pickle.
"""

import os
import ssl
import sys
import pickle
import time

try:
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("Missing dependencies. Run:")
    print("  pip install google-auth google-auth-oauthlib google-api-python-client")
    sys.exit(1)

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(SCRIPT_DIR, "token.pickle")
CREDS_PATH = os.path.join(SCRIPT_DIR, "credentials.json")

# ── New consolidated label IDs (already created in your Gmail) ──────────────
NEW_LABEL_IDS = {
    "Music":        "Label_186",
    "Finance":      "Label_187",
    "Personal":     "Label_188",
    "Work":         "Label_151",  # pre-existing "work" label
    "Logins & Tech":"Label_189",
}

# ── Old label ID → consolidated category ────────────────────────────────────
LABEL_MAP = {
    # MUSIC ──────────────────────────────────────────────────
    "Label_1":   "Music",   # 2011 plans/bookings/docs
    "Label_3":   "Music",   # ABLETON TIPS
    "Label_7":   "Music",   # Bad Apple Correspondence with Pegged
    "Label_8":   "Music",   # BAMFU
    "Label_11":  "Music",   # Beaux ARTS
    "Label_13":  "Music",   # BIO
    "Label_14":  "Music",   # BOOKINGS
    "Label_17":  "Music",   # CARLO
    "Label_20":  "Music",   # CHFM broadcast
    "Label_21":  "Music",   # claydo
    "Label_22":  "Music",   # CLAYDO ART PROJECT VID
    "Label_23":  "Music",   # CMAVS
    "Label_25":  "Music",   # Collaborations
    "Label_26":  "Music",   # COLONY FEATURES
    "Label_27":  "Music",   # CORE GROUP EMAILS
    "Label_30":  "Music",   # DEMF TICKETS
    "Label_32":  "Music",   # Disco Aliens
    "Label_33":  "Music",   # Disco Aliens and Moogonaughts 2011/12
    "Label_34":  "Music",   # DREKS FUCKUPPS
    "Label_47":  "Music",   # FLOWCAMP
    "Label_48":  "Music",   # Flyers
    "Label_49":  "Music",   # FORECASTLE
    "Label_51":  "Music",   # GFG FANPAGE
    "Label_54":  "Music",   # Groove Italio Dirty Monkey Records
    "Label_55":  "Music",   # HARVEY
    "Label_57":  "Music",   # IDEAS/EVENTS/PLOTS
    "Label_58":  "Music",   # Imagism Album Artwork
    "Label_59":  "Music",   # INDY MOJO
    "Label_63":  "Music",   # JOHN NAPIER TRACK TALK
    "Label_65":  "Music",   # LABEL PROMOS
    "Label_69":  "Music",   # LOGOS
    "Label_71":  "Music",   # Man Overboard
    "Label_72":  "Music",   # MATT @ INDY MOJO
    "Label_75":  "Music",   # miami
    "Label_76":  "Music",   # MIXES
    "Label_78":  "Music",   # MOB 2
    "Label_79":  "Music",   # Monkey Wrench
    "Label_80":  "Music",   # Moogonaughts
    "Label_81":  "Music",   # MOOGONAUGHTS PICTURES
    "Label_83":  "Music",   # MUSIC MAKING DEMOS
    "Label_84":  "Music",   # Music Website Newsletters
    "Label_85":  "Music",   # NAPIER RECORD LABEL
    "Label_86":  "Music",   # NATE FX
    "Label_89":  "Music",   # NCM
    "Label_93":  "Music",   # NEWSLETTER
    "Label_95":  "Music",   # NYE STL
    "Label_96":  "Music",   # ONE LITTLE FISHIE DOCS
    "Label_97":  "Music",   # ORIGINAL TRACKS
    "Label_101": "Music",   # PERSONAL PICKS
    "Label_103": "Music",   # PK - HARVEY - PRESS INFO
    "Label_104": "Music",   # PODCAST
    "Label_106": "Music",   # press kits
    "Label_107": "Music",   # PSYCHO
    "Label_108": "Music",   # QBAM
    "Label_110": "Music",   # RECORD LABEL EMAILS PROMOS
    "Label_112": "Music",   # REMIX COMPS
    "Label_115": "Music",   # ROOFTOP GLASSWORKS
    "Label_119": "Music",   # SLACKIN FEATURED ARTIST INFO and EMAILS
    "Label_120": "Music",   # SONICACADEMY
    "Label_121": "Music",   # SOUNDCLOUD
    "Label_122": "Music",   # SOUNDCLOUD & LABEL EMAILS
    "Label_123": "Music",   # Spoiled Rotten Records
    "Label_124": "Music",   # Spoiled Rotten Tracks
    "Label_127": "Music",   # studio time
    "Label_129": "Music",   # SUNDAY SLACKING PODCAST INFO
    "Label_130": "Music",   # Talent Attach - NATE FX
    "Label_132": "Music",   # TRACK WEBSITE ADMIN
    "Label_133": "Music",   # Tracks
    "Label_134": "Music",   # TRACKS AND STEMS
    "Label_135": "Music",   # TRACKS AND STEMS/TRACK LINKS
    "Label_136": "Music",   # Tracks from FRIENDS
    "Label_138": "Music",   # Tshirt Designs (merch)
    "Label_142": "Music",   # UNKLE FUNK
    "Label_144": "Music",   # VIlle billy mashups
    "Label_148": "Music",   # WISCONSIN SBASSED OUT 2
    "Label_150": "Music",   # WMC
    "Label_153": "Music",   # WREX ED EP
    "Label_154": "Music",   # WREX ED PROJECT
    "Label_155": "Music",   # WWD7
    "Label_158": "Music",   # ZACH HOBSON EMAILED SAMPLES
    "Label_160": "Music",   # dayton 2012
    "Label_164": "Music",   # VOCAL IDEAS
    "Label_165": "Music",   # 2011 plans/bookings
    "Label_167": "Music",   # Tracks/TUNE PREVIEW
    "Label_1727785354984583904": "Music",  # 1)Koke&friends
    "Label_3762709951286251336": "Music",  # 0) music
    "Label_4602006262340291897": "Music",  # 0) music/AUDIO ADVERT
    "Label_4330746127279408160": "Music",  # 1) Adverts
    "Label_6468313643773471569": "Music",  # 1) DJ info
    "Label_7057443232087846766": "Music",  # 1) Spacedome Specializations
    "Label_8116622258255224990": "Music",  # Spacedome Specialization
    "Label_4186110575378957473": "Music",  # BLAZE/BECK EMAILS
    "Label_8209620290013737849": "Music",  # JUMBIE ART STUDIO PROJECT
    "Label_8740440506505659783": "Music",  # 1) Mike & Frands

    # FINANCE ────────────────────────────────────────────────
    "Label_9":   "Finance",  # BANK ACCOUNTS
    "Label_12":  "Finance",  # BILLS
    "Label_24":  "Finance",  # CMAVS SHIRT ORDERS
    "Label_29":  "Finance",  # DEALS
    "Label_40":  "Finance",  # Equipment Receipts
    "Label_46":  "Finance",  # FLIGHT INFO
    "Label_53":  "Finance",  # GILT SHOPPING SALES
    "Label_60":  "Finance",  # INSURANCE
    "Label_70":  "Finance",  # MACBOOK PURCHASE
    "Label_74":  "Finance",  # MEGABUS
    "Label_82":  "Finance",  # Mortgage
    "Label_90":  "Finance",  # Netflix
    "Label_99":  "Finance",  # PAYCHECKS
    "Label_100": "Finance",  # PAYPAL
    "Label_105": "Finance",  # PODOMATIC RECEIPT
    "Label_109": "Finance",  # RECEIPTS
    "Label_114": "Finance",  # ROBERTSON REFINANCE
    "Label_117": "Finance",  # SHIRT ORDERS
    "Label_118": "Finance",  # SHOPPING
    "Label_125": "Finance",  # SPRINT
    "Label_126": "Finance",  # STICKERS
    "Label_131": "Finance",  # TAXES
    "Label_143": "Finance",  # UPS account
    "Label_152": "Finance",  # WORK BENEFITS
    "Label_8813349448290710702": "Finance",  # FORD MAVERICK

    # PERSONAL ───────────────────────────────────────────────
    "Label_15":  "Personal",  # CA
    "Label_16":  "Personal",  # Caboose
    "Label_18":  "Personal",  # Cassi
    "Label_19":  "Personal",  # cherylanna
    "Label_28":  "Personal",  # DAD BDAY
    "Label_31":  "Personal",  # Denise
    "Label_36":  "Personal",  # EMAIL CONTACTS
    "Label_37":  "Personal",  # EMILY GUELDA
    "Label_38":  "Personal",  # ENERGY and NUMEROLOGY
    "Label_39":  "Personal",  # Enterprise
    "Label_41":  "Personal",  # FACEBOOK UPDATES
    "Label_42":  "Personal",  # fantasy baseball
    "Label_43":  "Personal",  # fantasy baseball 2012
    "Label_44":  "Personal",  # FANTASY FOOTBALL
    "Label_45":  "Personal",  # FANTASY LEAGUE
    "Label_50":  "Personal",  # Friends *ONLY*
    "Label_56":  "Personal",  # healthcare
    "Label_61":  "Personal",  # Jennifer Mason
    "Label_64":  "Personal",  # Kayla
    "Label_66":  "Personal",  # LANNY BACKRUB
    "Label_67":  "Personal",  # links
    "Label_68":  "Personal",  # LISA WEDDING
    "Label_73":  "Personal",  # meg
    "Label_88":  "Personal",  # NBA FANTASY
    "Label_102": "Personal",  # PICS
    "Label_111": "Personal",  # Referral
    "Label_128": "Personal",  # STUFF
    "Label_140": "Personal",  # TWITTER
    "Label_149": "Personal",  # WISEMAN
    "Label_4311526521236154597": "Personal",  # r:/Parenting
    "Label_6717647934962047319": "Personal",  # sports
    "Label_7329380965344127626": "Personal",  # baby emails
    "Label_2411295242574469407": "Personal",  # 2) PHOTOS

    # WORK ───────────────────────────────────────────────────
    "Label_4":   "Work",  # Admin
    "Label_62":  "Work",  # JOB OP IN CHICAGO
    "Label_91":  "Work",  # NEW COLONY WEBSITE
    "Label_92":  "Work",  # New Colony Work
    "Label_113": "Work",  # RESUME
    "Label_6270940015533252560": "Work",  # JOB EMAILS
    "Label_7102780655159248484": "Work",  # 1) WORKTRU

    # LOGINS & TECH ──────────────────────────────────────────
    "Label_5":   "Logins & Tech",  # APPS and WEBSITE PASSWORDS
    "Label_6":   "Logins & Tech",  # ARTICLES and LINKS
    "Label_10":  "Logins & Tech",  # Beatport Login
    "Label_35":  "Logins & Tech",  # dropbox
    "Label_52":  "Logins & Tech",  # GFG SOCIAL MEDIA LOGIN INFO
    "Label_77":  "Logins & Tech",  # MLB.com login
    "Label_87":  "Logins & Tech",  # Native Instruments
    "Label_94":  "Logins & Tech",  # NMLS LOGIN INFO
    "Label_98":  "Logins & Tech",  # PASSWORDS
    "Label_137": "Logins & Tech",  # TRAKTOR
    "Label_139": "Logins & Tech",  # TUTORIALS and TIPS
    "Label_145": "Logins & Tech",  # WEBSITE ANALYTICS
    "Label_146": "Logins & Tech",  # WEBSITE HELP
    "Label_147": "Logins & Tech",  # WEBSITE LOGINS
    "Label_156": "Logins & Tech",  # www.djgfg.com
    "Label_157": "Logins & Tech",  # YOUTUBE ACCOUNT
    "Label_162": "Logins & Tech",  # APPLE STUFF
    "Label_168": "Logins & Tech",  # wrexed@sundayslackin.com
    "Label_169": "Logins & Tech",  # unklefunk@sundayslackin.com
}

# Labels to delete without re-labeling (junk/system/imap artifacts)
LABELS_DELETE_ONLY = [
    "Label_166",  # [Imap]/Outbox
    "Label_172",  # Sync Issues
    "Label_173",  # Sync Issues/Conflicts
    "Label_174",  # Sync Issues/Local Failures
    "Label_175",  # Sync Issues/Server Failures
    "Label_176",  # [Imap]/Sent
    "Label_177",  # Sent Messages
    "Label_178",  # HNGUnsubscribe
    "Label_180",  # Unroll.me
    "Label_181",  # [Imap]/Drafts
    "Label_182",  # cc-automated
    "Label_183",  # [Notion]
    "Label_171",  # contact script
    "Label_161",  # Notes
    "Label_179",  # Notes/USPS Confirmation Numbers
    "Label_184",  # Notes/CLAUDE OATH
    "Label_163",  # REVIEW (old)
]


def get_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDS_PATH):
                print(f"ERROR: credentials.json not found at {CREDS_PATH}")
                print("Download it from Google Cloud Console > APIs & Services > Credentials")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)
    return build("gmail", "v1", credentials=creds)


def get_all_threads_for_label(service, label_id):
    """Fetch all thread IDs for a given label, handling pagination."""
    threads = []
    page_token = None
    while True:
        kwargs = {"userId": "me", "labelIds": [label_id], "maxResults": 500}
        if page_token:
            kwargs["pageToken"] = page_token
        try:
            resp = service.users().threads().list(**kwargs).execute()
        except (HttpError, ssl.SSLError, OSError) as e:
            print(f"    [warn] list error for {label_id}: {e}")
            break
        threads.extend(t["id"] for t in resp.get("threads", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return threads


def modify_thread(service, thread_id, add_labels=None, remove_labels=None):
    """Apply/remove labels on a thread with simple retry."""
    body = {}
    if add_labels:
        body["addLabelIds"] = add_labels
    if remove_labels:
        body["removeLabelIds"] = remove_labels
    for attempt in range(4):
        try:
            service.users().threads().modify(
                userId="me", id=thread_id, body=body
            ).execute()
            return True
        except HttpError as e:
            if e.resp.status == 429 or e.resp.status >= 500:
                wait = 2 ** attempt
                print(f"    [retry {attempt+1}] rate limit, waiting {wait}s")
                time.sleep(wait)
            else:
                print(f"    [error] thread {thread_id}: {e}")
                return False
        except (ssl.SSLError, OSError) as e:
            wait = 2 ** attempt
            print(f"    [retry {attempt+1}] network error ({e}), waiting {wait}s")
            time.sleep(wait)
    return False


def process_label(service, old_label_id, new_category):
    """Re-label all threads under old_label_id and archive them."""
    new_label_id = NEW_LABEL_IDS[new_category]
    threads = get_all_threads_for_label(service, old_label_id)
    if not threads:
        return 0
    print(f"    {len(threads)} threads → {new_category}")
    ok = 0
    for tid in threads:
        success = modify_thread(
            service, tid,
            add_labels=[new_label_id],
            remove_labels=[old_label_id, "INBOX"],
        )
        if success:
            ok += 1
        time.sleep(0.05)  # stay under rate limit (~20 req/s)
    return ok


def archive_inbox(service):
    """Archive every remaining thread in INBOX (remove INBOX label)."""
    print("\n── Archiving remaining inbox threads ──")
    total = 0
    page_token = None
    while True:
        kwargs = {"userId": "me", "labelIds": ["INBOX"], "maxResults": 500}
        if page_token:
            kwargs["pageToken"] = page_token
        try:
            resp = service.users().threads().list(**kwargs).execute()
        except HttpError as e:
            print(f"  [error] Could not list inbox threads: {e}")
            break
        threads = resp.get("threads", [])
        if not threads:
            break
        print(f"  Archiving batch of {len(threads)}...")
        for t in threads:
            modify_thread(service, t["id"], remove_labels=["INBOX"])
            total += 1
            time.sleep(0.05)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    print(f"  Archived {total} additional inbox threads.")
    return total


def delete_label(service, label_id):
    for attempt in range(4):
        try:
            service.users().labels().delete(userId="me", id=label_id).execute()
            return True
        except HttpError as e:
            if e.resp.status in (429,) or e.resp.status >= 500:
                time.sleep(2 ** attempt)
            else:
                print(f"    [warn] could not delete {label_id}: {e}")
                return False
        except (ssl.SSLError, OSError) as e:
            print(f"    [retry {attempt+1}] network error ({e}), waiting {2**attempt}s")
            time.sleep(2 ** attempt)
    return False


def main():
    print("Gmail Consolidation Script")
    print("=" * 50)
    service = get_service()
    # Quick API connectivity check
    try:
        profile = service.users().getProfile(userId="me").execute()
        print(f"Authenticated OK — {profile.get('emailAddress')}\n")
    except HttpError as e:
        if e.resp.status == 403 and "has not been used" in str(e):
            import json, re
            m = re.search(r"project[= ](\d+)", str(e))
            proj = m.group(1) if m else "YOUR_PROJECT_ID"
            print("\nERROR: Gmail API is not enabled for your Google Cloud project.")
            print(f"\nFix: visit this URL and click Enable:")
            print(f"  https://console.developers.google.com/apis/api/gmail.googleapis.com/overview?project={proj}")
            print("\nThen wait 60 seconds and run this script again.")
        else:
            print(f"ERROR: {e}")
        sys.exit(1)

    # ── Phase 1: Re-label + archive by old label ──────────────────────────
    print("── Phase 1: Consolidating labels ──")
    total_moved = 0
    for old_id, category in LABEL_MAP.items():
        name_resp = None
        try:
            name_resp = service.users().labels().get(userId="me", id=old_id).execute()
            name = name_resp.get("name", old_id)
        except HttpError:
            name = old_id
        print(f"  [{old_id}] {name}")
        moved = process_label(service, old_id, category)
        total_moved += moved
        # delete the old label after processing
        delete_label(service, old_id)
        time.sleep(0.1)

    print(f"\nPhase 1 complete: {total_moved} threads re-labeled.\n")

    # ── Phase 2: Delete junk/system labels ───────────────────────────────
    print("── Phase 2: Deleting junk/system labels ──")
    for lid in LABELS_DELETE_ONLY:
        deleted = delete_label(service, lid)
        status = "deleted" if deleted else "skipped"
        print(f"  {lid}: {status}")

    # ── Phase 3: Archive everything left in INBOX ─────────────────────────
    archived = archive_inbox(service)

    print("\n" + "=" * 50)
    print("Done!")
    print(f"  Labels consolidated: {len(LABEL_MAP)}")
    print(f"  Threads re-labeled:  {total_moved}")
    print(f"  Inbox archived:      {archived}")
    print("\nYour Gmail now has 5 labels + NEEDS RESPONSE (red).")
    print("All emails still exist — search anytime to find them.")


if __name__ == "__main__":
    main()
