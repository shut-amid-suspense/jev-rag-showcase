## How it works

A long manual is hard to search. Ctrl+F only finds the exact words you type, and a general chatbot may answer from memory instead of from your document. This app lets you ask in your own words and answers **only from your PDF**, showing the passage and page each answer comes from.

### Using it

1. **Keys.** The app uses [OpenRouter](https://openrouter.ai) to read the PDF and write answers, so it needs your OpenRouter API key. A [Cerebras](https://cloud.cerebras.ai) key is optional and adds the faster Qwen model. You paste them once; they're checked, then kept only in your browser. **Remove keys** deletes them. The app never uses a key of its own.
2. **PDF.** Upload a PDF. It's indexed right away, with progress shown. The 867-page Ableton Live 11 manual usually takes 15–40 seconds, and up to about a minute and a half when OpenRouter is busy. It costs about half a cent.
3. **Ask.** Type a question the way you'd ask a colleague. The answer shows up with the passages it's based on. Open **How it found this** to see every search it ran.

### What happens when you upload

- The text of every page is read and cut into passages of up to about 300 words. The Live 11 manual becomes 1,047 passages.
- Each passage is labelled with the heading it falls under in the PDF's own table of contents.
- Two indexes are built: one for **words** (keyword search) and one for **meaning** (an embedding of each passage), so a search finds a passage even when it uses different words than you did.

### What happens when you ask

An AI agent (Gemini 3.7 Flash) searches the PDF the way a person would:

1. It turns your question into the words the document itself would use, and searches.
2. Each search merges the keyword and meaning results into 20 candidates. **Jev**, a model built to pick from a list, ranks them, and the best 3 go back to the agent.
3. If those don't answer the question, it searches again with other words, or reads the whole page around a passage. It takes up to 6 steps.
4. It answers and names the passages it used. If the PDF doesn't cover the question, it says so instead of guessing.

### Why you can check every answer

- Answers come only from the PDF's text, not from the model's general knowledge.
- The full passage behind each answer is shown under it, with its page and section.
- Every search step is listed under **How it found this**.

### What we measured

On the Ableton Live 11 manual, with 149 test questions:

| Way of finding the right passage | Found it |
|---|---|
| Keyword search alone | 44% |
| Meaning search alone | 62% |
| Both, then Jev picks | **83%** |
| Both, then a general chat model picks | 82%, but twice as slow and about 7× the cost |

A full answer from the agent takes about **5 seconds** for a simple question and up to **25 seconds** when it has to search several times, for example when the manual doesn't cover the question. Most of that time is the agent thinking between searches. Each question costs roughly $0.002–$0.02.

### Good to know

- **Your PDF's text is sent to OpenRouter** and the model providers behind it, to index it and answer. Don't upload confidential documents.
- **Your keys** go to the app's server with each request, because it makes the calls for you, and are stored in your browser, not on the server.
- **Scanned PDFs** without a text layer can't be searched. Images aren't read, and tables lose their layout.
- **Answers take seconds, not milliseconds.** Most of the time goes to the agent deciding what to search next.
- **Indexes live in memory.** After the app restarts, a PDF is indexed again. Re-uploading the same PDF while the app is running is instant.

### Tips for better answers

- **Describe what you see:** "I only hear the echo, not my note" works better than "echo broken".
- **Use the feature's name if you know it:** it helps the first search land.
- **Check the passage under the answer:** it's there so you don't have to trust the answer blindly.
