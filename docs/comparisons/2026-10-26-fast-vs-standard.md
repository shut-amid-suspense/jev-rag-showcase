# Jev RAG: live comparison

Tested on 26 October 2026 using the OpenRouter key supplied by Sesame.

The test called the existing application indexing and answering functions with real provider requests. It did not automate a browser chat session. The browser interface was separately opened and checked.

## What was compared

- **Fast:** a normal hybrid RAG baseline: one keyword/embedding search, its top five passages, then one answer call.
- **Standard:** generate search terms, search each term, pool up to 40 passages, use Jev to rank them, then answer from the best five.
- Both used the same PDF, index, questions, and answer model. Fast/Standard order alternated by question.

The document was the existing 867-page Ableton Live 11 manual. Eight questions were randomly sampled from the existing 149-question set with seed 20261026; two deliberately unrelated questions checked whether the system would decline to invent an answer. Each mode answered all ten.

**Models:** answer generation `google/gemini-3.8-flash`; embeddings `openai/text-embedding-3-small`; reranker `~typesafe/jev-latest`.

## Whole-answer performance and cost

| Mode | Median time | Slowest answer | Mean cost per question | Extrapolated cost per 1,000 questions | API requests per question |
|---|---:|---:|---:|---:|---:|
| Fast | 5.66 s | 10.20 s | $0.002512 | $2.51 | 2.0 |
| Standard | 11.45 s | 32.92 s | $0.003996 | $4.00 | 4.0 |

Standard's median time was 2.02 times Fast's, and its mean query cost was 1.59 times Fast's in this small run.

Costs are the usage.cost values returned by OpenRouter for all successful embedding, reranking and answer-generation requests in each pipeline. They include query expansion in Standard and exclude initial indexing. Cost per 1,000 is an extrapolation from ten queries, not a bulk run or guaranteed price.

Initial indexing took 45.05 seconds and cost $0.005609, producing 1,047 passages. This was a fresh indexing run; later questions reused that index.

The comparison's total recorded API cost, including indexing and the separate retrieval experiment below, was $0.072812. The preliminary three-request capability check cost about $0.000397 separately.

## Isolating the Jev step

A separate retrieval experiment used each of the same eight answerable questions, a single shared query embedding and the same 20-candidate hybrid shortlist. This isolates adding Jev from the extra query-expansion work in Standard.

| Metric | Result |
|---|---:|
| Median hybrid search time | 1.00 s |
| Median hybrid search plus Jev time | 1.73 s |
| Mean extra Jev cost per question | $0.000264 |
| Extra Jev cost extrapolated per 1,000 questions | $0.26 |
| Expected page selected by meaning search alone | 4/8 |
| Expected page selected by hybrid search | 5/8 |
| Expected page selected by hybrid plus Jev | 6/8 |

**Expected-page matching is not answer accuracy.** The manual repeats instructions. For example, template access is correctly described on pages 71 and 97 even though the benchmark question names page 24. Push automation is described on both pages 720 and 791. These alternatives explain several benchmark misses without establishing an incorrect answer.

## What the answers showed

Both modes supplied useful answers with cited passages in the sampled manual tasks. Standard sometimes brought in broader evidence: for automation recording it explained both the ordinary Session View workflow and the Push 2 workflow; Fast concentrated on Push. For the reverb question, Standard added Dark Hall details while Fast gave the direct Size-setting answer. Other pairs were substantially similar.

Both modes declined the two deliberately unrelated questions and provided no source passages for them. These are easy absence checks; they do not establish reliability on difficult, nearly answerable questions.

There was no blinded answer-quality grading or repeated timing study. The sample is too small to establish a general winner in answer quality. Standard also adds query expansion and changes the retrieved pool, so differences between its final answers and Fast cannot be attributed only to Jev.

For context, the existing older 149-question retrieval experiment recorded 124 exact-passage hits with hybrid plus Jev, 87 with hybrid alone, and 92 with embedding search alone. Those historical retrieval measurements are separate from this new whole-answer run.

## Recorded artifacts and method

