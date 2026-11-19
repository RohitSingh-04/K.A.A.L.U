# Project KAALU V2

Project KAALU V2 is an autonomous multi-agent desktop, browser, and mobile orchestration system. It combines local system execution, browser automation, Android device control, user-profile and resume workflows, neural voice synthesis, and integrations with external LLM providers.

**KAALU** stands for **Knowledge-Augmented Autonomous Logic Unit**: the central intelligence responsible for understanding requests, planning tasks, coordinating specialized agents, and deciding when and how to use connected tools.



---





## KAALU — Knowledge-Augmented Autonomous Logic Unit



---



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

- Windows 10/11
- Python 3.10+
- Node.js & npm (for Resume Builder web frontend)
- Google Chrome

---

### 1. Download Resume Builder (Companion Web App)

Project KAALU integrates directly with the **CareerForge AI / Resume Builder** application (`http://localhost:5173/`). For seamless integration and automated unified startup, first clone the Resume Builder repository into the **same parent directory** alongside `Project-Kaalu-V2`:

- **Repository Link**: [https://github.com/RohitSingh-04/AI-Resume-Builder.git](https://github.com/RohitSingh-04/AI-Resume-Builder.git) *(or `https://linkedin.com/RohitSingh-04/AI-Resume-Builder.git`)*

```cmd
# 1. Navigate to the parent directory containing Project-Kaalu-V2 (e.g. Desktop or your development workspace):
cd ..

# 2. Clone the Resume Builder into the same folder:
git clone https://github.com/RohitSingh-04/AI-Resume-Builder.git Resume_Builder_V2
```

**Directory Layout:**
```
Parent_Folder/
├── Project-Kaalu-V2/
└── Resume_Builder_V2/      <-- Cloned AI Resume Builder repository (or AI-Resume-Builder/)
```
*(Both folder names `Resume_Builder_V2` and `AI-Resume-Builder` are automatically detected by `start_with_RB.bat`)*

---

### 2. Environment Setup (Project Kaalu)

Navigate into `Project-Kaalu-V2` and create your Python virtual environment:

```cmd
cd Project-Kaalu-V2
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

### 3. Configuration

Copy or edit `central_communication_system/rgs_hub/settings.yaml` and configure your API keys (or export `GEMINI_API_KEY` in your environment / `.env`):

```yaml
llm:
  default_model: "gemini/gemini-2.5-flash"
  timeout: 30
```

---

### 4. Install David Chrome Extension

1. Open Google Chrome and navigate to `chrome://extensions`.
2. Toggle on **Developer mode** in the top right.
3. Click **Load unpacked** and select the folder:
   ```
   central_communication_system\david_browser_agent
   ```

---

## Running the System

You have two launch options:

### Option A: Complete System with Resume Builder (Recommended)
Launches the full CareerForge AI Resume Builder (Vite frontend on `http://localhost:5173` and FastAPI backend on `http://localhost:8005`) together with Project Kaalu (RGS Central Hub on `:8000`, Faulkner System Agent, and Kaalu Master Orchestrator):

```cmd
.\start_with_RB.bat
```

### Option B: Project Kaalu Standalone
Launches only the Project Kaalu agent ecosystem (RGS Hub `:8000`, Faulkner, and Kaalu terminal):

```cmd
.\start.bat
```

*> **Note**: To grant Faulkner full process management permissions (such as closing elevated applications like Task Manager), right-click `start_with_RB.bat` or `start.bat` and choose **Run as administrator**.*



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



Project K.A.A.L.U integrates with the standalone [CareerForge AI / Resume Builder](https://github.com/RohitSingh-04/AI-Resume-Builder.git) web application (`http://localhost:5173/`) to create, preview, download, and track job-tailored resumes across Kaalu, David, and Faulkner. Keep the repository in the same parent folder alongside `Project-Kaalu-V2` to launch both systems seamlessly via `start_with_RB.bat`.



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

Project KAALU includes a dedicated mobile device automation subsystem (`central_communication_system/android_controller/`) integrated with the wider agent ecosystem through RGS (Runtime Gateway System). It interfaces directly with Android Debug Bridge (ADB) located at `C:\Users\rsing\AppData\Local\Android\Sdk\platform-tools\adb.exe` (with automatic fallback to `ADB_PATH` environment variable and system PATH).

---

### 1. Connecting Your Android Phone (OnePlus Setup Guide)

#### Prerequisites
1. **ADB Installation**: Ensure ADB is present at `C:\Users\rsing\AppData\Local\Android\Sdk\platform-tools\adb.exe` or available in your system PATH.
2. **Enable Developer Options**:
   - On your OnePlus phone, go to **Settings > About Device > Version**.
   - Tap **Build Number** 7 times until you see the confirmation: *"You are now in Developer mode!"*.
3. **Enable Debugging Settings**:
   - Navigate to **Settings > Additional Settings > Developer Options**.
   - Enable **USB Debugging**.
   - Enable **Wireless Debugging** (for Wi-Fi / cable-free connection).
   - Enable **Disable Permission Monitoring** (recommended for OxygenOS/ColorOS to allow ADB touch and keyboard input without permission popups).

---

#### Connection Method A: Wireless TLS Debugging (Default / Recommended)
Connect your phone and PC to the same Wi-Fi network without requiring a physical USB cable:
1. On your phone, go to **Settings > Additional Settings > Developer Options > Wireless Debugging**.
2. Tap **Pair device with pairing code**. Note the IP address, pairing port (e.g. `192.168.1.50:37123`), and the 6-digit Wi-Fi pairing code.
3. Open your PC terminal and pair:
   ```cmd
   adb pair <IP_ADDRESS>:<PAIRING_PORT> <6_DIGIT_CODE>
   ```
4. Look at the main *Wireless Debugging* screen for the active connection IP and port (e.g. `192.168.1.50:41255`). Connect to it:
   ```cmd
   adb connect <IP_ADDRESS>:<PORT>
   ```
5. Verify the connection:
   ```cmd
   adb devices -l
   ```
   *Expected output:*
   ```text
   List of devices attached
   adb-AQTWNN8DWSMNG6KJ-vxhPaR._adb-tls-connect._tcp   device product:OP555BL1 model:IV2201 device:OP555BL1 transport_id:1
   ```

---

#### Connection Method B: High-Speed USB Connection
1. Connect your phone to your PC via a USB-C data cable.
2. When the USB notification appears, choose **File Transfer** (MTP).
3. On the phone screen, accept the prompt: **"Allow USB debugging?"** and check **"Always allow from this computer"**.
4. Verify the attached device:
   ```cmd
   adb devices -l
   ```

---

#### Live Telemetry & Device Monitoring in RGS Settings (`/settings`)
When an Android device is attached, navigate to `http://localhost:8000/settings` or click the **⚙️ Settings** gear icon in the web interface:
- **Automatic Device Recognition**: Recognizes your phone as the **OnePlus Phone** (`OnePlus Nord CE 2 5G / IV2201`, `1080x2400 FHD+`, Android 13).
- **Real-Time Telemetry**: Queries battery level (%), display dimensions, Android version, connection transport (Wireless TLS or USB), and the active focused package/activity (`dumpsys window`).
- **Hardware Quick Actions**:
  - `📸 Capture Screenshot`: Grabs a high-resolution screenshot and renders a live interactive preview modal.
  - `🏠 Home`: Simulates pressing the physical Home key.
  - `◀ Back`: Simulates pressing the physical Back key.
  - `📋 Apps`: Opens the Recent Apps switcher.



### 2. Complete Commands Reference

Project KAALU provides 4 complementary ways to control connected mobile devices:

#### A. Kaalu Natural Language & Voice Commands
Speak or type these instructions directly into the Kaalu terminal (`start.bat`) or over voice:

| Intent / Goal | Natural Language Prompt Example | Action Taken by Kaalu |
| :--- | :--- | :--- |
| **Call Contact by Name** | `"call Mom"` / `"call Diya on my phone"` | Resolves contact name to phone number in contacts database and dials directly on phone via Android `CALL` intent in 0.2s |
| **Windows Phone Link Call** | `"call her using phone link"` / `"call Mom via Microsoft Phone Link"` | Delegates to **Faulkner**; resolves contact, launches Phone Link on Windows desktop, and dials via `tel:<number>` |
| **Open Phone Link** | `"open phone link on my PC"` / `"launch link to windows"` | Delegates to **Faulkner**; opens Microsoft Phone Link app (`Microsoft.YourPhone_8wekyb3d8bbwe!App`) on Windows desktop |
| **Close Phone Link Window** | `"close the phone link don't terminate it from task manager"` / `"remove phone link from taskbar"` | Delegates to **Faulkner**; dispatches `WM_CLOSE` / `CloseMainWindow()` to close window and remove it from taskbar without terminating background process |
| **Cellular Phone Call** | `"call 9876543210 from my phone"` | Native cellular dial in 0.2s via Android `CALL` intent |
| **WhatsApp Audio Call** | `"call Diya on WhatsApp using my OnePlus phone"` | Opens chat and triggers voice call button from chat header |
| **Answer Phone Call** | `"answer the phone"` / `"accept call"` | Accepts incoming phone or WhatsApp call via CALL keyevent & headset hook |
| **End Active Call** | `"hang up call"` / `"end call on phone"` | Hangs up active call via ENDCALL keyevent |
| **Send SMS Message** | `"send SMS to Mom saying I will be home soon"` | Resolves contact name, prefills message via `SENDTO` intent, verifies and taps Send |
| **Read SMS Inbox** | `"read my recent text messages"` / `"what SMS did I receive?"` | Queries SMS inbox content provider and returns recent message texts and senders |
| **WhatsApp Message** | `"send 'hello' to Diya BBA GEHU on whatsapp using my phone"` | Opens WhatsApp, finds contact, types message, verifies and taps Send in 1 turn |
| **WhatsApp Emoji** | `"open whatsapp on phone and send laughing emoji to Project X group"` | Navigates to group, searches emoji via Gboard, taps `😂`, verifies Send |
| **Check Bluetooth** | `"check bluetooth on my phone"` / `"bluetooth status"` | Queries Bluetooth adapter status and lists all bonded/paired devices |
| **Toggle Bluetooth** | `"turn on bluetooth on phone"` / `"turn off bluetooth"` | Enables or disables Bluetooth adapter via native `cmd bluetooth_manager` |
| **Connect Bluetooth Device** | `"connect my phone to realme Buds"` | Enables Bluetooth, opens settings, and connects to specified paired earbuds/headphones/watch |
| **Screen Inspection** | `"can you see Diya BBA GEHU on the screen of my phone?"` | Dumps UI hierarchy and verifies contact labels |
| **Screen Capture** | `"take a screenshot of my OnePlus phone and tell me what is open"` | Binary screen capture in ~200ms with visual inspection |
| **Lock Rotation** | `"lock phone rotation to portrait mode"` | Programmatically sets `accelerometer_rotation=0` & `user_rotation=0` |
| **Rotation Status** | `"what is my phone rotation status?"` | Queries system auto-rotate setting and orientation lock |
| **Navigation** | `"go to home screen on my phone"` / `"press back on phone"` | Dispatches `input keyevent 3` (HOME) / `keyevent 4` (BACK) |
| **Launch Apps** | `"open YouTube on phone"` / `"launch Chrome on phone"` | Launches target app package via Android Launcher intent |

---

#### B. Python SDK (`AndroidDeviceManager`)
Import and invoke `AndroidDeviceManager` directly in custom automation scripts or test suites:

```python
from android_controller.manager import AndroidDeviceManager

mgr = AndroidDeviceManager()

# 1. Device Discovery & Hardware Telemetry
devices = mgr.list_devices_details()
details = mgr.get_device_details() # Returns brand, model, battery level %, resolution, active package

# 2. Vision & UI Hierarchy Inspection
res = mgr.capture_screenshot(save=True)  # Saves to data/android_screenshots/screen_<timestamp>.png
ui = mgr.inspect_screen()                # Returns visible_texts and interactive_elements with [x, y]
elem = mgr.find_element("Diya BBA GEHU") # Locates element bounding box and center coordinate

# 3. High-Speed Macro Actions (Single-Turn Execution)
# End-to-end WhatsApp messaging & emoji with voice recording prevention guard
mgr.send_whatsapp(contact="Project X", message="Hello team!", emoji="laugh", auto_send=True)

# Calling: Cellular (with automatic contact name resolution) or WhatsApp voice
mgr.call_phone(target="Mom", app="phone")             # Resolves 'Mom' to +918477873189 and dials in 0.2s
mgr.call_phone(target="9876543210", app="phone")      # Direct number dialing
mgr.call_phone(target="Diya BBA GEHU", app="whatsapp") # WhatsApp voice calling
mgr.answer_call()                                     # Answers incoming phone/WhatsApp call
mgr.end_call()                                        # Hangs up active call

# SMS Messaging & Inbox Reading
mgr.send_sms(target="Mom", message="On my way home", auto_send=True) # Prefills and sends SMS
sms_list = mgr.read_sms(limit=10)                    # Reads recent incoming SMS messages

# Contacts Search
contacts = mgr.search_contacts(query="Mom")          # Returns [{name, number, clean_number}]

# Bluetooth Device Management
bt_status = mgr.get_bluetooth_status()                # Queries state and lists all bonded devices
mgr.set_bluetooth(enabled=True)                       # Enables Bluetooth adapter
mgr.connect_bluetooth_device("realme TechLife Buds T100") # Connects to paired earbuds/device

# 4. Universal Gboard Emoji Search & Typing
# Opens Gboard, taps Search, types keyword ('laugh', 'smile', 'heart'), taps match, restores text mode
mgr.type_gboard_emoji(emoji="laugh")  # Types 😂 into active text field
mgr.type_gboard_emoji(emoji="heart")  # Types ❤️ into active text field

# 5. Screen Auto-Rotate & Orientation Lock
mgr.set_auto_rotate(enabled=False)    # Locks screen in portrait orientation
status = mgr.get_auto_rotate_status() # {"auto_rotate": False, "is_portrait_locked": True}

# 6. Touch, Typing, Gestures & Key Navigation
mgr.tap(target="Search")              # Semantic touch tap by visible label
mgr.tap(x=540, y=1200)                # Coordinate touch tap
mgr.type_text("Hello World", clear=True)
mgr.swipe(x1=500, y1=1800, x2=500, y2=400, duration_ms=300) # Scroll down gesture
mgr.press_key("HOME")                 # "HOME", "BACK", "ENTER", "APP_SWITCH", "POWER", etc.
mgr.open_app("com.whatsapp")          # Launches package directly
mgr.shell("pm list packages -3")      # Arbitrary ADB shell command

# 7. Encrypted Phone Security & Unlock Device
# Saves unlock PIN/password encrypted with Windows DPAPI (machine and user account bound)
mgr.save_phone_pin(pin="123456")           # Encrypted and saved to data/device_credentials.json
status = mgr.get_credentials_status()      # {"configured": True, "cipher_method": "win32_dpapi"}
mgr.unlock_device()                        # Wakes screen, dismisses lockscreen, types PIN, submits ENTER
mgr.clear_phone_pin()                      # Safely removes stored credentials
```

---

#### C. REST API Endpoints (RGS Hub `:8000`)
The Runtime Gateway System exposes complete HTTP endpoints for programmatic mobile automation:

| Endpoint | Method | Request Payload / Query Params | Description |
| :--- | :--- | :--- | :--- |
| `/android/devices` | `GET` | — | Lists attached devices with full hardware telemetry & battery % |
| `/android/screenshot` | `GET` | `?raw=true` (optional) | Captures screenshot; returns JSON or raw binary PNG image |
| `/android/inspect` | `GET` | — | Dumps active screen UI hierarchy and interactive coordinates |
| `/android/whatsapp/send` | `POST` | `{"contact": "Diya", "message": "Hi", "emoji": "laugh", "auto_send": true}` | Single-turn WhatsApp message & emoji macro |
| `/android/call` | `POST` | `{"target": "Mom", "app": "phone"}` | Dials direct cellular call (with contact resolution) or WhatsApp call on phone |
| `/android/call/answer` | `POST` | — | Answers incoming phone or WhatsApp call via CALL keyevent / headset hook |
| `/android/call/end` | `POST` | — | Hangs up active call via ENDCALL keyevent |
| `/faulkner/phonelink/call` | `POST` | `{"target": "Mom"}` | Dials call through Microsoft Phone Link on Windows desktop via `tel:<number>` |
| `/faulkner/phonelink/open` | `POST` | — | Launches or brings Microsoft Phone Link to the front on Windows |
| `/faulkner/phonelink/close` | `POST` | — | Gracefully closes Phone Link window (simulating 'X' button) without killing background task |
| `/android/contacts` | `GET` | `?query=Mom` (optional) | Queries Android contacts database with name, number, and clean number |
| `/android/sms/send` | `POST` | `{"target": "Mom", "message": "Hello", "auto_send": true}` | Resolves contact name, prefills and sends SMS message |
| `/android/sms` | `GET` | `?limit=10` (optional) | Reads recent incoming SMS messages from the inbox |
| `/android/bluetooth` | `GET` | — | Queries Bluetooth adapter status and lists all bonded/paired devices |
| `/android/bluetooth` | `POST` | `{"enabled": true}` | Turns Bluetooth ON or OFF via `cmd bluetooth_manager` |
| `/android/bluetooth/connect` | `POST` | `{"device": "realme Buds"}` | Connects to specified paired Bluetooth earbuds/device |
| `/android/emoji` | `POST` | `{"emoji": "laugh"}` | Types emoji via Gboard deterministic search (`laugh`, `smile`, `heart`, etc.) |
| `/android/rotation` | `GET` | — | Returns `auto_rotate` state and `is_portrait_locked` boolean |
| `/android/rotation` | `POST` | `{"enabled": false}` | Sets auto-rotate (`false` locks portrait mode) |
| `/android/tap` | `POST` | `{"target": "Send"}` or `{"x": 540, "y": 1200}` | Performs touch tap by semantic label or exact coordinate |
| `/android/type` | `POST` | `{"text": "Hello", "target": "Message", "clear": false}` | Focuses input field and types text |
| `/android/swipe` | `POST` | `{"x1": 500, "y1": 1800, "x2": 500, "y2": 400}` | Executes swipe or scroll gesture |
| `/android/key` | `POST` | `{"key": "HOME"}` | Triggers Android key event (`HOME`, `BACK`, `ENTER`, etc.) |
| `/android/app/open` | `POST` | `{"package": "com.whatsapp"}` | Launches application package |
| `/android/credentials` | `GET` | — | Returns encryption and PIN configuration status without exposing secrets |
| `/android/credentials` | `POST` | `{"pin": "123456"}` | Safely encrypts and stores phone unlock PIN/password via Windows DPAPI |
| `/android/credentials` | `DELETE` | — | Clears stored phone unlock credentials |
| `/android/unlock` | `POST` | `{"pin": "123456"}` (optional) | Wakes screen and executes unlock sequence with saved PIN or override |
| `/android/shell` | `POST` | `{"command": "getprop ro.product.model"}` | Executes raw ADB shell command |

---

#### D. Essential ADB Commands Cheat Sheet
Run these directly in your command line or PowerShell if managing devices manually:

```cmd
# 1. Device Pairing & Connectivity
adb pair 192.168.1.X:<PAIRING_PORT> <PAIRING_CODE>
adb connect 192.168.1.X:<PORT>
adb devices -l
adb disconnect

# 2. Vision & Screen Dumps
adb exec-out screencap -p > screenshot.png
adb shell uiautomator dump /sdcard/window_dump.xml
adb shell cat /sdcard/window_dump.xml

# 3. Touch, Typing & Key Simulation
adb shell input tap 540 1200
adb shell input swipe 500 1800 500 400 300
adb shell input text "Hello%sWorld"
adb shell input keyevent 3     # HOME
adb shell input keyevent 4     # BACK
adb shell input keyevent 66    # ENTER
adb shell input keyevent 187   # RECENTS / APP_SWITCH

# 4. App & Activity Control
adb shell monkey -p com.whatsapp -c android.intent.category.LAUNCHER 1
adb shell am force-stop com.whatsapp
adb shell dumpsys window | grep -E "mCurrentFocus"
```

---

### 3. Subsystem Architecture & Safeguards

- **Universal Gboard Emoji Search**: Uses Google Gboard's deterministic emoji search (`Q Search` on Gboard) rather than dynamic Recent Emojis. This ensures that emojis like `😂` (laugh), `❤️` (heart), and `👍` (thumbs up) type reliably across all chat applications regardless of user history.
- **WhatsApp Voice Recording Prevention Guard**: When sending WhatsApp messages, Kaalu explicitly verifies that the Send button is visible before dispatching taps. If the input field is empty and WhatsApp displays the microphone button (`voice_note_btn`), fallback taps are strictly skipped, preventing unintentional voice note recordings.
- **Token & Rate-Limit (TPM) Optimizations**: Macro actions (`send_whatsapp`, `call_phone`) execute end-to-end in a single turn, and mobile operations dynamically omit job tracking history, cutting token consumption by >70% per turn on the Gemini Free Tier.
- **Hardware-Encrypted Phone Credentials (Windows DPAPI)**: Phone unlock credentials (PIN / password) are encrypted using Windows Data Protection API (`CryptProtectData`), binding the key to the current machine and user account. Plaintext secrets are never stored on disk and never exposed in REST responses or logs. When the user asks Kaalu to unlock their phone (*"Kaalu, unlock my phone"*), the orchestrator automatically decrypts the PIN in memory and completes the unlock sequence without requiring manual input. Manage or update credentials anytime from the `/settings` web dashboard.



**---**



## Running Automated Tests



Run the comprehensive pytest test suite to verify all subsystem contracts:



```cmd

.venv\Scripts\pytest

```



**---**



## License



This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.
