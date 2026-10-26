# Jev RAG POC: Fast, Standard and Thorough

This benchmark compares the three search modes exposed by this application. All application code, test questions, the benchmark runner and the recorded results belong to this repository.

## Scope and method

- **Jev RAG — Fast:** one hybrid keyword/embedding search; answer from the top five passages.
- **Jev RAG — Standard:** generate search terms, combine their search results, rank up to 40 candidates with Jev, and answer from five passages.
- **Jev RAG — Thorough:** an agent can search repeatedly with Jev, read whole pages and then answer; the application limits it to six model turns.

Run started: 2026-10-26T19:45:33.454222+01:00. Document: `data/live11-manual-en.pdf`. Questions: `benchmarks/cases/troubleshooting-live11.json`.

The same 6 questions, document index, and answer model were used for each mode. Mode order rotated for successive questions. Requests within each answer ran sequentially; indexing used the application's normal batching.

Answer model: `google/gemini-3.8-flash`. Embeddings: `openai/text-embedding-3-small`. Jev: `~typesafe/jev-latest`.

The runner calls the application functions directly. It does not automate browser interactions or test screenshots. Application source hashes and request-level usage are recorded in the JSON.

## Whole-answer measurements

| Jev RAG mode | Median time | Slowest | Mean cost per question | Estimated cost per 1,000 | Mean API requests |
|---|---:|---:|---:|---:|---:|
| Jev RAG — Fast | 16.20 s | 30.50 s | $0.007569 | $7.57 | 2.0 |
| Jev RAG — Standard | 18.18 s | 20.01 s | $0.007001 | $7.00 | 4.0 |
| Jev RAG — Thorough | 27.76 s | 30.52 s | $0.011760 | $11.76 | 10.7 |

Costs are provider-reported `usage.cost` for the complete answer pipeline: query embeddings, query expansion where used, reranking where used and answer generation. Initial indexing is separate. Per-1,000 figures extrapolate this small sample; they are not a bulk run or guaranteed prices.

Index preparation: 0.25 s, $0.000000, 1047 passages. Saved index reused: True.

Total known API cost for this run, including any indexing calls: $0.157978.

## Where Jev was used

Jev is the passage decision/ranking model. Gemini generates the final answer. The recorded requests show the following actual Jev API calls:

| Jev RAG mode | Jev decision API calls in this run |
|---|---:|
| Jev RAG — Fast | 0 |
| Jev RAG — Standard | 6 |
| Jev RAG — Thorough | 17 |

## Answer-quality limits

Expected-page matching is a retrieval/citation check, not an answer-correctness score. A document may contain the same instruction on several pages. No blinded answer-quality judging was performed. The sample and one timing run per question do not establish a general accuracy winner. Standard and Thorough change the retrieval workflow as well as using Jev, so their differences cannot be attributed entirely to the ranking model.

| Jev RAG mode | Answers returned | Expected page cited on answerable questions | Empty answers |
|---|---:|---:|---:|
| Jev RAG — Fast | 6/6 | 1/6 | 0 |
| Jev RAG — Standard | 6/6 | 5/6 | 0 |
| Jev RAG — Thorough | 6/6 | 6/6 | 0 |

Questions marked with no expected page are absence controls when present. Their full answers and source lists are preserved below; empty citations by themselves do not prove a correct refusal. If the case includes required-fact criteria, these need a separate source-grounded review; the timing runner does not automatically establish answer accuracy.

## Reproduce from this repository

[Benchmark instructions](../../benchmarks/README.md) include a synthetic handbook and questions that are committed in this repository. The default run builds its own PDF from that fixture, so it does not require a downloaded manual or another checkout.

Run this exact case from the repository root after making its PDF available at the recorded repository-local path:

```bash
sesame run OPENROUTER_API_KEY -- .venv/bin/python benchmarks/compare_search_modes.py --case benchmarks/cases/troubleshooting-live11.json --output-prefix docs/comparisons/repeated-jev-rag-modes
```

The Ableton manual case uses a copyrighted local PDF and is therefore not the default portable case. The PDF and generated indexes are ignored by Git. Its SHA-256 is recorded for comparison; the questions and all measured results are committed here.

[Machine-readable measured results](2026-10-26-jev-troubleshooting.json)

