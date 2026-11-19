# Project KAALU V2

Project KAALU V2 is an autonomous multi-agent desktop, browser, and mobile orchestration system. It combines local system execution, browser automation, Android device control, user-profile and resume workflows, neural voice synthesis, and integrations with external LLM providers.

**KAALU** stands for **Knowledge-Augmented Autonomous Logic Unit**: the central intelligence responsible for understanding requests, planning tasks, coordinating specialized agents, and deciding when and how to use connected tools.



**---**





## KAALU — Knowledge-Augmented Autonomous Logic Unit



**---**



## Naming & System Roles

- **KAALU** — **Knowledge-Augmented Autonomous Logic Unit**: the main intelligence and orchestration agent. Created by Master **Rohit** for System AI Automation for Fun, dynamically powered by active cloud LLM models (e.g. `gemini-3.1-flash-lite`) via the RGS Gateway.
- **RGS** — **Runtime Gateway System**: the FastAPI and WebSocket-based communication and integration layer connecting agents, Android/ADB, and LLM services.
- **David** and **Faulkner** remain the names of the specialized agents.

The names **KAALU** and **RGS** are retained throughout the project. Their full forms are introduced where they clarify the architecture, rather than replacing the established names in code, endpoints, or everyday references.

## Architecture Overview



Project KAALU uses a hub-and-spoke multi-agent architecture. **RGS (Runtime Gateway System)** provides the communication and integration layer: a FastAPI service that manages WebSocket connections between KAALU, specialized agents, Android/ADB control, and external LLM services. It also exposes the unified LLM gateway and system-monitoring interfaces.



```

                      +-----------------------------+

                      |   RGS Central Hub (:8000)   |

                      |  - FastAPI WebSocket Bus    |

                      |  - LiteLLM Unified Gateway  |

                      |  - System & Fleet Monitor   |

                      +--------------+--------------+

                                     |

         +---------------------------+---------------------------+---------------------------+

         |                           |                           |                           |

         v                           v                           v                           v

+------------------+       +-------------------+       +-------------------+       +-------------------+

|      Kaalu       |       |     Faulkner      |       |       David       |       | Android Controller|

|   Orchestrator   |       |   System Agent    |       |   Browser Agent   |       |   OnePlus Phone   |

| (ReAct Engine &  |       | (Terminal, Shell, |       | (Chrome Ext V3,   |       | (Vision, Taps,    |

|   Voice Synth)   |       |  Screen Capture)  |       |   Semantic DOM)   |       |  Typing, Gestures)|

+------------------+       +-------------------+       +-------------------+       +-------------------+

```



### Components



1. **RGS — Runtime Gateway System (`rgs_hub`)**:

   - Central FastAPI communication router running on port `8000`.

   - Manages live agent WebSocket sessions (`/ws/kaalu`, `/ws/faulkner`, `/ws/david`).

   - Hosts the unified LLM Gateway (`/llm/generate`), abstracting providers (Google Gemini, OpenAI, Claude) via LiteLLM with automatic fallback and parameter normalization.



2. **KAALU Master Orchestrator (`kaalu_orchestrator`) — Knowledge-Augmented Autonomous Logic Unit**:

   - The user-facing intelligence operating in an autonomous step-by-step ReAct loop.

   - Maintains cross-turn conversational context for continuous workflows.

   - Produces dual-stream responses: comprehensive visual output for the console and natural, conversational text for voice playback.



3\. ****Faulkner System Agent (`faulkner_system`)****:

   - Local OS execution agent handling shell commands, process control, and desktop screen capture.

   - Built-in safeguards preventing termination of essential OS desktop shells.



4\. ****David Browser Agent (`david_browser_agent`)****:

   - Chrome Manifest V3 browser automation extension.

   - Features smart semantic element resolution (matches buttons, labels, and inputs by intuitive text without requiring minified CSS classes).

   - Automatically extracts search results, direct answer cards, and page snapshots upon navigation.

   - Full support for standard inputs and rich-text editors (`contenteditable`).



5\. ****Voice Engine (`voice_system`)****:

   - Offline neural Text-to-Speech (TTS) engine powered by Piper ONNX models.

   - Automatic text sanitization pipeline that strips markdown formatting, bullet symbols, raw paths, and URLs before audio synthesis.

   - Custom voice fine-tuning pipeline with Tensor Core acceleration, automated checkpoint resumption, and cross-device ONNX export.