- [Machine-readable requests, answers, timings and costs](2026-10-26-fast-vs-standard.json)
- Application source revision tested: `5fa3361`.
- The run called `app.index_pdf`, `classic.run_classic` and `keywords.run_keywords` without changing those application functions. Request instrumentation recorded the provider-reported costs.
- Eight questions were sampled from `data/questions.json` using `random.Random(20261026).sample(questions, 8)`. Their exact wording and expected pages are preserved in the JSON. The two absence controls are also preserved there.
- The separate retrieval experiment used the same indexed passages, a shared query embedding, BM25 and embedding rankings fused with reciprocal-rank fusion, and the same top-20 shortlist before adding Jev.
- Requests ran sequentially within each comparison; Fast and Standard order alternated by question. PDF embedding batches used the application's normal parallel indexing.
- The stored results omit complete manual passages and credentials. The copyrighted PDF, generated indexes and local environment are excluded from this report bundle.
- The test harness used for this run was outside the repository. This archive contains the report and measured data; it does not add a new benchmark runner or change application behavior.

## Per-question evidence

### 1. How do I find and access template Live Sets in the browser?

**Fast — 3.77 s; $0.001817; source pages: 71, 97**

Template Live Sets can be found and accessed in the browser’s Templates category, as well as in the Templates folder within the User Library.

**Standard — 10.67 s; $0.003455; source pages: 24, 71, 97**

You can find and access template Live Sets in the browser via the **Templates** label under the **Categories** section. This category displays template Live Sets from factory packs (including the Core Library), the User Library, and other Project folders. Additionally, template sets can be accessed directly from the **Templates** folder inside the User Library.

### 2. How do I make a reverb sound more metallic or smaller?

**Fast — 4.34 s; $0.002481; source pages: 487**

To make the reverb sound more metallic or smaller in room volume, set the Size parameter to a very small value.

**Standard — 17.36 s; $0.003734; source pages: 452, 487**

To make a reverb sound more metallic or smaller, set the **Size** parameter to a very small value, which reduces the room's volume and gives the reverb a highly colored, metallic feel. In Dark Hall mode, you can also adjust the **Shape** parameter toward small and resonant, or combine extremely small Size values with long decay times to create metallic gong-like resonances.

### 3. How do I record parameter changes into a clip so they play back automatically?

**Fast — 6.29 s; $0.003231; source pages: 720, 791**

To record parameter changes into a clip as automation:

1. Press the **Automation** button on Push (on Push 2, it will turn red). This toggles Live's Session Automation Arm button.
2. Adjust the device or mixer parameters using Push's encoders while the clip plays; these changes are recorded into the clip.
3. When you are finished recording parameter changes, press the **Automation** button again to turn it off.

**Standard — 11.41 s; $0.005419; source pages: 355, 791**

To record parameter changes into a clip as automation:

**In Live's Session View:**
1. Enable the **Automation Arm** button.
2. Activate the **Arm** button for the track(s) you want to record onto (or enable the *Session Automation Recording* switch in Preferences to record into all playing clips regardless of track arming).
3. Click the **Session Record** button to begin recording, then adjust the device or mixer parameters.

