# Offline application setup

The citizen flow is English-only and runs its AI features on this computer. It uses Ollama for the dialogue model and OpenAI Whisper `small.en` for editable English transcripts. Both model files must be present once; after setup, intake requests use only the local Ollama service and local Python packages.

## Model files

- Ollama: `qwen2.5:3b` (about 1.9 GB). Install Ollama, then run `ollama pull qwen2.5:3b` once.
- Whisper: `small.en.pt` (about 484 MB). First-time download is verified and cached by Whisper under the user model cache.
- The scikit-learn classifier is loaded from `models/`.

The launcher warms Ollama when the first screen opens so model loading can overlap the user's reading time. Warm responses were measured at about 1.1 seconds on this computer; the first cold request took about 11 seconds.

## Start

```powershell
python scripts/run_offline.py
```

Open `http://127.0.0.1:8503`. Start Ollama before launching. The launcher fixes the provider to local Ollama, points it to loopback, and selects English Whisper. If `.venv-gpu` exists, the launcher uses it automatically. Otherwise it falls back to CPU.

The citizen site and stylesheets contain no remote font or script dependencies. The investigator workspace remains available at `/officer`.

## Speech notes

The first run downloads Whisper if it is not already installed in the user cache. An optional isolated environment can enable the RTX 2050 for Whisper while keeping the system Python environment untouched. It requires several GB of disk space for CUDA-enabled PyTorch. The launcher chooses `.venv-gpu` automatically once it is installed. Review the transcript before adding it to the complaint. The intake now preserves Whisper's original words instead of silently replacing uncertain speech with bank names or transaction terms. High no-speech segments are filtered so silence cannot become copied prompt text.

## Model limitations

The LLM helps with short acknowledgements; the application rules choose one follow-up question at a time, and the classifier suggests the complaint category. Validate classifications against reviewed cases before operational use. The selected category and the classifier prediction are recorded separately if the user changes the suggestion. Statute mapping is a lookup table that must be maintained and reviewed.
