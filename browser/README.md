# Foundry Town — browser game with cloud saves

The original Python map, trading mechanics, and character customization run in the browser through Pyodide. `web/engine.py` contains the adapted game and SVG renderer; the original desktop game in the repository root is preserved.

The initial screen offers **New Game** and **Continue**. Starting a new game asks before replacing existing progress. Continue loads the signed-in player's cloud save. Existing browser saves can be imported using Continue local game / Continue local backup.

## Saving

- `GET /api/save` returns the current user's save and revision, or `{ "save": null }`.
- `PUT /api/save` stores `{ version: 1, marketStart, state }`. Pass the revision from GET as the `If-Match` header (`none` for the first save).
- Saves are scoped by the server-provided `oai-authenticated-user-id` header. The hosting platform supplies authenticated identity; browser callers cannot choose a save owner.
- Cloudflare R2 binding `BUCKET` stores durable JSON save files. No third-party API key is needed.
- Stale revisions return 409 to prevent another tab overwriting newer progress.
- Cloud autosave runs every 10 seconds. Save game saves manually; Main menu saves before returning. A local backup is refreshed every 3 seconds and kept if the connection fails. Closing a tab sends a best-effort final save; use Save game and wait for confirmation before closing for certainty.

## Build and test

Requires Node.js 22+; no npm packages needed.

```
node --test tests/api.test.mjs
node scripts/build.mjs
```

The build embeds web assets and the API in `dist/server/index.js`, a Cloudflare Worker module. Deploy with the Sites hosting manifest. Hosted authentication and the R2 binding are required for cloud saves; serving the HTML with a plain static HTTP server does not provide the save API.

Pyodide is loaded from jsDelivr on first launch. Existing `.openai/hosting.json` identifies this game's Site; preserve its project ID when updating that deployment.