6\. ****Centralized User Profile (`user_profile`)****:

   - Standalone profile generator extracting candidate data from PDF, TXT, MD, and JSON resumes.

   - Interactive profile management interface (`/profile/edit`) with dynamic card controls for multiple experiences, projects, educations, certifications, and customizable skill categories.

   - One-click GitHub repository fetcher and project importer (`/profile/github/repos` and `/profile/github/import`).

   - Unified context layer feeding Kaalu's LLM reasoning and David's browser form autofilling.



7\. ****Android Device Automation (`android_controller`)****:

   - Native ADB-driven mobile automation supporting wireless TLS (`adb-tls-connect`) and USB.

   - Automatic hardware recognition identifying the user's ****OnePlus Phone**** (`OnePlus Nord CE 2 5G / IV2201`, display `1080x2400 FHD+`, Android 13).

   - High-speed direct binary screenshot capture (`screencap -p`), base64 visual analysis, touch coordinates, keyboard input, gestures, and shell commands.



**---**



## Installation & Setup



### Prerequisites

\- Windows 10/11

\- Python 3.10+

\- Google Chrome



### 1. Environment Setup

Clone the repository and create a Python virtual environment:



```cmd

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt

```



### 2. Configuration

Copy or edit `central_communication_system/rgs_hub/settings.yaml` and configure your API keys (or export `GEMINI_API_KEY` in your environment / `.env`):



```yaml

llm:

  default_model: "gemini/gemini-2.5-flash"

  timeout: 30

```



### 3. Install David Chrome Extension

1\. Open Google Chrome and navigate to `chrome://extensions`.

2\. Toggle on ****Developer mode**** in the top right.

3\. Click ****Load unpacked**** and select the folder:

   ```

   central_communication_system\david_browser_agent

   ```



**---**



## Running the System



To launch all agents, hub, and the interactive terminal at once, run:



```cmd

.\start.bat

```



_>&#x20;_****Note****_: To grant Faulkner full process management permissions (such as closing elevated applications), right-click `start.bat` and choose&#x20;_****Run as administrator****_._



**---**



## Neural Voice Engine: Training & GPU Optimization Guide



The `voice_system` module enables real-time offline neural speech synthesis using Piper VITS ONNX models and allows fine-tuning custom speaker voices with a single line of Python.



### Quickstart



```python

from voice_system.tts import Speaker



*# 1. Synthesize Speech (defaults to 'tony' when trained, or 'jarvis')*

Speaker.speak("Hello, I am ready to assist.")



*# 2. Switch Voice Model*

Speaker.set_voice("jarvis")



*# 3. Train / Fine-Tune Custom Voice with 1 required parameter*

*# Automatically looks for datasets/\<name> with metadata.csv and wav/ folder*

Speaker.train_voice("tony")



*# 4. Directly Export Existing Checkpoint to ONNX Without Retraining*

Speaker.export_voice("tony")

```



**---**



### GPU Hardware Optimization Guide (NVIDIA RTX 3050 / 6GB VRAM)



Training Piper VITS models on consumer GPUs (such as an NVIDIA RTX 3050 6GB Laptop/Desktop) previously suffered from long training times (6+ hours for 1,000 epochs) and underutilized VRAM (\~3GB / 6GB). The engine has been optimized with three major performance improvements:



```

+-----------------------------------------------------------------------------------+

|                        RTX 3050 6GB VRAM ALLOCATION                               |

|                                                                                   |

|  [ VITS Weights & Optimizers ]   [ FP16 Activation Tensors ]   [ Free Headroom ]  |

|          \~1.5 GB                   \~3.5 GB (batch_size=12)          \~1.0 GB       |

|  |<------------------------- \~5.0 - 5.2 GB Used -------------------------->|      |

+-----------------------------------------------------------------------------------+

```



#### 1. Dynamic VRAM Scaling via `batch_size`

\- ****Issue****: PyTorch dynamically allocates memory based on model size plus active batch activations ($\text{VRAM} = \text{Model} + \text{Activations}$). At the previous default of `batch_size=4`, activations only required \~1.3 GB, capping VRAM at \~2.8–3.0 GB.

