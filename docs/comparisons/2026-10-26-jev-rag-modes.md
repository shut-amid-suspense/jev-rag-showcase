# Jev RAG POC: Fast, Standard and Thorough

This benchmark compares the three search modes exposed by this application. All application code, test questions, the benchmark runner and the recorded results belong to this repository.

## Scope and method

- **Jev RAG — Fast:** one hybrid keyword/embedding search; answer from the top five passages.
- **Jev RAG — Standard:** generate search terms, combine their search results, rank up to 40 candidates with Jev, and answer from five passages.
- **Jev RAG — Thorough:** an agent can search repeatedly with Jev, read whole pages and then answer; the application limits it to six model turns.

Run started: 2026-10-26T19:06:45.201040+01:00. Document: `data/live11-manual-en.pdf`. Questions: `benchmarks/cases/live11.json`.

The same 10 questions, document index, and answer model were used for each mode. Mode order rotated for successive questions. Requests within each answer ran sequentially; indexing used the application's normal batching.

Answer model: `google/gemini-3.8-flash`. Embeddings: `openai/text-embedding-3-small`. Jev: `~typesafe/jev-latest`.

The runner calls the application functions directly. It does not automate browser interactions or test screenshots. Application source hashes and request-level usage are recorded in the JSON.

## Whole-answer measurements

| Jev RAG mode | Median time | Slowest | Mean cost per question | Estimated cost per 1,000 | Mean API requests |
|---|---:|---:|---:|---:|---:|
| Jev RAG — Fast | 5.79 s | 15.63 s | $0.002700 | $2.70 | 2.0 |
| Jev RAG — Standard | 14.55 s | 34.92 s | $0.004156 | $4.16 | 4.0 |
| Jev RAG — Thorough | 20.75 s | 53.14 s | $0.005658 | $5.66 | 7.0 |

Costs are provider-reported `usage.cost` for the complete answer pipeline: query embeddings, query expansion where used, reranking where used and answer generation. Initial indexing is separate. Per-1,000 figures extrapolate this small sample; they are not a bulk run or guaranteed prices.

Index preparation: 63.99 s, $0.005609, 1047 passages. Saved index reused: False.

Total known API cost for this run, including any indexing calls: $0.130745.

## Answer-quality limits

Expected-page matching is a retrieval/citation check, not an answer-correctness score. A document may contain the same instruction on several pages. No blinded answer-quality judging was performed. The sample and one timing run per question do not establish a general accuracy winner. Standard and Thorough change the retrieval workflow as well as using Jev, so their differences cannot be attributed entirely to the ranking model.

| Jev RAG mode | Answers returned | Expected page cited on answerable questions | Empty answers |
|---|---:|---:|---:|
| Jev RAG — Fast | 10/10 | 7/8 | 0 |
| Jev RAG — Standard | 10/10 | 7/8 | 0 |
| Jev RAG — Thorough | 10/10 | 6/8 | 0 |

The two questions marked with no expected page are deliberate absence controls. Their full answers and source lists are preserved below; empty citations by themselves do not prove a correct refusal.

## Reproduce from this repository

[Benchmark instructions](../../benchmarks/README.md) include a synthetic handbook and questions that are committed in this repository. The default run builds its own PDF from that fixture, so it does not require a downloaded manual or another checkout.

Run this exact case from the repository root after making its PDF available at the recorded repository-local path:

```bash
sesame run OPENROUTER_API_KEY -- .venv/bin/python benchmarks/compare_search_modes.py --case benchmarks/cases/live11.json --output-prefix docs/comparisons/repeated-jev-rag-modes
```

The Ableton manual case uses a copyrighted local PDF and is therefore not the default portable case. The PDF and generated indexes are ignored by Git. Its SHA-256 is recorded for comparison; the questions and all measured results are committed here.

[Machine-readable measured results](2026-10-26-jev-rag-modes.json)

## All answers

### 1. How do I find and access template Live Sets in the browser?

**Jev RAG — Fast: 4.88 s; $0.001986; source pages: 71, 97; model turns: 1**

You can find and access template Live Sets in the browser via:

• The browser’s **Templates** category.
• The **Templates** folder in the **User Library** (which is automatically created the first time a template set is saved).

**Jev RAG — Standard: 10.23 s; $0.003707; source pages: 24, 71, 97; model turns: 2**