## All answers

### 1. I have existing MIDI clips playing in Session View. I want to overdub knob automation without adding more notes, including clips on tracks that are not armed. Later, moving a control by hand stops the recorded movement from playing. Give me the setup and a recovery procedure that preserves the recorded automation. Also explain why recording with a mouse stops differently from recording with a MIDI knob.

**Jev RAG — Fast: 9.78 s; $0.005587; source pages: none; model turns: 1**

The provided passages do not contain the information needed to answer the question. Specifically, they do not describe the setup for recording automation on unarmed tracks, nor do they provide a recovery procedure for restoring automation playback after manually moving a control.

**Jev RAG — Standard: 18.39 s; $0.006408; source pages: 355, 356, 357; model turns: 2**

**Setup:**
1. Enable the **Session Automation Recording** switch in the Record/Warp/Launch Preferences (this allows overdubbing automation into playing MIDI clips without adding notes, even on unarmed tracks).
2. Enable the **Automation Arm** button in the Control Bar.
3. Click the **Session Record** button to begin recording.

**Recovery Procedure:**
Moving an automated control while not recording temporarily overrides/deactivates the automation. To restore playback of the recorded automation without losing it, you can:
* Click the **Re-Enable Automation** button in the Control Bar,
* Right-click (Win) / CTRL-click (Mac) the parameter and select **Re-Enable Automation**, or
* Simply relaunch the Session clip containing the automation.

**Why Mouse Recording Stops Differently From a MIDI Knob:**
* **Mouse ("touch" behavior):** Recording stops immediately as soon as you release the mouse button.
* **MIDI Knob ("latch" behavior):** Recording continues as long as you move the controller; once you let go, recording keeps running until the end of the clip's loop and then automatically "punches out."

**Jev RAG — Thorough: 16.51 s; $0.006171; source pages: 355, 356, 357; model turns: 4**

### Setup for Overdubbing Automation Without Adding Notes (Including Unarmed Tracks)
1. **Enable the Session Automation Recording Preference**: Set the **Session Automation Recording** switch in the *Record/Warp/Launch* Preferences (this allows recording automation into all playing Session clips regardless of whether tracks are armed, preventing notes from being recorded into existing MIDI clips).
2. **Enable Automation Arm**: Turn on the **Automation Arm** button in the Control Bar.
3. **Keep Tracks Unarmed**: Do not arm the MIDI tracks, ensuring new notes will not be recorded.
4. **Trigger Session Record**: Click the **Session Record** button to begin recording automation while the clips are playing.

### Recovery Procedure for Overridden Automation
Moving an automated control by hand when not recording overrides the automation and turns off the control's automation LED. To restore the recorded automation without losing it, you can:
- Click the **Re-Enable Automation** button in the Control Bar (which lights up when automation is overridden) to reactivate all automation across the Set.
- [Right-click] (Win) / [CTRL-click] (Mac) the specific control and choose **Re-Enable Automation** from its context menu to restore only that parameter.
- Simply **relaunch the Session clip** that contains the automation.

### Why Mouse Recording Differs from MIDI Knob Recording
- **Mouse (“Touch” behavior)**: Recording stops immediately as soon as you release the mouse button.
- **MIDI Knobs/Faders (“Latch” behavior)**: Recording continues for as long as you adjust the hardware controller. When you let go, recording continues to the end of the clip’s loop and automatically “punches out” at the loop boundary.

### 2. My Set sends a Return track through an external analog reverb. I need an export of the master and separate tracks, including tracks that never touch the hardware. Explain the send/return setup and wet setting, which exports need real-time processing, how to deal with an old reverb tail before rendering, and what to do if the render keeps restarting after glitches.

**Jev RAG — Fast: 20.34 s; $0.007922; source pages: none; model turns: 1**

The provided passages do not answer the question because they do not contain information on what to do if the render keeps restarting after glitches.

**Jev RAG — Standard: 20.01 s; $0.007534; source pages: 90, 91, 434; model turns: 2**

Based on the provided passages:

1. **Send/Return Setup & Wet Setting:** Insert the **External Audio Effect** device on the return track. Set **Audio To** to the audio hardware outputs feeding your external reverb, and **Audio From** to the hardware inputs returning the signal into Live. Set the **Dry/Wet** control to **100 percent** for a return track setup.
2. **Real-Time vs. Offline Exports:**
   - Rendering the **Master output** will occur in **real time**.
   - When exporting **separate (single) tracks**, Live automatically traces signal flow: any tracks that do not route to an external device anywhere in their signal path will be rendered **offline**, whereas tracks accessing the external hardware will render in **real time**.
3. **Handling an Old Reverb Tail:** Live pauses before starting a real-time render to wait for external devices to become silent (defaulting to 10 seconds). If you have a long reverb tail, you can increase this wait time by entering a larger number in the number box (or click "Skip" if the device is already silent).
4. **Restarts Due to Glitches/Drop-outs:** If "Auto-Restart on drop-outs" is enabled, Live restarts rendering from the beginning when glitches occur. If restarts keep happening, close other running applications to free up more CPU/processing power for rendering.

**Jev RAG — Thorough: 17.28 s; $0.004869; source pages: 90, 91, 434; model turns: 3**

Based on the manual, here is how to handle your setup and rendering:

1. **Send/Return Setup & Wet Setting:**
   Use the **External Audio Effect** device in your Return track. In this device, use the *Audio To* chooser to route audio out to your hardware reverb, and the *Audio From* chooser to bring the processed signal back into Live. Set the device's **Dry/Wet control to 100 percent** when using it in a return track.

2. **Real-Time Processing for Exports:**
   - **Master Output:** Renders in real time because the set contains an external device routing to hardware.
   - **Separate Tracks:** Live automatically traces each track’s signal flow. Tracks that do not route to an external device anywhere in their signal path are rendered **offline**. Any tracks that do access external devices are then rendered in **real time**.

3. **Dealing with an Old Reverb Tail Before Rendering:**
   When rendering in real time, Live displays a *"Waiting for External Devices to Become Silent"* prompt, which defaults to waiting ten seconds for external sounds to fade out. If your reverb tail lasts longer, you can **increase the wait time by typing a new number** into the number box (or click "Skip" if there is no residual sound).

4. **Handling Repeated Restarts After Glitches/Drop-outs:**
   Real-time rendering can trigger drop-outs (small gaps or audio glitches), causing Live to restart from the beginning if *Auto-Restart on drop-outs* is enabled. If restarts keep happening, **close other running applications** to free up CPU processing power for the render.

### 3. I am slowing down and transposing a complete stereo song containing drums, vocals and pads. Re-Pitch is changing the pitch with the speed, and Complex processing is stressing the CPU. Explain the relevant warp-mode tradeoffs and how I can reduce processing while keeping the option to edit later. If I move a frozen Arrangement clip with a long reverb decay, what must move with it? Do not promise a specific quality or CPU improvement on my machine.

**Jev RAG — Fast: 17.22 s; $0.008751; source pages: none; model turns: 1**

The provided passages do not contain information about what must move when moving a frozen Arrangement clip with a long reverb decay, so they do not fully answer the question.

**Jev RAG — Standard: 17.97 s; $0.007675; source pages: 189, 190, 823, 824; model turns: 2**

**Warp-Mode Tradeoffs:**
• **Re-Pitch Mode:** Adjusts playback rate to stretch audio rather than time-stretching independently. Pitch changes directly with speed, and the Transpose and Detune controls have no effect.
• **Complex Mode:** Designed specifically for composite signals combining beats, tones, and textures (such as complete songs). However, it is CPU-intensive, using roughly ten times the processing resources of other warp modes.
• **Complex Pro Mode:** Also suited for whole songs and polyphonic textures and allows formant preservation when transposing, but requires even more CPU power than Complex Mode.
• **Tones and Texture Modes:** Tailored to specific elements (clear monophonic pitch contours or ambiguous textures/pads, respectively) rather than composite mixes containing drums, vocals, and pads.

**Reducing Processing While Retaining Editability:**
• **Freeze the track:** You can freeze tracks that use Complex Mode to free up CPU resources. Freezing keeps editing options open, as you can still perform many clip and mixer edits, or choose *Unfreeze Track* from the Edit menu at any time to modify clip or device settings and re-freeze when finished.

**Moving a Frozen Arrangement Clip with Reverb Decay:**
• Reverb tails appear in the Arrangement View as separate, crosshatched "temporary" clips adjacent to the original clip. When moving the frozen clip, you must also select the second, frozen tail clip so the two move together.

