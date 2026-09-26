## How it works

A long manual is hard to search. Ctrl+F only finds the exact words you type, and a general chatbot may answer from memory instead of from your document. This app lets you ask in your own words and answers **only from your PDF**, showing the passage and page each answer comes from.

### Using it

1. **Keys.** The app uses [OpenRouter](https://openrouter.ai) to read the PDF and write answers, so it needs your OpenRouter API key. A [Cerebras](https://cloud.cerebras.ai) key is optional and adds the faster Qwen model. You paste them once; they're checked, then kept only in your browser. **Remove keys** deletes them. The app never uses a key of its own.
2. **PDF.** Upload a PDF. It's indexed right away, with progress shown. The 867-page Ableton Live 11 manual usually takes 15–40 seconds, and up to about a minute and a half when OpenRouter is busy. It costs about half a cent.
3. **Ask.** Type a question the way you'd ask a colleague. Attach a screenshot with the paperclip if it helps; click its thumbnail to see it full size. Pick the **Search** and the **Model** under the box. The answer shows up with the passages it's based on. Open **How it found this** to see every search it ran.

### What happens when you upload

- The text of every page is read and cut into passages of up to about 300 words. The Live 11 manual becomes 1,047 passages.
- Each passage is labelled with the heading it falls under in the PDF's own table of contents.
- Two indexes are built: one for **words** (keyword search) and one for **meaning** (an embedding of each passage), so a search finds a passage even when it uses different words than you did.

### What happens when you ask

There are three ways to search, chosen under **Search**:

- **Standard** (the default). The AI reads your question and screenshot and writes a few search terms in the manual's own words, such as the names of the controls it sees. Each term is searched (keyword and meaning search together), the hits go into one pool of up to 40 passages, **Jev**, a model built to pick from a list, keeps the best 5, and the AI answers from those.
- **Fast.** One search with your question as typed. The top 5 passages go straight to the AI. No Jev.
- **Thorough.** An AI agent searches like a person would: it searches, Jev ranks each search's 20 candidates and hands back the best 3, and it searches again with other words or reads the whole page until it's sure. Up to 6 steps.

Every way answers only from the passages it found and names them. If the PDF doesn't cover the question, it says so instead of guessing.

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

Full answers on 20 of those questions (typical time, slowest, cost per question):

| Search | Model | Right page found | Typical | Slowest | Cost |
|---|---|---|---|---|---|
| Fast | Gemini | 16 of 20 | 4.1 s | 11.0 s | $0.003 |
| Standard | Gemini | **20 of 20** | 7.5 s | 11.2 s | $0.004 |
| Thorough | Gemini | 20 of 20 | 6.0 s | 20.8 s | $0.004 |
| Fast | Qwen | 16 of 20 | 1.3 s | 2.7 s | $0.003 |
| Standard | Qwen | 19 of 20 | 2.5 s | 3.9 s | $0.004 |
| Thorough | Qwen | 19 of 20 | 3.0 s | 9.0 s | $0.007 |

With a screenshot, Gemini is the better reader: shown the Note Echo device with its input set to Mute, it searched for "Note Echo" and "Mute" and found the right page. Qwen searched in general terms and missed it.

### Good to know

- **Your PDF's text is sent to OpenRouter** and the model providers behind it, to index it and answer. Don't upload confidential documents.
- **Your keys** go to the app's server with each request, because it makes the calls for you, and are stored in your browser, not on the server.
- **Scanned PDFs** without a text layer can't be searched. Images aren't read, and tables lose their layout.
- **Answers take seconds, not milliseconds.** Most of the time goes to the AI thinking, not to the search.
- **Indexes live in memory.** After the app restarts, a PDF is indexed again. Re-uploading the same PDF while the app is running is instant.

### Tips for better answers

- **Describe what you see:** "I only hear the echo, not my note" works better than "echo broken".
- **Use the feature's name if you know it:** it helps the first search land.
- **Check the passage under the answer:** it's there so you don't have to trust the answer blindly.