You can find and access template Live Sets in the browser under the **Templates** label in the **Categories** section, as well as in the **Templates** folder within the **User Library**. The Templates category displays template Live Sets from factory packs (including the Core Library), the User Library, and other Project folders.

**Jev RAG — Thorough: 24.50 s; $0.003095; source pages: 24, 71, 97; model turns: 3**

You can find and access template Live Sets in the browser by:

1. Going to the **Templates** label under the browser's **Categories**, which displays template Live Sets from factory packs (including the Core Library), the User Library, and other Project folders.
2. Navigating to the **Templates** folder located in the **User Library** (which is automatically created the first time a template Set is saved).

### 2. How do I make a reverb sound more metallic or smaller?

**Jev RAG — Fast: 5.26 s; $0.002579; source pages: 487; model turns: 1**

To make the reverb sound more metallic or smaller, set the Size parameter to a very small value. The Size parameter controls the room's volume, and using a very small value gives the reverb a highly colored, metallic feel.

**Jev RAG — Standard: 26.86 s; $0.004536; source pages: 452, 487; model turns: 2**

To make a reverb sound smaller or more metallic:

- **Set the Size parameter to a very small value:** The Size parameter controls the room's volume; setting it to a very small value gives the reverb a highly colored, metallic feel. In Dark Hall mode, combining extremely small Size values with long decay times produces metallic gong-like resonances.
- **Adjust the Shape parameter:** Lower/transforming the Shape parameter shifts the artificial space's characteristics toward sounding small and resonant rather than large and diffused.

**Jev RAG — Thorough: 30.21 s; $0.004493; source pages: 452, 485, 487; model turns: 3**

To make a reverb sound more metallic or smaller, set the **Size** parameter to a very small value. In the Reverb effect, the Size parameter controls the room's volume: setting it to a very small value gives it a highly colored, metallic feel. Additionally:

- In the Hybrid Reverb's Dark Hall algorithm, combining extremely small **Size** values with long decay times creates metallic, gong-like resonances, while adjusting **Shape** can transform the artificial space's sonic characteristics from small and resonant to large and diffused.
- When the room size is extremely small in Reverb, the **Diffusion** and **Scale** parameters also have a large impact on the coloration contributed by the diffusion.

### 3. How do I record parameter changes into a clip so they play back automatically?

**Jev RAG — Fast: 8.62 s; $0.003194; source pages: 720, 791; model turns: 1**

To record parameter changes into a clip as automation so they play back over time:

1. Press Push's (or Push 2's) **Automation** button (on Push 2, it turns red). This toggles Live's Session Automation Arm button.
2. Adjust the device or mixer parameters using the encoders while the clip plays to record the changes into the clip.
3. When finished, press the **Automation** button again to turn it off.

**Jev RAG — Standard: 15.14 s; $0.004606; source pages: 355, 791; model turns: 2**

To record parameter changes into a clip as automation:

1. Enable the **Automation Arm** button to prepare for automation recording.
2. Activate the **Arm** button for the tracks onto which you want to record.
3. Click the **Session Record** button to begin recording automation while adjusting the controls.

*(Note: It is also possible to record automation into all playing Session clips regardless of track arming via the Session Automation Recording switch in Preferences. If using Push 2, you can press the Automation button so it turns red, adjust the encoders to record changes into the clip, and press the button again when finished).*

**Jev RAG — Thorough: 37.46 s; $0.007247; source pages: 355, 356; model turns: 5**

To record parameter changes into a Session View clip as automation so they play back automatically:

1. Enable the **Automation Arm** button in the Control Bar to prepare for automation recording.
2. Activate the **Arm** button for the track(s) onto which you want to record.
3. Click the **Session Record** button to begin recording automation while adjusting the desired parameters.

*(Note: You can also record automation into all currently playing Session clips regardless of track arm status by setting the **Session Automation Recording** switch in the Record/Warp/Launch Preferences.)*

### 4. How do I control how quickly the gate closes after the sound drops below the threshold?

**Jev RAG — Fast: 4.33 s; $0.002144; source pages: 428, 442; model turns: 1**

You can control how quickly the gate closes using the Release parameter, which sets the period of time over which the gate closes after the signal drops below the threshold (and after any Hold time expires).

**Jev RAG — Standard: 17.37 s; $0.003799; source pages: 428, 442; model turns: 2**

You control how quickly the gate closes after the signal drops below the threshold using the Release parameter. (Note that when the signal falls below the threshold, the Hold time kicks in first; once it expires, the gate closes over the period of time set by Release.)