**Jev RAG — Thorough: 30.52 s; $0.016059; source pages: 188, 189, 190, 823, 824; model turns: 6**

**Warp-Mode Tradeoffs:**
- **Re-Pitch Mode:** Adjusts playback rate to stretch/compress audio (speeding up or slowing down changes pitch proportionally, like a variable-speed turntable). Transpose and Detune controls have no effect in this mode.
- **Complex Mode:** Designed specifically for composite signals combining beats, tones, and textures (such as complete songs). However, it is CPU-intensive, requiring approximately ten times the CPU resources of other warp modes.
- **Complex Pro Mode:** Offers a variation of the Complex algorithm that also works well for polyphonic textures and whole songs (offering formant and envelope adjustments), but at an even higher increase in CPU usage.
- **Other Modes (Beats, Tones, Texture):** These consume far fewer resources than Complex/Complex Pro, but are tailored to specific material types:
  - *Beats Mode* is optimized to preserve transients for rhythmic material (e.g., drum loops).
  - *Tones Mode* works for signals with a clear pitch contour (e.g., vocals, monophonic instruments, basslines), but can introduce audible repetitions depending on grain size.
  - *Texture Mode* is designed for sound textures with ambiguous pitch contours (e.g., polyphonic orchestral music, noise, atmospheric pads) using unaltered grain sizes and randomness (fluctuation).

**Reducing CPU Processing While Keeping Future Editing Options:**
- You can **Freeze** the track (`Freeze Track` command). Freezing renders the track's audio to conserve CPU resources while retaining clip and arrangement editing capabilities (such as editing, cutting, copying, duplicating, trimming, and editing mixer automation). When you need to adjust clip warping or device settings, you can simply select `Unfreeze Track` from the Edit menu.

**Moving a Frozen Arrangement Clip with a Long Reverb Decay:**
- Live creates a separate, adjacent “temporary” clip in the Arrangement representing the frozen reverb tail (shown as a crosshatched region extending beyond the clip).
- When moving the frozen clip, you must select and move the **second, frozen tail clip along with it** so the two remain together.

### 4. I am playing a monitored input live while the Set contains latency-producing plug-ins and return effects. I want a more responsive monitored performance, and I also want to record the Master output into a new Session audio clip. Explain the monitoring latency/synchronization tradeoff, the resampling routing and recording steps, whether the recording track feeds itself into that recording, and where the audio is stored before and after saving the Set.

**Jev RAG — Fast: 15.19 s; $0.008130; source pages: none; model turns: 1**

The provided passages do not contain information about whether the recording track feeds itself into that recording, nor where the audio is stored before and after saving the Set. Therefore, the passages do not fully answer the question.

**Jev RAG — Standard: 13.38 s; $0.007183; source pages: 259, 297, 328; model turns: 2**

**Monitoring Latency vs. Synchronization Tradeoff**
When Device Delay Compensation is active, you can enable the **Reduced Latency When Monitoring** option in the Options menu for a more responsive performance.
- **When enabled:** Tracks with input monitoring on achieve the lowest possible latency, but they may be out of sync with other tracks in your Set (such as Return tracks, which remain delay compensated).
- **When disabled:** All tracks remain in sync, but input-monitored tracks may experience higher latency.

**Resampling Routing and Recording Steps**
1. On an audio track, select **Resampling** in its Input Type chooser to route the Master output into that track.
2. Mute, solo, or adjust the tracks feeding the Master output, using the Master Volume meter to achieve optimal levels without clipping.
3. Arm the track and record into any of its empty Session clip slots.

**Self-Feedback / Recording Track Output**
The recording track does **not** feed itself into the recording; its own output is suppressed while resampling takes place and will not be included in the recorded audio.

**Storage Location Before and After Saving**
- **Before saving the Set:** The recorded samples are kept at the location specified by the **Temporary Folder** (set in Preferences under the File/Folder tab).
- **After saving the Set:** The samples are stored within the current Set’s Project folder under **Samples/Recorded**.

**Jev RAG — Thorough: 27.96 s; $0.011567; source pages: 259, 328; model turns: 5**

Based on the manual:

### 1. Monitoring Latency / Synchronization Tradeoff
When **Delay Compensation** is active in the Options menu, you can enable the **Reduced Latency When Monitoring** option in the Options menu:
* **When enabled:** Input-monitored tracks achieve the lowest possible latency for a responsive live performance, but they may be out of sync with other tracks in your Set (such as Return tracks, which remain delay compensated).
* **When disabled:** All tracks remain fully synchronized, but input-monitored tracks may experience higher latency.

### 2. Resampling Routing and Recording Steps
To record the Master output into a new Session audio clip:
1. On an audio track, select **“Resampling”** in its **Input Type** chooser to route the Master output to that track.
2. Adjust, mute, or solo the tracks feeding the Master output, and check the Master Volume meter to achieve the highest level possible without clipping.
3. Arm the track for recording.
4. Record into any of the armed track's empty Session clip slots (e.g., by clicking an empty slot's Clip Record button or using the Session Record button).

### 3. Track Feedback During Resampling
The recording track's own output is **suppressed** while resampling takes place, so it **will not feed itself into the recording** or be included in it.

### 4. Storage Location of the Audio
* **Before saving the Set:** The recorded resampled audio remains at the location specified by the **Temporary Folder**.
* **After saving the Set:** The audio is stored within the current Set's **Project folder**, under `Samples/Recorded`.

### 5. I saved my Set under a new name in a different project folder and now want to send it to a collaborator. It still uses samples from another project and a large third-party instrument the collaborator does not own. I want their copy to play, but I want to retain the original instrument and editability in my own copy. Explain why sending only the .als is insufficient, how to collect the sample dependencies, and the difference between freezing and flattening for this handoff.

**Jev RAG — Fast: 30.50 s; $0.009211; source pages: none; model turns: 1**

The provided passages do not contain information to answer the question, as they do not mention freezing or flattening.

**Jev RAG — Standard: 18.86 s; $0.007078; source pages: 103, 106, 824, 831; model turns: 2**

**Why sending only the .als is insufficient:**
A Live Set (`.als`) file only references sample locations rather than containing the actual audio files. Because the Set was saved in a new project folder without its samples, it is still referencing files from the original project. If only the `.als` file is sent or the original project is not present on the collaborator's computer, the Set will be missing samples and have broken file references [c114, c118].

**How to collect sample dependencies:**
You can copy external dependencies into the Set's project folder using the File Manager:
1. Choose the **Manage Files** command from the **File** menu.
2. Click the **Manage Set** button.
3. Unfold the triangular-shaped fold button in the **External Files** section to collect/copy the files into the project folder [c118].

**Difference between Freezing and Flattening:**
* **Freezing:** Renders the track's audio output into freeze files so that a computer lacking the instrument or device can still play the Set, while retaining the original clips, devices, and settings intact (allowing you to unfreeze and edit them later) [c994].
* **Flattening:** Completely and permanently replaces the original clips and devices with the rendered audio files [c994, c1003].

To retain your original instrument and editability in your copy while enabling your collaborator to play the track, you should freeze the track rather than flatten it [c994].

**Jev RAG — Thorough: 30.31 s; $0.012384; source pages: 65, 106, 107, 823, 824; model turns: 6**

**Why sending only the .als file is insufficient:**
A Live Set (`.als`) file saves clip settings, device parameters, and positions, but audio clips only reference their corresponding sample files on disk rather than containing them directly. If the referenced samples reside in another project or disk location, sending only the `.als` file will result in broken file references (missing samples) on your collaborator’s computer. In addition, an `.als` file does not embed third-party plug-ins/instruments; if the collaborator does not own the third-party instrument, their computer will lack the device required to play back that track.

**How to collect the sample dependencies:**
You can copy external samples directly into your Set's Project folder using either of the following methods:
1. **Collect All and Save shortcut:** Select **Collect All and Save** from the **File** menu to gather and copy all referenced external files into the Set's Project folder.
2. **File Manager:** Choose **Manage Files** from the **File** menu, click the **Manage Set** button, unfold the **External Files** section, select which locations to collect (such as files from other Projects), and click the File Manager's **Collect and Save** button.

