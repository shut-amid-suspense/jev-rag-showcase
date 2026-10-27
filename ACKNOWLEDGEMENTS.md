# Sources and dependencies

- **Ableton Live 11 Reference Manual:** the source corpus for the recorded manual retrieval and troubleshooting experiments. The copyrighted manual is not included; its expected content fingerprint and the frozen questions are recorded.
- **SQuAD v2:** the source for the historical retrieval experiment in `squad_eval.py`. The original dataset is not included. The script and recorded results identify that experiment separately from the new troubleshooting diagnostic.
- **Synthetic support handbook:** fictional material included in `benchmarks/fixtures/` and the generated demo PDF in `examples/`. It is a portable functional example, not the corpus used to claim hard-task accuracy.
- **Gradio and PyMuPDF:** application dependencies installed through `requirements.txt`. They are not vendored into this repository; their package metadata and upstream projects provide their own terms and attribution.
- **OpenRouter, Jev, Gemini and optional Cerebras/Qwen:** external model services used by the application. No model weights or provider credentials are bundled.
