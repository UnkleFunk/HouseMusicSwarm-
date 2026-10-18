# Hazel setup

[Hazel](https://www.noodlesoft.com/) watches a folder and runs a rule on each new file. Here it hands every new photo to the Resale app, which adds it to an item, files the original away, and queues the photo read.

You can use Hazel, the built-in watcher (`python -m resale_app watch`), or both. They share the same ingest code, and a photo that arrives twice is recognised by its content and ignored.

## One-time setup

1. Make the drop folder: `mkdir -p ~/ResaleDrop`. (To use another path, set `RESALE_DROP_DIR` in `resale_app/.env`.)
2. `chmod +x resale_app/scripts/hazel_ingest.sh`. If the repo isn't at `~/HouseMusicSwarm-` or the virtualenv isn't `.venv-resale`, edit the two variables at the top of the script.
3. Keep the web app running (`python -m resale_app serve`). Its worker does the photo reading. Without it, run `python -m resale_app analyze` when you want the queue processed.

The web app, Hazel and the watcher must all use the same `RESALE_HOME`. The default (`resale_app/data/` inside the checkout) is shared automatically.

## The rule

| Setting | Value |
|---|---|
| Watched folder | `~/ResaleDrop` |
| Rule name | `Resale: ingest photos` |
| Match | **All** of the following |
| Condition 1 | **Kind** **is** **Image** |
| Condition 2 | **Name** **does not start with** `.` |
| Condition 3 (optional) | **Date Last Modified** **is not in the last** 10 seconds. This stops Hazel grabbing a file AirDrop is still writing. If your Hazel only offers minutes, use 1 minute. |
| Action | **Run shell script** (embedded, shell `/bin/zsh`) |

`hazel_ingest.sh` itself is plain `/bin/sh`. The embedded script is one line:

```zsh
"$HOME/HouseMusicSwarm-/resale_app/scripts/hazel_ingest.sh" "$1"
```

**Do not add a Move, Rename or Sort action.** Ingest moves the file itself, to `~/ResaleDrop/_processed/<date>/`, or to `~/ResaleDrop/_failed/` with a `.error.txt` explaining why. Keep the shell script as the last action in the rule.

## How photos find their item

Hazel hands over one file at a time, so grouping comes from where the file sits or what it is called. The first rule that matches wins:

| You drop | What happens |
|---|---|
| `RS-0012_socket.jpg`, or any file inside a folder called `RS-0012` | Added to item `RS-0012`. Use this to add the photos the review card asked for. |
| `~/ResaleDrop/ASUS TUF X570/IMG_1.jpg` (a folder per item) | One item per folder, named after the folder. All photos in it land on the same item. |
| `~/ResaleDrop/boards/ASUS TUF X570/IMG_1.jpg` | Same, and the first folder sets the category: `boards`, `clothing`, `sneakers`, `other` (singular forms and `shoes`, `apparel`, `mobo` also work). |
| `~/ResaleDrop/IMG_1.jpg` (loose) | Joins the newest "drop batch" item if its last photo arrived within 2 minutes, otherwise starts a new item. A phone shoot AirDropped in one go becomes one item. Change the window with `RESALE_BATCH_GAP_SECONDS`. |

Photo reading is queued with a 45-second settle delay (`RESALE_SETTLE_SECONDS`) after the **last** photo arrives, so a shoot that is still trickling in is read once, with everything.

## Subfolders

Hazel only descends into subfolders if you tell it to, and where that switch lives depends on the Hazel version. If your Hazel doesn't reach `~/ResaleDrop/<item folder>/`, either enable subfolder processing for the folder, or let `python -m resale_app watch` handle nested folders and keep Hazel for flat drops. The watcher reads up to four folder levels deep.

## Cautions

- **Don't aim a catch-all rule at your whole Downloads or Photos folder.** Every image it moves into `~/ResaleDrop` becomes a photo on an item. Point it at a dedicated export folder or album.
- If `~/ResaleDrop` is under Desktop or Documents and nothing happens, check that Hazel has the permission macOS asks for on those folders.
- HEIC photos from an iPhone need `pillow-heif` (it's in `requirements.txt`). Without it they land in `_failed/` with a clear message.

## Troubleshooting

- The log is `~/Library/Logs/resale-ingest.log`. Every Hazel call writes its arguments and result there.
- Run the same thing by hand to see what Hazel sees: `python -m resale_app ingest --keep ~/ResaleDrop/some-photo.jpg`.
- Photos landed but nothing was read: the web app isn't running, or an API key isn't set (the item's card says "Analysis failed" with the reason).

## Status of this document

The command Hazel runs (`python -m resale_app ingest`) is tested, including one-file-at-a-time calls that simulate Hazel. Hazel itself is a Mac app and wasn't available where this was written, so the rule wording above comes from memory. Check it against your Hazel on the first run, and fix this page if a label differs.