**Jev RAG — Thorough: 17.00 s; $0.002721; source pages: 442; model turns: 2**

You can control how quickly the gate closes using the **Release** parameter, which sets the period of time over which the gate closes. Additionally, when the signal drops from above to below the threshold, the **Hold** time kicks in first; once the hold time expires, the gate closes at the rate determined by the Release setting.

### 5. How do I make the arpeggiator pattern repeat at specific intervals or restart at certain beats?

**Jev RAG — Fast: 8.97 s; $0.003738; source pages: 520; model turns: 1**

To control how the pattern repeats or restarts, use the following parameters:

- **Repeats parameter:** Allows you to set the pattern to repeat a specified number of times until it is retriggered (or indefinitely with a setting of "inf").
- **Retrigger parameter:** Resets the pattern to start again from the beginning. Setting it to **Beat** allows it to restart at a specified song position or beat-time, which can be specified in terms of notes or bars and is aligned with the song position.

**Jev RAG — Standard: 13.59 s; $0.005041; source pages: 520; model turns: 2**

To restart the arpeggiator pattern at certain beats and control its repetitions, use the **Retrigger** and **Repeats** parameters:

* **Restarting at certain beats:** Use the **Retrigger** parameter and set it to **Beat**. This resets the pattern so that it starts again from the beginning at a specified song position or beat-time (which can be defined in notes or bars and aligns with song position).
* **Repeating at specific intervals:** Use the **Repeats** parameter to specify the number of times the pattern repeats before retriggering (or set it to "inf" to repeat indefinitely). Combining **Repeats** with **Retrigger** allows you to create rhythmically generated arpeggios separated by pauses.

**Jev RAG — Thorough: 9.11 s; $0.002709; source pages: 520; model turns: 2**

To make the arpeggiator pattern repeat at specific intervals or restart at certain beats, use the following parameters:

- **Retrigger parameter:** Resets the pattern so it starts again from the beginning. By setting Retrigger to **Beat**, retriggering can be set to occur at a specified song position or beat-time (specified in terms of notes or bars, aligned with song position). Retriggering can also be set to occur when new notes are pressed (**Note**) or deactivated (**Off**). An LED in the upper right corner indicates when the pattern has been retriggered.
- **Repeats parameter:** Allows the pattern to repeat a specified number of times until it is retriggered (a setting of “inf“ repeats the pattern indefinitely). Combining Repeats with Retrigger allows you to create rhythmically generated arpeggios separated by pauses.
- **Hold parameter:** Keeps the pattern repeating even after keyboard keys are released, continuing until another key is pressed.

### 6. How do fade times work differently between Mono/Poly and Thru playback modes in Simpler?

**Jev RAG — Fast: 5.57 s; $0.001908; source pages: 614; model turns: 1**

With Mono or Poly selected, fade times are measured from the beginning to the end of each individual slice. In contrast, with Thru selected, fade times are measured from the triggered slice to the end of the entire region, meaning the fade times can sound different depending on where in the region you trigger playback.

**Jev RAG — Standard: 8.05 s; $0.003038; source pages: 614; model turns: 2**

In Mono or Poly mode, fade times are measured from the beginning to the end of each individual slice. In Thru mode, fade times are measured from the triggered slice to the end of the region, which means fade times can sound different depending on where in the region the sample is triggered.

**Jev RAG — Thorough: 16.45 s; $0.001942; source pages: 614; model turns: 2**

In Simpler, Fade In and Out controls behave differently based on the Playback setting:

- **Mono or Poly mode:** Fade times are measured from the beginning to the end of each individual slice.
- **Thru mode:** Fade times are measured from the triggered slice to the end of the region, which means fade times may sound different depending on where in the region you trigger playback.

### 7. How do I control different parameters using pressure, slide, and pitch bend in an MPE device?

**Jev RAG — Fast: 11.49 s; $0.006141; source pages: 674, 675; model turns: 1**

In an MPE device (such as within MPE Control), you control parameters using these sources as follows:

- **Pressure:** Controls polyphonic aftertouch (accessed after initially pressing a key down), allowing you to assign per-note aftertouch to various parameters.
- **Slide:** Modifies MIDI CC 74 (often corresponding to the vertical position of your finger on the controller key or pad), which you assign to the specific parameter you want to control within an MPE-enabled instrument.
- **Pitch Bend (Pitch):** Modifies the X-axis, corresponding to per-note pitch bend, which by definition specifically affects the pitch or pitches being produced (or can cover larger modulation ranges if mapped to another destination).