**Difference between Freezing and Flattening for this handoff:**
- **Track Freeze:** Renders the track’s audible result into temporary 32-bit audio "freeze files" (stored under `Samples/Processed/Freeze` upon saving). This allows computers lacking the required devices/plug-ins to play back the track while keeping the original devices, clip data, and settings intact. Because freezing can be undone at any time via **Unfreeze Track**, you retain the original instrument and full editability.
- **Flatten:** Available from the Edit menu, flattening permanently and completely replaces the original clips and devices with the audio files created by freezing. If you flatten the track, you lose the original instrument and device parameters, preventing you from returning to the original instrument state and making device adjustments.

Therefore, for this handoff, **freezing** the third-party instrument track (and running Collect All and Save) allows your collaborator to hear and play the track without owning the plug-in, while preserving the original instrument and editability for you to unfreeze whenever needed.

### 6. An External Audio Effect on my return track is late. Sometimes I connect the hardware digitally and sometimes through analog I/O, and I change sample rates between projects. The Hardware Latency control is currently disabled. Tell me what enables that control, which units preserve the intended compensation in each connection type, and how to handle sample-level fine tuning on the analog connection. The processor model and measured round-trip delay are unknown: give the exact compensation value if the manual supports one, otherwise state what still has to be measured.

**Jev RAG — Fast: 12.30 s; $0.005813; source pages: 328, 435; model turns: 1**

Based on the manual:

- **Enabling the control:** Check the "Delay Compensation" option in the Options menu. When this option is unchecked, the Hardware Latency slider is disabled.
- **Preserving compensation across sample rates:**
  - **Digital connection:** Use **samples**, which ensures the specified number of samples is retained when changing sample rates.
  - **Analog connection:** Use **milliseconds**, which ensures the specified amount of time is retained when changing sample rates.
- **Sample-level fine tuning for analog connections:** You can temporarily switch to samples to "fine tune" the latency for the lowest possible delay, but you must switch back to milliseconds before changing your sample rate.
- **Compensation value / measurement:** The manual does not provide an exact compensation value because hardware effects introduce latency that Live cannot automatically detect. The actual latency/delay introduced by your external hardware must still be measured (the manual directs users to the "Driver Error Compensation" lesson to accurately set this up).

**Jev RAG — Standard: 13.23 s; $0.006127; source pages: 435; model turns: 2**

Based on the provided manual passages:

- **What enables the control:** Check the **Delay Compensation** option in the **Options** menu (the Hardware Latency slider is disabled if this option is unchecked).
- **Units for each connection type:**
  - **Digital connection:** Use **samples**, which ensures the number of samples is retained when changing the sample rate.
  - **Analog connection:** Use **milliseconds**, which ensures the amount of time specified is retained when changing the sample rate.
- **Handling sample-level fine-tuning on analog connections:** You can adjust the latency in **samples** for finer control to achieve the lowest possible latency, but you must **switch back to milliseconds** before changing the project's sample rate.
- **Compensation value:** The manual does not provide an exact compensation value because external hardware latency cannot be automatically detected by Live. The delay introduced by the external hardware still has to be measured/set up (the manual directs you to the "Driver Error Compensation" lesson for instructions on how to accurately set up latency compensation).

**Jev RAG — Thorough: 27.55 s; $0.019508; source pages: 435; model turns: 6**

Based on the manual:

1. **Enabling the Hardware Latency control:**
   The Hardware Latency slider is disabled if the **Delay Compensation** option is unchecked in the **Options menu**. Checking **Delay Compensation** will enable the control.

2. **Units that preserve compensation when changing sample rates:**
   * **Digital connection:** Use **samples** (this ensures the specified number of samples is retained when changing sample rates).
   * **Analog connection:** Use **milliseconds** (this ensures the amount of time specified is retained when changing sample rates).

3. **Sample-level fine tuning on the analog connection:**
   Because adjusting in samples provides finer control, you can switch to samples to "fine tune" the latency to achieve the lowest possible latency. However, you must **switch back to milliseconds before changing your sample rate**.

4. **Exact compensation value / what still has to be measured:**
   The manual does **not** provide a fixed compensation value, because hardware effects introduce latency that Live cannot automatically detect. The exact latency introduced by the external hardware delay must still be measured (the manual directs users to the built-in **"Driver Error Compensation" lesson** for instructions on accurately setting up latency compensation for your hardware).
