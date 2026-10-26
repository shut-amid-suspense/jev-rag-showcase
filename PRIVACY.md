# Data flow and local storage

- The browser sends a supplied API key to the local Gradio server for provider requests. The sharing version holds keys in per-session server memory and does not persist them in localStorage or index files. Reloading the page requires key entry again; Remove keys clears the active session values.
- PDF text is sent to OpenRouter's embedding and answer providers. Standard and Thorough also send candidate passages to Jev through OpenRouter's Decisions API. An optional screenshot is sent to the selected answer provider.
- If Cerebras is selected, its key and the selected answer context are sent to Cerebras. Retrieval still uses OpenRouter.
- Uploaded document text and embeddings are cached locally under `data/indexes/`. The cache is data-only JSON and is not included in the repository. Cache files are created with owner-only permissions on POSIX systems.
- Gradio manages temporary upload files locally. Removing a PDF from the page forgets the selection; it is not a promise to erase all local cache or temporary files. To discard saved indexes, stop the app and remove its `data/indexes/` folder.
- The app explicitly binds to `127.0.0.1` and disables Gradio analytics by default. Do not expose the service or enable sharing for confidential data.

This is a single-user proof of concept. It does not implement user isolation, provider retention controls or production access management. Historical source snapshots preserve the code used for the recorded tests; they predate the sharing version's credential/cache cleanup and are provided for evidence verification.