In MPE Control, you can select each source (Pressure, Slide, or Pitch) via the Source drop-down chooser to edit its curve (Linear or S-Shaped) and settings, though all MPE sources remain active simultaneously.

**Jev RAG — Standard: 11.65 s; $0.005691; source pages: 674; model turns: 2**

In an MPE-enabled device or when using the MPE Control effect, parameters are controlled through the three MPE sources as follows:

- **Pressure:** Controls polyphonic aftertouch (accessed after pressing a key down), allowing you to assign per-note aftertouch to various parameters.
- **Slide:** Modifies MIDI CC 74 (often corresponding to the vertical position of your finger on a key or pad). You can assign this directly to the parameter you wish to control within an MPE-enabled instrument.
- **Pitch:** Modifies the X-axis to provide per-note pitch bend (Note Pitch Bend), which by definition only affects the pitch or pitches being produced.

In the MPE Control device, you can select any of these via the **Source** drop-down chooser to view and edit their modulation curves (Linear or S-Shaped) and controls, while all three sources remain active simultaneously.

**Jev RAG — Thorough: 37.60 s; $0.016052; source pages: 674, 675; model turns: 6**

In an MPE-enabled device or setup, pressure, slide, and pitch bend operate and control parameters as follows:

- **Pressure:** Controls polyphonic aftertouch (accessed after initially pressing a key down), allowing you to assign per-note aftertouch to various parameters.
- **Slide:** Modifies MIDI CC 74 (often corresponding to the vertical position of your finger on a controller key or pad). You assign MIDI CC 74 to the specific parameter you want to control within the MPE-enabled instrument.
- **Pitch Bend:** Modifies the X-axis on a per-note basis (Note Pitch Bend) and, by definition, directly affects the pitch or pitches being produced (though devices like MPE Control allow adjusting the pitch range or remapping).

You can also use tools like the **MPE Control** device to shape and transform these modulation curves (Linear or S-Shaped), adjust min/max values, smooth rise/fall times, or convert MPE messages to standard MIDI CC messages for non-MPE instruments.

### 8. How do I export audio from Looper as a new clip in Live?

**Jev RAG — Fast: 3.92 s; $0.001890; source pages: 460; model turns: 1**

To export audio from Looper as a new clip, drag and drop from the "Drag me!" area in Looper's display directly onto a track (or to the browser).

**Jev RAG — Standard: 14.57 s; $0.003752; source pages: 460; model turns: 2**

To export audio from Looper as a new clip, use the "Drag me!" area in Looper's display and drag and drop directly onto a track (or to the browser). The newly created clip's Warp mode will default to Re-Pitch.

**Jev RAG — Thorough: 9.70 s; $0.001954; source pages: 460; model turns: 2**

To export audio from Looper as a new clip in Live, drag and drop directly from the "Drag me!" area in Looper's display to a track. You can also drag and drop it to the browser to export Looper's buffer as a new audio file. (The newly created clip will have its Warp mode set to Re-Pitch by default.)

### 9. What is the exact price of a private helicopter transfer from Berlin to Munich on 26 October 2026?

**Jev RAG — Fast: 15.63 s; $0.001718; source pages: none; model turns: 1**

The provided passages do not contain information about the price of a private helicopter transfer from Berlin to Munich.

**Jev RAG — Standard: 14.52 s; $0.004571; source pages: none; model turns: 2**

The provided passages do not contain information about the price of a private helicopter transfer from Berlin to Munich.

**Jev RAG — Thorough: 8.55 s; $0.002223; source pages: none; model turns: 2**

The provided document is the Ableton Live Reference Manual and does not contain information about helicopter transfers or their pricing.

### 10. What is the password for the Fairsource company payroll administrator account?

**Jev RAG — Fast: 6.00 s; $0.001704; source pages: none; model turns: 1**

I am sorry, but the provided passages do not contain information about the password for the Fairsource company payroll administrator account.

**Jev RAG — Standard: 34.92 s; $0.002817; source pages: none; model turns: 2**

The provided passages do not contain information about the password for the Fairsource company payroll administrator account.

**Jev RAG — Thorough: 53.14 s; $0.014142; source pages: none; model turns: 5**

The provided document is the Ableton Live Reference Manual and does not contain any information about a Fairsource company payroll administrator account or its password.