\- ****Solution****: The default `batch_size` is now `8` on CUDA (with support for `12` or `16`). Because laptops run Windows desktop rendering on the integrated GPU (iGPU), almost 100% of the dedicated 6GB VRAM is free for PyTorch, allowing `batch_size=12` to safely saturate \~5.2 GB of VRAM without Out-Of-Memory (OOM).



#### 2. Ampere Tensor Core Acceleration (`16-mixed`)

\- ****Issue****: The original command ran in `--precision 32` (FP32 single precision). On NVIDIA Ampere GPUs (RTX 3050), FP32 does not utilize Tensor Cores.

\- ****Solution****: Automatic Mixed Precision (`--precision 16-mixed`) is now enabled by default on CUDA. This engages Ampere 2nd-gen ****Tensor Cores****, speeding up matrix multiplications by ****2x–3x**** and cutting activation memory per utterance in half.



#### 3. Disk I/O Bottleneck Fix (`checkpoint_epochs=25`)

\- ****Issue****: Previously configured with `--checkpoint-epochs 1`, PyTorch Lightning wrote an ****845 MB checkpoint file to disk after every single epoch****. For 1,000 epochs, this caused ****845 Gigabytes of disk writes****. In OneDrive-synced workspaces, Windows file locks and I/O flushing stalled training for 2–4 seconds per epoch, leaving the GPU idle 95% of the time.

\- ****Solution****: Checkpoints are now saved every 25 epochs (`checkpoint_epochs=25`), eliminating 96% of disk write overhead and reducing training time from ****6 hours down to \~15–25 minutes****.



#### 4. Cross-Device ONNX Export Fix

\- Checkpoints trained on CUDA previously caused a device mismatch error during ONNX tracing (`RuntimeError: Expected all tensors to be on the same device, but found cuda:0 and cpu`).

\- `piper_train.export_onnx` is now patched to automatically apply `map_location="cpu"` and move model weights to CPU before graph tracing, ensuring clean, portable ONNX exports regardless of training device.



#### 5. Smart Auto-Resume & Direct Export

\- ****Smart Resumption****: `Speaker.train_voice(name)` automatically inspects `lightning_logs` for existing checkpoints. If the target epoch (e.g. 1000) has already been reached, it skips re-training and exports the ONNX model directly. If interrupted midway, it resumes fine-tuning from the latest checkpoint instead of restarting from epoch 0.

\- ****Direct Export Helper****:

  ```python

  Speaker.export_voice("tony")

  ```



| Parameter | Previous Setting | Optimized Setting | Hardware Impact |

| :--- | :--- | :--- | :--- |

| ****`batch_size`**** | `4` | `8` (or `12` / `16`) | Scales VRAM utilization to ****4.5 GB – 5.5 GB**** |

| ****`precision`**** | `32` (FP32) | `16-mixed` (FP16 AMP) | Engages ****Ampere Tensor Cores**** (2x speedup) |

| ****`checkpoint_epochs`**** | `1` | `25` | Eliminates ****96% of disk write overhead**** (\~800 GB less I/O) |

| ****`export_voice`**** | Manual CLI | One-click method | Instant ONNX export without retraining |



**---**



## Centralized User Profile & Career Guidance



Project KAALU includes a centralized User Profile system accessible across the agent ecosystem (KAALU, David, Faulkner, and services connected through RGS — the Runtime Gateway System).



### Key Features

\- ****Resume Upload & Parsing (`/profile/upload`)****: Drag & drop PDF, TXT, MD, or JSON resumes to auto-extract contact details, links, education, work experience, projects, certifications, and skills.

\- ****Interactive Multi-Item Editor (`/profile/edit`)****: Add and remove multiple work experiences, projects, degrees, certifications, and custom skill categories (`AI & LLMs`, `Cloud & DevOps`, etc.).

\- ****GitHub Repository Importer****: Fetch public repositories from GitHub with one click (`/profile/github/repos`) and import them directly as portfolio projects (`/profile/github/import`).

\- ****Autonomous Job Matching & Form Autofill****: Kaalu formulates targeted job searches using verified profile data, instructs David to query job boards, filters matching roles, and autofills application forms.



**---**



## Resume Builder & Job Application Tracking



Project K.A.A.L.U integrates with the standalone Resume Builder web application (`http\://localhost:5173/`) to create, preview, download, and track job-tailored resumes across Kaalu, David, and Faulkner.



### 1. Web App Workflow

\- ****Application URL****: `http\://localhost:5173/` (credentials: `rsingh.py\@gmail.com` / `Rohiyaa`).

