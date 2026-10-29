# LLM Models Directory

This directory holds GGUF model files for the LLM clinical refinement pipeline.
Files here are **not committed to git** (see `.gitignore`).

## Supported Models

The app allows selecting between LLM models dynamically from the UI or API:

| Model ID | Model Name | Quantization File | Size | RAM Footprint | Profile |
|---|---|---|---|---|---|
| `qwen2.5-1.5b` | **Qwen2.5-1.5B-Instruct** | `qwen2.5-1.5b-instruct-q4_k_m.gguf` | ~1.06 GB | ~1.1 GB | Default: High accuracy clinical reasoning & JSON extraction |
| `llama-3.2-1b-medical` | **Llama 3.2 1B Medical** | `Llama3.2-1B-Medical-Q4_KM.gguf` | ~770 MB | ~800 MB | Fast edge medical fine-tune |
| `qwen2.5-3b-medical` | **Qwen2.5 3B Medical** | `qwen2.5-3b-medical-instruct-q4_k_m.gguf` | ~1.84 GB | ~2.2 GB | Advanced clinical instruction & reasoning |

---

## Dynamic Switching in the App

- **UI**: Select the desired LLM in the **LLM Refiner** dropdown in the top header.
- **REST API**: 
  - `GET /api/llm/models` — list available models and download status
  - `POST /api/llm/select` — body `{"model_key": "qwen2.5-3b-medical"}`