**Using Push 2:**
1. Press the **Automation** button so it turns red (this toggles Live's Session Automation Arm).
2. Adjust the parameter encoders to record the changes into the clip.
3. When finished, press the **Automation** button again to turn it off.

### 4. How do I control how quickly the gate closes after the sound drops below the threshold?

**Fast — 6.63 s; $0.002305; source pages: 428, 442**

You control how quickly the gate closes using the Release parameter, which sets the period of time over which the gate closes after the sound drops below the threshold (and after any set Hold time expires).

**Standard — 13.62 s; $0.003437; source pages: 428, 442**

You can control how quickly the gate closes after the sound drops below the threshold by adjusting the Release parameter. (Note that when the signal drops below the threshold, the Hold time kicks in first, after which the gate closes over the period set by Release).

### 5. How do I make the arpeggiator pattern repeat at specific intervals or restart at certain beats?

**Fast — 7.18 s; $0.003078; source pages: 520**

You can control pattern repetition and restarting using the following parameters:

- **Repeats:** Allows you to set the pattern to repeat a specified number of times (or indefinitely with "inf") until it is retriggered.
- **Retrigger:** Resets the pattern so it restarts from the beginning. By setting Retrigger to **Beat**, you can make the pattern restart at a specified song position or beat-time, defined in terms of notes or bars and aligned with the song position.

Combining the **Repeats** and **Retrigger** parameters allows you to create rhythmically generated arpeggios separated by pauses.

**Standard — 10.77 s; $0.004644; source pages: 520**

To restart or repeat the arpeggiator pattern at specific intervals or beats, use the **Retrigger** parameter (which can also be combined with the **Repeats** parameter):

- Set **Retrigger** to **Beat**: This resets the pattern to start again from the beginning at a specified song position or beat-time. Beat retriggering can be specified in terms of notes or bars and is aligned with the song position.
- Use the **Repeats** parameter: This controls the number of times the pattern repeats until it is retriggered, allowing you to create rhythmically generated arpeggios separated by pauses when combined with Retrigger.

### 6. How do fade times work differently between Mono/Poly and Thru playback modes in Simpler?

**Fast — 5.92 s; $0.001979; source pages: 614**

With Mono or Poly selected, fade times are measured from the beginning to the end of each individual slice. In contrast, with Thru selected, fade times are measured from the triggered slice to the end of the entire sample region, meaning the fade times can sound different depending on where in the region playback is triggered.

**Standard — 11.50 s; $0.002977; source pages: 614**

With Mono or Poly selected, fade times are measured from the beginning to the end of each individual slice. In contrast, with Thru selected, fade times are measured from the triggered slice to the end of the region.

### 7. How do I control different parameters using pressure, slide, and pitch bend in an MPE device?

**Fast — 10.20 s; $0.004630; source pages: 674, 675**

In an MPE device (such as the MPE Control effect), you can utilize these sources as follows:

- **Pressure:** Controls polyphonic aftertouch (accessed after initially pressing a key down), allowing you to assign per-note aftertouch to various parameters.
- **Slide:** Modifies MIDI CC 74 (often corresponding to the vertical position of a finger on a key or pad), which you assign to the specific parameter you want to control within an MPE-enabled instrument.
- **Pitch:** Modifies the X-axis (per-note pitch bend), which by definition only affects the pitch or pitches being produced (though Note Pitch Bend MIDI CC can also be mapped to other targets).

You can select each source using the Source drop-down chooser to edit their curves and modulation settings, while all sources remain active.

**Standard — 32.92 s; $0.006274; source pages: 673, 674**

In an MPE device such as MPE Control:

* **Pressure:** Controls polyphonic aftertouch (accessed after initially pressing a key down), allowing you to assign per-note aftertouch to modulate various parameters.
* **Slide:** Modifies MIDI CC 74 (typically corresponding to the vertical position of a finger on a key or pad), which you assign directly to the desired parameter within an MPE-enabled instrument.
* **Pitch Bend (Pitch):** Modifies the X-axis for per-note pitch bend (Note Pitch Bend); by definition, it only affects the pitch or pitches being produced.

In the MPE Control effect, you can select any of these via the **Source** drop-down chooser to shape and edit their response curves (all MPE sources remain active simultaneously even when not selected).

### 8. How do I export audio from Looper as a new clip in Live?

**Fast — 5.40 s; $0.002306; source pages: 460**

You can export audio from Looper by dragging and dropping from the ”Drag me!” area in Looper's display directly to a track (or to the browser), which creates a new clip.

**Standard — 8.11 s; $0.003415; source pages: 460**

You can export audio from Looper as a new clip by dragging and dropping from the "Drag me!" area in Looper's display directly onto a track (or to the browser).

### 9. What is the exact price of a private helicopter transfer from Berlin to Munich on 26 October 2026?

**Fast — 4.17 s; $0.001474; source pages: none**

The provided passages do not contain information about the price of a private helicopter transfer from Berlin to Munich.

**Standard — 6.57 s; $0.003697; source pages: none**

The provided passages do not contain information about the price of a helicopter transfer from Berlin to Munich.

### 10. What is the password for the Fairsource company payroll administrator account?

**Fast — 3.80 s; $0.001821; source pages: none**

The provided passages do not contain information about the password for the Fairsource company payroll administrator account.

**Standard — 28.61 s; $0.002912; source pages: none**

The provided passages do not contain information about the password for the Fairsource company payroll administrator account.