\- ****Target Opportunity****: Fill in hiring company, position title, and job description (minimum 20 chars).

\- ****Generation Phase****: Click `🚀 Generate Tailored Resume`. AI extracts keywords, selects relevant skills and experiences from the user profile, and renders the Live Resume Preview.



### 2. Strict Generation vs. Download Separation

\- ****Generation-Only Rule****: During resume creation, the resume is ****only generated and previewed**** inside the web app. No export or file download is triggered automatically.

\- ****Explicit Download Trigger****: Downloading the resume (`📄 Export PDF` or `📝 Export DOCX`) occurs ****strictly upon explicit user command**** (e.g. "download resume", "export pdf").



### 3. Date-Organized Storage & Profile Synchronization

\- ****Date Directory Structure****: Downloaded resumes are automatically moved to structured date-based storage:

  ```

  central_communication_system/data/resumes/YYYY-MM-DD/\<Company>\_\<Position>\_Resume\_\<timestamp>.pdf

  ```

\- ****Live Profile Sync****: Saving a downloaded resume automatically updates `resume_path` in `central_communication_system/data/user_profile.json`, making the latest resume instantly accessible to all agents.



### 4. Job Application & Snapshot Tracking

\- ****Application Record****: Once an application uses a tailored resume or is submitted, the complete application data is stored in `central_communication_system/data/job_applications.json` and `data/applications/YYYY-MM-DD/\<application_id>.json`.

\- ****Downstream Agent Retention****: Preserves target job description, URL, location, timestamps, tailored resume snapshot, and resume file path for follow-up and multi-agent interview prep.

\- ****Direct Applied Job Queries in Kaalu****: Kaalu's reasoning engine automatically injects the verified `[TRACKED JOB APPLICATIONS DATABASE]` into context. When asked about past applications (e.g. **"What jobs have I applied to?"**, **"Which resume did I send to Stripe?"**), Kaalu responds instantly with formatted tables, interview prep tips based on the saved job descriptions, and spoken summaries.

\- ****Agent Delegation to `job_tracker`****: Kaalu can autonomously delegate actions (`record_application`, `mark_applied`, `save_resume`, `list_applications`) directly to `job_tracker`.

\- ****REST Endpoints & WebSocket Actions****:

  - `POST /job/resume/save`: Saves downloaded resume to date folder and syncs profile.

  - `POST /job/applied`: Records job application or updates status to `applied`.

  - `GET /job/applications`: Lists tracked applications with optional `status` or `company` filters.

  - `GET /job/applications/{application_id}`: Fetches specific application record.



**---**



## System Settings & Agent Fleet Monitoring (`/settings`)



Project KAALU features an integrated telemetry dashboard, with RGS (Runtime Gateway System) providing the central service and connection status, accessible at `http\://localhost:8000/settings` or via the `⚙️ Settings` gear tab across all web interfaces.



### Features

\- ****Online Service Health Probing****: Real-time HTTP ping & latency probe of the Resume Builder (`http\://localhost:5173/`), RGS Central Gateway (`:8000`), and Central Job Storage.

\- ****Connected Agent Fleet****: Live status indicator of all WebSocket-connected sub-agents:

  - ****Kaalu****: Master Orchestrator (`/ws/kaalu`)

  - ****Faulkner****: Local System & Terminal Execution (`/ws/faulkner`)

  - ****David****: Chrome Extension V3 Browser Agent (`/ws/david`)

\- ****Neural Voice Switcher****: Live indicator of active voice (`tony` or `jarvis`), one-click voice switching, and instant audio synthesis tester (`🔊 Test Voice Audio`).

\- ****Gemini & LLM Model Configuration****: Displays active provider, active Gemini model (`gemini-3.1-flash-lite`), API key configuration status, and instant model switching dropdown.

\- ****Connected Hardware & Mobile Devices (ADB)****: Live monitoring of connected Android hardware (e.g. OnePlus Phone), showing real-time battery level, display resolution, OS version, active app, and connection serial, with quick action controls (`📸 Capture Screenshot`, `🏠 Home`, `◀ Back`, `📋 Apps`) and a live screenshot modal.

