## How it works

The app retrieves passages from a PDF and asks an answer model to use that evidence. Sources and search steps are shown so you can check the result. Models can omit information or make errors; citations are useful evidence to inspect, not a correctness guarantee.

### Use it

1. Run the app using the README setup instructions. Enter an OpenRouter key. A Cerebras key is optional.
2. Upload a text-based PDF, such as `examples/support-handbook.pdf`. The app extracts passages, labels them with page numbers and builds keyword and embedding indexes.
3. Ask a question. Choose Fast, Standard or Thorough. Inspect the answer and its cited passages, then expand **How it found this** to inspect retrieval steps.

Fast uses one hybrid search without Jev. Standard generates focused search terms and asks Jev to rank the combined candidate pool. Thorough lets an agent search repeatedly, with Jev ranking each search's shortlist, and read full pages when needed. The generative model writes the final answer in all three modes.

### Keys and saved data

API keys are held in server-side session memory. They are not written to browser storage, cache files or logs. Re-enter them after a page reload. **Remove keys** clears the active key state. Restarting the server also clears its in-memory sessions.

The local index contains extracted document text, metadata and embeddings. It is stored as validated JSON under `data/indexes/`, which is ignored by Git. The ten most recently used indexes are retained. Selecting an unchanged PDF again reuses its saved index. After a server restart, reselect the PDF; the index remains available.

PDF text goes to OpenRouter and its selected providers for embedding and answering. An attached screenshot also goes to the selected answer provider. The optional Cerebras route sends the answer context to Cerebras. No unrelated credential file or other repository is read to obtain a key.

### Limits

Scanned PDFs without a text layer cannot be indexed. PDF tables and layout may lose structure during text extraction. The application runs locally for one trusted user; it is not a hosted multi-user service. The included benchmark reports describe small experiments and their limitations.