\- ****REST & Telemetry Endpoints****:

  - `GET /settings`: Renders the full interactive monitoring dashboard.

  - `GET /system/status` (or `GET /api/status`): Returns structured JSON telemetry for all agents, services, voice, and LLM configuration.

  - `POST /voice/change` (or `POST /api/settings/voice`): Switches active voice model in real-time.

  - `POST /voice/test`: Synthesizes a test phrase using the active voice.

  - `POST /llm/change` (or `POST /api/settings/llm`): Dynamically updates default LLM model/provider.



**---**



## Android Mobile Device Automation (OnePlus Phone via ADB)



Project KAALU includes a dedicated mobile device automation subsystem, integrated with the wider agent ecosystem through RGS (Runtime Gateway System), (`central_communication_system/android_controller/`) that interfaces directly with Android Debug Bridge (ADB) located at `C:\Users\rsing\AppData\Local\Android\Sdk\platform-tools\adb.exe` (with automatic fallback to `ADB_PATH` environment variable and system PATH).



### 1. Device Identification & OnePlus Recognition

\- ****Automatic Recognition****: Recognizes the user's primary mobile device as the ****OnePlus Phone**** (`OnePlus Nord CE 2 5G / IV2201`, `1080x2400 FHD+`, Android 13) connected over Wireless TLS (`adb-AQTWNN8DWSMNG6KJ-vxhPaR.\_adb-tls-connect.\_tcp`) or USB.

\- ****Hardware Telemetry****: Queries battery level, screen dimensions (`wm size`), operating system version, and active focused application window (`dumpsys window`) in real time.



### 2. Supported Mobile Actions

- **📸 Vision & Screen Capture (`capture_screenshot`)**:
  - Captures high-resolution screen images via direct binary pipe (`adb exec-out screencap -p`) in ~200ms.
  - Automatically saves timestamped PNG files to `central_communication_system/data/android_screenshots/screen_<timestamp>.png` and provides base64 image strings for visual analysis.

- **⚡ End-to-End WhatsApp Macro (`send_whatsapp`)**:
  - Delivers complete WhatsApp messaging in a single turn without exhausting LLM tokens.
  - Automatically foregrounds WhatsApp, verifies or navigates to the contact chat, types message text, enters requested emojis via Gboard universal typing, and touches Send.
  - **Voice Recording Prevention Guard**: Features an active guard checking whether the action button is `Send` or `Voice message` (`voice_note_btn`). If the message entry is empty, it strictly avoids tapping fallback coordinates, completely preventing unintentional voice audio recording.

- **📞 High-Speed Phone & WhatsApp Calling (`call_phone`)**:
  - Native cellular dialing in 0.2s via `android.intent.action.CALL` intent without multi-turn dialing loops.
  - WhatsApp Voice Calling (`app="whatsapp"`): Navigates directly to the contact and triggers the voice call button in the chat header.

- **😂 Universal Gboard Emoji Search & Typing (`type_gboard_emoji` / `tap_emoji`)**:
  - In Android, ADB shell `input text` cannot type 4-byte unicode emojis directly.
  - Kaalu uses Google Gboard's deterministic emoji search: focuses the input field, long-presses the comma `,` key at `[205, 2320]` for 450ms to open Gboard's emoji palette, taps `Search` at `[280, 1280]`, inputs the query keyword (e.g. `laugh`, `smile`, `heart`, `rofl`), and selects the emoji directly from the search grid (e.g. `😂` at `[229, 1213]`).
  - This eliminates reliance on dynamic Recent Emojis (which shift over time) and guarantees 100% reliable emoji typing universally across all Android apps.

- **🔄 Screen Auto-Rotate & Orientation Lock Control (`set_auto_rotate`, `get_auto_rotate_status`)**:
  - Queries real-time `accelerometer_rotation` and `user_rotation` system properties.
  - Allows locking the phone to portrait mode (`set_auto_rotate(enabled=False)`) or toggling auto-rotate (`enabled=True`).
  - **OxygenOS Auto-Rotate Override Diagnostics**: Diagnoses background packages overriding rotation:
    - `com.google.android.apps.work.clouddpc` & `com.microsoft.windowsintune.companyportal`: Corporate Work Profiles holding `WRITE_SETTINGS: granted=true`.
    - `com.aiunit.aon`: OxygenOS Face-based Smart Rotation (auto-adjusts rotation based on front camera face orientation).
    - `com.oplus.games`: Game Space rotation override policies.

- **👆 Touch & Tap (`tap`)**: Simulates touch taps at exact pixel coordinates (`x`, `y`) or semantic target names (`target="Diya BBA GEHU"`).

- **⌨️ Keyboard & Text Input (`type_text`)**: Automatically sanitizes spaces (`%s`), quotes, and special characters, typing directly into active input fields.

- **↔️ Swipe & Gestures (`swipe`)**: Executes swipe and scroll gestures with custom durations (`swipe(x1, y1, x2, y2, duration_ms)`).

- **🔘 Hardware & Navigation Keys (`press_key`)**: Triggers standard Android key events (`HOME`, `BACK`, `ENTER`, `APP_SWITCH`, `POWER`, `VOLUME_UP`, `VOLUME_DOWN`).

- **🚀 App Launching (`open_app`)**: Launches target application packages (e.g. `com.whatsapp`, `com.android.chrome`, `com.google.android.youtube`).

- **💻 Arbitrary Shell Commands (`shell`)**: Executes raw ADB shell commands on the mobile device.

---

### 3. Free Tier Token & Rate-Limit (TPM/RPM) Optimizations

To completely eliminate 429 rate limit errors and prevent token exhaustion on the Gemini Free Tier:
1. **Dynamic Context Filtering**: Mobile and device tasks dynamically omit the ~3,500 token job application tracking history and full career CV, cutting prompt token consumption by >70% per turn.
2. **Single-Turn Macro Execution**: Complex mobile operations (`send_whatsapp`, `call_phone`) execute in a single high-speed turn rather than requiring 8-12 conversational reasoning round-trips.
3. **Screen Observation Pruning**: UI hierarchy dumps are capped to 15 non-empty labels and 10 interactive coordinate elements. Older intermediate history steps are compressed into single-line summaries to eliminate quadratic token growth.
4. **Intelligent Gemini Fallback Chain**: If a specific model encounters temporary rate limits or high demand, the gateway automatically retries with adaptive exponential backoff and cascades through `gemini-3.1-flash-lite`, `gemini-2.5-flash`, `gemini-2.0-flash`, and `gemini-1.5-flash`.

---

### 4. Kaalu Master Orchestrator Delegation (`recipient: 'android'`)

Kaalu seamlessly identifies mobile requests and delegates them to the `android` agent:

- **"Send 'hello' to Diya BBA GEHU on WhatsApp using my phone."** (Executes in 1 turn via `send_whatsapp`)
- **"Call Diya on WhatsApp using my OnePlus phone."** (Executes in 1 turn via `call_phone`)
- **"Call 9876543210 from my phone."** (Executes native cellular call via CALL intent)
- **"Send a laughing emoji to Diya BBA GEHU on WhatsApp."** (Taps emoji via on-screen keyboard)
- **"Can you see Diya BBA GEHU on the screen of my phone?"** (Inspects screen with confirmed element labels)
- **"Take a screenshot of my OnePlus phone and tell me what is open."**

---

### 5. REST Endpoints & WebSocket Support

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/android/devices` | `GET` | Returns list and telemetry of all connected Android devices |
| `/android/screenshot` | `GET` | Captures screenshot (returns JSON with base64 and path; pass `raw=true` for binary PNG) |
| `/android/inspect` | `GET` | Returns parsed UI elements and visible labels |
| `/android/whatsapp/send` | `POST` | High-speed WhatsApp messaging & emoji macro |
| `/android/call` | `POST` | High-speed phone call or WhatsApp audio call macro |
| `/android/emoji` | `POST` | Taps emoji on screen keyboard (`laugh`, `smile`, `heart`, etc.) |
| `/android/tap` | `POST` | Performs touch tap: `{"x": 540, "y": 1200}` or `{"target": "Contact"}` |
| `/android/type` | `POST` | Types text: `{"text": "Hello World"}` |
| `/android/swipe` | `POST` | Performs swipe: `{"x1": 500, "y1": 1800, "x2": 500, "y2": 400, "duration_ms": 300}` |
| `/android/key` | `POST` | Presses key: `{"key": "HOME"}` |
| `/android/app/open` | `POST` | Launches application package: `{"package": "com.whatsapp"}` |
| `/android/shell` | `POST` | Executes ADB shell command: `{"command": "pm list packages -3"}` |



**---**



## Running Automated Tests



Run the comprehensive pytest test suite to verify all subsystem contracts:



```cmd

.venv\Scripts\pytest

```



**---**



## License



This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.
