"""
Project Kaalu - Futuristic JARVIS-Inspired Interactive GUI
Provides a two-tab interface:
Tab 1: Unified Live Editable Working Terminal for Hub, Faulkner, and Kaalu.
Tab 2: Hologram Video Avatar, Markdown Output, and Continuous Voice Listening with Interruption.
"""

def render_gui_page(active_animation: str = "jarvis-30-fps-1600x1600.mp4", active_voice: str = "jarvis-gb") -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Kaalu | Autonomous AI Assistant</title>
    <!-- Marked.js for fast client-side markdown parsing -->
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root {{
            --bg-base: #060913;
            --bg-surface: #0c1322;
            --bg-card: #111a2e;
            --border-color: #1e293b;
            --primary-glow: #38bdf8;
            --accent-cyan: #06b6d4;
            --accent-purple: #818cf8;
            --accent-amber: #f59e0b;
            --accent-emerald: #10b981;
            --accent-rose: #f43f5e;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --font-mono: "Fira Code", "Consolas", "Courier New", monospace;
            --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background: var(--bg-base);
            color: var(--text-main);
            font-family: var(--font-sans);
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            user-select: none;
        }}

        /* Header Navigation */
        header {{
            background: rgba(12, 19, 34, 0.95);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border-color);
            padding: 0.6rem 1.25rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 100;
        }}

        .brand {{
            display: flex;
            align-items: center;
            gap: 0.6rem;
            font-weight: 700;
            font-size: 1.1rem;
            letter-spacing: 0.05em;
        }}

        .brand-badge {{
            background: linear-gradient(135deg, #0284c7, #6366f1);
            color: white;
            font-size: 0.7rem;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            font-weight: 800;
        }}

        /* Tab Switcher */
        .tabs-nav {{
            display: flex;
            background: #080d1a;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 0.25rem;
            gap: 0.25rem;
        }}

        .tab-btn {{
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 0.45rem 1rem;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.45rem;
            transition: all 0.2s ease;
        }}

        .tab-btn:hover {{
            color: var(--text-main);
            background: rgba(255, 255, 255, 0.05);
        }}

        .tab-btn.active {{
            background: #1e293b;
            color: var(--primary-glow);
            box-shadow: 0 0 12px rgba(56, 189, 248, 0.25);
        }}

        /* Header Telemetry Pills */
        .header-pills {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .telemetry-pill {{
            background: #080d1a;
            border: 1px solid #1e293b;
            border-radius: 6px;
            padding: 0.3rem 0.6rem;
            font-size: 0.75rem;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 0.35rem;
        }}

        .telemetry-pill .dot {{
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: var(--accent-emerald);
            box-shadow: 0 0 6px var(--accent-emerald);
        }}

        .settings-link {{
            background: transparent;
            border: 1px solid #334155;
            color: #94a3b8;
            padding: 0.3rem 0.6rem;
            border-radius: 6px;
            font-size: 0.75rem;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 0.3rem;
            transition: all 0.2s;
        }}

        .settings-link:hover {{
            border-color: var(--primary-glow);
            color: white;
        }}

        /* Main Workspace Container */
        main {{
            flex: 1;
            position: relative;
            overflow: hidden;
            display: flex;
        }}

        .tab-content {{
            display: none;
            width: 100%;
            height: 100%;
            flex-direction: column;
        }}

        .tab-content.active {{
            display: flex;
        }}

        /* ================= TAB 1: LIVE EDITABLE TERMINAL ================= */
        .terminal-container {{
            display: flex;
            flex-direction: column;
            height: 100%;
            background: #040711;
            font-family: var(--font-mono);
        }}

        .terminal-toolbar {{
            background: #080d1a;
            border-bottom: 1px solid var(--border-color);
            padding: 0.5rem 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.8rem;
        }}

        .terminal-filters {{
            display: flex;
            gap: 0.4rem;
        }}

        .filter-btn {{
            background: #0f172a;
            border: 1px solid #1e293b;
            color: #64748b;
            padding: 0.25rem 0.6rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.75rem;
            font-family: var(--font-mono);
            transition: all 0.15s;
        }}

        .filter-btn:hover {{
            color: #cbd5e1;
        }}

        .filter-btn.active {{
            background: #1e293b;
            color: var(--primary-glow);
            border-color: #38bdf8;
        }}

        .terminal-actions {{
            display: flex;
            gap: 0.5rem;
        }}

        .term-action-btn {{
            background: transparent;
            border: 1px solid #334155;
            color: #94a3b8;
            padding: 0.25rem 0.55rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.75rem;
        }}

        .term-action-btn:hover {{
            color: white;
            border-color: #64748b;
        }}

        .terminal-screen {{
            flex: 1;
            padding: 1rem;
            overflow-y: auto;
            color: #cbd5e1;
            font-size: 0.85rem;
            line-height: 1.5;
            white-space: pre-wrap;
            word-break: break-all;
            user-select: text;
        }}

        .log-line {{
            display: flex;
            gap: 0.6rem;
            margin-bottom: 0.25rem;
            align-items: flex-start;
        }}

        .log-ts {{
            color: #475569;
            font-size: 0.75rem;
            min-width: 65px;
        }}

        .log-tag {{
            font-size: 0.7rem;
            padding: 0.1rem 0.35rem;
            border-radius: 3px;
            font-weight: 700;
            text-transform: uppercase;
        }}

        .tag-kaalu {{ background: rgba(56, 189, 248, 0.2); color: #38bdf8; }}
        .tag-faulkner {{ background: rgba(245, 158, 11, 0.2); color: #f59e0b; }}
        .tag-android {{ background: rgba(16, 185, 129, 0.2); color: #10b981; }}
        .tag-hub {{ background: rgba(129, 140, 248, 0.2); color: #818cf8; }}
        .tag-system {{ background: rgba(244, 63, 94, 0.2); color: #f43f5e; }}

        .log-msg {{
            flex: 1;
        }}

        /* Terminal Interactive Command Prompt Bar */
        .terminal-prompt-bar {{
            background: #090e1b;
            border-top: 1px solid var(--border-color);
            padding: 0.6rem 1rem;
            display: flex;
            align-items: center;
            gap: 0.6rem;
        }}

        .prompt-symbol {{
            color: #38bdf8;
            font-weight: 800;
            font-size: 0.95rem;
        }}

        .terminal-input {{
            flex: 1;
            background: #040711;
            border: 1px solid #1e293b;
            color: #f8fafc;
            padding: 0.5rem 0.8rem;
            border-radius: 6px;
            font-family: var(--font-mono);
            font-size: 0.85rem;
            outline: none;
            transition: border-color 0.2s;
        }}

        .terminal-input:focus {{
            border-color: #38bdf8;
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.2);
        }}

        .btn-execute {{
            background: #0284c7;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            cursor: pointer;
            font-family: var(--font-mono);
            font-size: 0.8rem;
            font-weight: 700;
            transition: background 0.2s;
        }}

        .btn-execute:hover {{
            background: #0369a1;
        }}

        /* ================= TAB 2: VISUAL ASSISTANT & HOLOGRAM ================= */
        .assistant-view {{
            display: flex;
            height: 100%;
            overflow: hidden;
        }}

        /* Left Column: Hologram Video Avatar & Ear Listening Status */
        .avatar-pane {{
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            position: relative;
            background: radial-gradient(circle at center, #0e172a 0%, #060913 85%);
            border-right: 1px solid var(--border-color);
            padding: 1.5rem;
        }}

        /* Hologram Glowing Video Circle */
        .hologram-wrapper {{
            position: relative;
            width: 320px;
            height: 320px;
            border-radius: 50%;
            padding: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: conic-gradient(from 180deg at 50% 50%, #06b6d4, #38bdf8, #6366f1, #06b6d4);
            box-shadow: 0 0 40px rgba(56, 189, 248, 0.4);
            animation: holoRotate 20s linear infinite;
            transition: all 0.4s ease;
        }}

        @keyframes holoRotate {{
            0% {{ filter: hue-rotate(0deg); }}
            100% {{ filter: hue-rotate(360deg); }}
        }}

        .hologram-wrapper.speaking {{
            box-shadow: 0 0 60px rgba(16, 185, 129, 0.8);
            transform: scale(1.04);
        }}

        .hologram-wrapper.hearing {{
            box-shadow: 0 0 60px rgba(245, 158, 11, 0.85);
            transform: scale(1.05);
        }}

        .hologram-wrapper.reasoning {{
            box-shadow: 0 0 50px rgba(129, 140, 248, 0.8);
            animation: holoPulse 1.2s ease-in-out infinite alternate;
        }}

        @keyframes holoPulse {{
            0% {{ transform: scale(0.98); }}
            100% {{ transform: scale(1.03); }}
        }}

        .video-mask {{
            width: 100%;
            height: 100%;
            border-radius: 50%;
            overflow: hidden;
            background: #000;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .avatar-video {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: 50%;
        }}

        /* Kaalu Live Step Status Display */
        .step-status-bar {{
            margin-top: 1.25rem;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0.35rem;
            background: rgba(11, 21, 40, 0.75);
            border: 1px solid rgba(56, 189, 248, 0.25);
            border-radius: 10px;
            padding: 0.6rem 1.1rem;
            width: 100%;
            max-width: 360px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
            transition: all 0.3s ease;
        }}

        .step-status-bar.active {{
            border-color: #38bdf8;
            box-shadow: 0 0 20px rgba(56, 189, 248, 0.25);
        }}

        .step-badge-pill {{
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            background: #070d19;
            border: 1px solid #1e3a5f;
            border-radius: 20px;
            padding: 0.2rem 0.65rem;
            font-size: 0.75rem;
            font-weight: 700;
            color: #38bdf8;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-family: var(--font-mono);
        }}

        .status-indicator-dot {{
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: #10b981;
            box-shadow: 0 0 8px #10b981;
        }}

        .status-indicator-dot.pulse {{
            background: #38bdf8;
            box-shadow: 0 0 10px #38bdf8;
            animation: dotPulse 1s ease-in-out infinite alternate;
        }}

        @keyframes dotPulse {{
            0% {{ transform: scale(0.9); opacity: 0.7; }}
            100% {{ transform: scale(1.3); opacity: 1; }}
        }}

        .step-desc-text {{
            font-size: 0.8rem;
            color: #cbd5e1;
            text-align: center;
            min-height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.2rem;
            word-break: break-word;
        }}

        .step-dots {{
            display: inline-flex;
            letter-spacing: 1px;
        }}

        .step-dots span {{
            animation: blinkDots 1.4s infinite;
            opacity: 0.2;
            color: #38bdf8;
            font-weight: bold;
        }}

        .step-dots span:nth-child(1) {{ animation-delay: 0.0s; }}
        .step-dots span:nth-child(2) {{ animation-delay: 0.2s; }}
        .step-dots span:nth-child(3) {{ animation-delay: 0.4s; }}

        @keyframes blinkDots {{
            0%, 80%, 100% {{ opacity: 0.2; transform: translateY(0); }}
            40% {{ opacity: 1; transform: translateY(-2px); color: #38bdf8; text-shadow: 0 0 6px #38bdf8; }}
        }}

        /* Voice Status Banner */
        .voice-status-box {{
            margin-top: 1.25rem;
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            gap: 0.5rem;
            max-width: 400px;
        }}

        .voice-indicator {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.4rem 1rem;
            border-radius: 20px;
            background: #0b1324;
            border: 1px solid #1e293b;
            font-size: 0.85rem;
            font-weight: 600;
        }}

        .voice-indicator.active {{
            border-color: #38bdf8;
            color: #38bdf8;
            box-shadow: 0 0 15px rgba(56, 189, 248, 0.2);
        }}

        .voice-transcript {{
            font-size: 0.8rem;
            color: #94a3b8;
            min-height: 24px;
            font-style: italic;
        }}

        .mic-toggle-btn {{
            margin-top: 0.5rem;
            background: #1e293b;
            border: 1px solid #334155;
            color: #cbd5e1;
            padding: 0.45rem 1rem;
            border-radius: 6px;
            font-size: 0.8rem;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.4rem;
            transition: all 0.2s;
        }}

        .mic-toggle-btn:hover {{
            border-color: #38bdf8;
            color: white;
        }}

        /* Right Column: Markdown Output & Voice Synthesis */
        .output-pane {{
            flex: 1.2;
            display: flex;
            flex-direction: column;
            background: var(--bg-surface);
            padding: 1.25rem;
            overflow-y: auto;
            user-select: text;
        }}

        .pane-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid var(--border-color);
        }}

        .pane-title {{
            font-size: 1.05rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        /* Voice Response Alert Box */
        .voice-response-card {{
            background: #0b1528;
            border: 1px solid #1e3a5f;
            border-left: 4px solid #38bdf8;
            border-radius: 8px;
            padding: 0.9rem 1rem;
            margin-bottom: 1.25rem;
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
        }}

        .voice-response-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.75rem;
            font-weight: 700;
            color: #38bdf8;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .voice-response-text {{
            font-size: 0.9rem;
            color: #f1f5f9;
            line-height: 1.4;
        }}

        .typewriter-cursor {{
            color: #38bdf8;
            font-weight: bold;
            display: inline-block;
            animation: blinkCursor 0.75s infinite;
            margin-left: 2px;
        }}

        @keyframes blinkCursor {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0; }}
        }}

        /* Markdown Rendered Container & Chat History Scrollbar */
        .markdown-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.15rem;
            flex: 1;
            overflow-y: auto;
            line-height: 1.6;
            color: #e2e8f0;
            font-size: 0.9rem;
            transition: all 0.3s ease;
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
            scroll-behavior: smooth;
        }}

        .markdown-card::-webkit-scrollbar {{
            width: 7px;
        }}

        .markdown-card::-webkit-scrollbar-track {{
            background: rgba(4, 7, 17, 0.7);
            border-radius: 4px;
        }}

        .markdown-card::-webkit-scrollbar-thumb {{
            background: #1e3a5f;
            border-radius: 4px;
            border: 1px solid rgba(56, 189, 248, 0.2);
        }}

        .markdown-card::-webkit-scrollbar-thumb:hover {{
            background: #38bdf8;
            box-shadow: 0 0 8px rgba(56, 189, 248, 0.5);
        }}

        /* Chat History Entries */
        .chat-entry {{
            display: flex;
            flex-direction: column;
            gap: 0.45rem;
            width: 100%;
            animation: chatSlideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }}

        @keyframes chatSlideIn {{
            from {{
                opacity: 0;
                transform: translateY(8px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}

        .chat-entry-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 0.3rem;
            font-size: 0.75rem;
        }}

        .chat-entry-header.user-header {{
            flex-direction: row;
        }}

        .chat-sender-info {{
            display: flex;
            align-items: center;
            gap: 0.45rem;
            font-weight: 700;
        }}

        .chat-avatar-icon {{
            font-size: 0.95rem;
        }}

        .chat-sender-name {{
            font-size: 0.8rem;
            color: #cbd5e1;
        }}

        .chat-timestamp {{
            font-family: var(--font-mono);
            font-size: 0.72rem;
            color: #64748b;
            letter-spacing: 0.03em;
        }}

        .chat-tag {{
            font-size: 0.65rem;
            padding: 0.1rem 0.4rem;
            border-radius: 3px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .tag-user {{
            background: rgba(14, 165, 233, 0.2);
            color: #38bdf8;
            border: 1px solid rgba(56, 189, 248, 0.3);
        }}

        .tag-kaalu {{
            background: rgba(16, 185, 129, 0.2);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        .tag-kaalu.reasoning {{
            background: rgba(129, 140, 248, 0.2);
            color: #818cf8;
            border: 1px solid rgba(129, 140, 248, 0.3);
        }}

        .chat-bubble {{
            border-radius: 8px;
            padding: 1rem 1.15rem;
            font-size: 0.88rem;
            line-height: 1.6;
            word-break: break-word;
            position: relative;
        }}

        .user-entry {{
            align-self: flex-end;
            max-width: 85%;
        }}

        .user-bubble {{
            background: linear-gradient(135deg, rgba(14, 165, 233, 0.12), rgba(99, 102, 241, 0.15));
            border: 1px solid rgba(56, 189, 248, 0.35);
            color: #f8fafc;
            border-top-right-radius: 2px;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
        }}

        .kaalu-entry {{
            align-self: flex-start;
            width: 100%;
        }}

        .kaalu-bubble {{
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid var(--border-color);
            color: #e2e8f0;
            border-top-left-radius: 2px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
        }}

        .markdown-card.fadeInUp {{
            animation: fadeInUp 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }}

        @keyframes fadeInUp {{
            0% {{
                opacity: 0;
                transform: translateY(12px);
            }}
            100% {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}

        .markdown-card a {{
            color: #38bdf8;
            text-decoration: underline;
            transition: color 0.15s;
        }}

        .markdown-card a:hover {{
            color: #7dd3fc;
        }}

        /* Objective Processing State in Markdown Card */
        .processing-placeholder {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 3rem 1.5rem;
            text-align: center;
            gap: 1rem;
            min-height: 250px;
        }}

        .processing-glow-badge {{
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid #38bdf8;
            color: #38bdf8;
            padding: 0.35rem 0.9rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            font-family: var(--font-mono);
            box-shadow: 0 0 15px rgba(56, 189, 248, 0.25);
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
        }}

        .processing-goal-title {{
            color: #f8fafc;
            font-size: 1.15rem;
            font-weight: 600;
            max-width: 90%;
            word-break: break-word;
            line-height: 1.4;
        }}

        .processing-note {{
            color: #94a3b8;
            font-size: 0.85rem;
        }}

        .processing-progress-track {{
            width: 240px;
            height: 4px;
            background: #1e293b;
            border-radius: 2px;
            overflow: hidden;
            position: relative;
            margin-top: 0.25rem;
        }}

        .processing-progress-bar {{
            width: 70px;
            height: 100%;
            background: linear-gradient(90deg, #06b6d4, #38bdf8, #818cf8);
            position: absolute;
            border-radius: 2px;
            animation: indeterminateTrack 1.4s ease-in-out infinite;
        }}

        @keyframes indeterminateTrack {{
            0% {{ left: -70px; width: 70px; }}
            50% {{ left: 35%; width: 110px; }}
            100% {{ left: 100%; width: 70px; }}
        }}

        .markdown-card h1, .markdown-card h2, .markdown-card h3 {{
            color: #f8fafc;
            margin-top: 1rem;
            margin-bottom: 0.5rem;
        }}

        .markdown-card h1 {{ font-size: 1.35rem; border-bottom: 1px solid #1e293b; padding-bottom: 0.4rem; }}
        .markdown-card h2 {{ font-size: 1.15rem; }}
        .markdown-card h3 {{ font-size: 1rem; }}

        .markdown-card p {{
            margin-bottom: 0.75rem;
        }}

        .markdown-card ul, .markdown-card ol {{
            margin-left: 1.5rem;
            margin-bottom: 0.75rem;
        }}

        .markdown-card li {{
            margin-bottom: 0.25rem;
        }}

        .markdown-card pre {{
            background: #050811;
            border: 1px solid #1e293b;
            padding: 0.75rem;
            border-radius: 6px;
            overflow-x: auto;
            font-family: var(--font-mono);
            font-size: 0.8rem;
            margin-bottom: 0.75rem;
        }}

        .markdown-card code {{
            background: rgba(56, 189, 248, 0.1);
            color: #38bdf8;
            padding: 0.15rem 0.35rem;
            border-radius: 4px;
            font-family: var(--font-mono);
            font-size: 0.85em;
        }}

        .markdown-card table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1rem;
        }}

        .markdown-card th, .markdown-card td {{
            border: 1px solid #334155;
            padding: 0.5rem 0.75rem;
            text-align: left;
        }}

        .markdown-card th {{
            background: #0b1324;
            color: #38bdf8;
        }}

        /* Tab 2 Bottom Input Bar */
        .assistant-input-bar {{
            margin-top: 1rem;
            display: flex;
            gap: 0.5rem;
        }}

        .assistant-input {{
            flex: 1;
            background: #090e1b;
            border: 1px solid var(--border-color);
            color: white;
            padding: 0.6rem 0.9rem;
            border-radius: 6px;
            font-size: 0.85rem;
            outline: none;
        }}

        .assistant-input:focus {{
            border-color: #38bdf8;
        }}

        /* Responsive Breakpoints */
        @media (max-width: 900px) {{
            .assistant-view {{
                flex-direction: column;
            }}
            .avatar-pane {{
                border-right: none;
                border-bottom: 1px solid var(--border-color);
                padding: 1rem;
            }}
            .hologram-wrapper {{
                width: 220px;
                height: 220px;
            }}
        }}
    </style>
</head>
<body>
    <!-- Top Header -->
    <header>
        <div class="brand">
            <span>Project Kaalu</span>
            <span class="brand-badge">GUI Agent</span>
        </div>

        <!-- 2-Tab Navigation -->
        <div class="tabs-nav">
            <button class="tab-btn active" id="tabBtn1" onclick="switchTab(1)">
                <span>💻</span> Live Terminal
            </button>
            <button class="tab-btn" id="tabBtn2" onclick="switchTab(2)">
                <span>🤖</span> Visual Assistant
            </button>
        </div>

        <!-- Telemetry & Settings -->
        <div class="header-pills">
            <div class="telemetry-pill">
                <span class="dot"></span>
                <span>Hub :8000</span>
            </div>
            <div class="telemetry-pill" id="voiceModelPill">
                <span>🎙️</span>
                <span id="headerVoiceLabel">{active_voice.upper()}</span>
            </div>
            <a href="/settings" class="settings-link" target="_blank" title="Open Settings Dashboard">
                <span>⚙️</span> Settings
            </a>
        </div>
    </header>

    <!-- Main Content Area -->
    <main>
        <!-- ================= TAB 1: LIVE EDITABLE TERMINAL ================= -->
        <section id="tabContent1" class="tab-content active">
            <div class="terminal-container">
                <!-- Toolbar with source filters -->
                <div class="terminal-toolbar">
                    <div class="terminal-filters">
                        <button class="filter-btn active" data-filter="all" onclick="filterLogs('all')">ALL LOGS</button>
                        <button class="filter-btn" data-filter="kaalu" onclick="filterLogs('kaalu')">KAALU</button>
                        <button class="filter-btn" data-filter="faulkner" onclick="filterLogs('faulkner')">FAULKNER</button>
                        <button class="filter-btn" data-filter="android" onclick="filterLogs('android')">ANDROID</button>
                        <button class="filter-btn" data-filter="rgs_hub" onclick="filterLogs('rgs_hub')">RGS HUB</button>
                    </div>
                    <div class="terminal-actions">
                        <button class="term-action-btn" onclick="clearTerminal()">🧹 Clear</button>
                        <button class="term-action-btn" id="autoScrollBtn" onclick="toggleAutoScroll()">📜 Auto-Scroll: ON</button>
                        <button class="term-action-btn" onclick="copyTerminalLogs()">📋 Copy All</button>
                    </div>
                </div>

                <!-- Scrolling Screen Output -->
                <div class="terminal-screen" id="terminalScreen">
                    <div class="log-line">
                        <span class="log-ts">SYS</span>
                        <span class="log-tag tag-hub">RGS HUB</span>
                        <span class="log-msg">Project Kaalu Unified Terminal connected. Awaiting telemetry stream...</span>
                    </div>
                </div>

                <!-- Interactive Command Line Prompt -->
                <div class="terminal-prompt-bar">
                    <span class="prompt-symbol">Kaalu&gt;</span>
                    <input type="text" id="terminalInput" class="terminal-input" 
                           placeholder="Type an objective, terminal task, or goal (e.g. 'call Mom', 'open notepad', 'open youtube.com')..."
                           autocomplete="off" spellcheck="false">
                    <button class="btn-execute" onclick="submitTerminalCommand()">⚡ Execute</button>
                </div>
            </div>
        </section>

        <!-- ================= TAB 2: VISUAL ASSISTANT & HOLOGRAM ================= -->
        <section id="tabContent2" class="tab-content">
            <div class="assistant-view">
                <!-- Left: Hologram Video Avatar & Voice Status -->
                <div class="avatar-pane">
                    <div class="hologram-wrapper" id="hologramRing">
                        <div class="video-mask">
                            <video id="avatarVideo" class="avatar-video" autoplay loop muted playsinline>
                                <source src="/animations/{active_animation}" type="video/mp4">
                                Your browser does not support video playback.
                            </video>
                        </div>
                    </div>

                    <!-- Kaalu Live Step Status Display -->
                    <div class="step-status-bar" id="stepStatusBar">
                        <div class="step-badge-pill" id="stepBadge">
                            <span class="status-indicator-dot" id="stepIndicatorDot"></span>
                            <span id="stepBadgeText">IDLE</span>
                        </div>
                        <div class="step-desc-text" id="stepDesc">
                            <span id="stepActionText">Ready for objective</span>
                            <span class="step-dots" id="stepDots" style="display: none;"><span>.</span><span>.</span><span>.</span></span>
                        </div>
                    </div>

                    <div class="voice-status-box">
                        <div class="voice-indicator active" id="voiceIndicator" onclick="toggleMic()" style="cursor: pointer;" title="Click to test or reactivate microphone">
                            <span id="voiceStatusDot" style="width: 8px; height: 8px; border-radius: 50%; background: #38bdf8;"></span>
                            <span id="voiceStatusText">🎙️ Kaalu Ears Active (Listening...)</span>
                        </div>
                        <div class="voice-transcript" id="voiceTranscript">
                            Speak to give Kaalu an objective...
                        </div>
                        <button class="mic-toggle-btn" id="micToggleBtn" onclick="toggleMic()">
                            <span>🎙️</span> <span id="micToggleLabel">Mute Microphone</span>
                        </button>
                    </div>
                </div>

                <!-- Right: Markdown & Voice Output Presentation -->
                <div class="output-pane">
                    <div class="pane-header">
                        <div class="pane-title">
                            <span>🤖</span> Kaalu Visual Intelligence
                        </div>
                        <div style="display: flex; gap: 0.5rem;">
                            <button class="term-action-btn" onclick="clearChatHistory()">
                                🧹 Clear Chat
                            </button>
                            <button class="term-action-btn" onclick="stopActiveVoice()">
                                🛑 Stop Voice Audio
                            </button>
                        </div>
                    </div>

                    <!-- Voice Response Summary -->
                    <div class="voice-response-card" id="voiceResponseCard">
                        <div class="voice-response-header">
                            <span>🔊 Spoken Voice Summary</span>
                            <span id="voiceModelTag">{active_voice.upper()}</span>
                        </div>
                        <div class="voice-response-text" id="voiceResponseText">
                            Sir, I am online and listening. You can speak your command or type in the console.
                        </div>
                    </div>

                    <!-- Formatted Markdown Output & Persistent Chat History -->
                    <div class="markdown-card" id="markdownOutput">
                        <div class="chat-entry kaalu-entry" id="chatEntry-welcome">
                            <div class="chat-entry-header">
                                <div class="chat-sender-info">
                                    <span class="chat-avatar-icon chat-avatar-kaalu">🤖</span>
                                    <span class="chat-sender-name">Project Kaalu</span>
                                    <span class="chat-tag tag-kaalu">ONLINE</span>
                                </div>
                                <div class="chat-timestamp" id="welcomeTimestamp">--:--:--</div>
                            </div>
                            <div class="chat-bubble kaalu-bubble">
                                <h2>Welcome to Project Kaalu</h2>
                                <p>Kaalu is your autonomous multi-agent assistant with voice intelligence, Windows system automation (Faulkner), Chrome browser automation (David), and mobile hardware control (Android ADB).</p>
                                <ul>
                                    <li><strong>Voice Ears:</strong> Speak anytime. When you start speaking, active voice output immediately cuts off and Kaalu begins listening.</li>
                                    <li><strong>Live Terminal:</strong> Switch to Tab 1 to see all multi-agent execution steps in real-time.</li>
                                    <li><strong>Hologram Avatar:</strong> Video animations can be switched dynamically from the <code>/settings</code> dashboard.</li>
                                </ul>
                            </div>
                        </div>
                    </div>

                    <!-- Bottom Quick Input Field -->
                    <div class="assistant-input-bar">
                        <input type="text" id="assistantInput" class="assistant-input" 
                               placeholder="Or type your goal here and press Enter...">
                        <button class="btn-execute" onclick="submitAssistantInput()">Send</button>
                    </div>
                </div>
            </div>
        </section>
    </main>

    <script>
        // State variables
        let activeTab = 1;
        let autoScroll = true;
        let micActive = true;
        let recognition = null;
        let isRecognizing = false;
        let isStartingRecognition = false;
        let isKaaluSpeaking = false;
        let lastSpokenText = '';
        let speakingTimeout = null;
        let restartTimer = null;
        let currentFilter = 'all';
        let commandHistory = [];
        let historyIndex = -1;
        let activeTypewriterTimer = null;
        let lastRenderedAnswer = null;
        let lastRenderTime = 0;
        let lastRenderedQId = null;
        let currentQueryId = 0;

        // Configure marked.js with custom renderer to open all links in target="_blank"
        if (window.marked) {{
            try {{
                const renderer = new marked.Renderer();
                renderer.link = function(arg1, arg2, arg3) {{
                    let href = '';
                    let title = '';
                    let text = '';
                    if (typeof arg1 === 'object' && arg1 !== null) {{
                        href = arg1.href || '';
                        title = arg1.title || '';
                        text = arg1.text || href;
                    }} else {{
                        href = arg1 || '';
                        title = arg2 || '';
                        text = arg3 || href;
                    }}
                    const titleAttr = title ? ` title="${{title}}"` : '';
                    return `<a href="${{href}}" target="_blank" rel="noopener noreferrer"${{titleAttr}}>${{text}}</a>`;
                }};
                marked.use({{ renderer: renderer }});
            }} catch (err) {{
                console.warn('Marked link renderer configuration note:', err);
            }}
        }}

        // Offline markdown fallback parser in case CDN is unreachable
        function simpleMarkdownFallback(text) {{
            if (!text) return '';
            let html = text
                .replace(/^### (.*$)/gim, '<h3>$1</h3>')
                .replace(/^## (.*$)/gim, '<h2>$1</h2>')
                .replace(/^# (.*$)/gim, '<h1>$1</h1>')
                .replace(/\\*\\*(.*?)\\*\\*/gim, '<strong>$1</strong>')
                .replace(/\\*(.*?)\\*/gim, '<em>$1</em>')
                .replace(/`([^`]+)`/gim, '<code>$1</code>')
                .replace(/\\[([^\\]]+)\\]\\(([^)]+)\\)/gim, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
                .replace(/(^|[^"'])(https?:\\/\\/[^\\s<]+)/gim, '$1<a href="$2" target="_blank" rel="noopener noreferrer">$2</a>')
                .replace(/^\\s*-\\s*(.*$)/gim, '<li>$1</li>')
                .replace(/\\n/gim, '<br>');
            return html;
        }}

        function parseMarkdown(text) {{
            if (window.marked && typeof window.marked.parse === 'function') {{
                try {{
                    return marked.parse(text);
                }} catch (e) {{
                    console.warn('Marked parse error, using fallback:', e);
                }}
            }}
            return simpleMarkdownFallback(text);
        }}

        function formatCurrentTime() {{
            const d = new Date();
            return d.toLocaleTimeString([], {{ hour: '2-digit', minute: '2-digit', second: '2-digit' }});
        }}

        function scrollChatToBottom() {{
            const mdBox = document.getElementById('markdownOutput');
            if (mdBox) {{
                mdBox.scrollTop = mdBox.scrollHeight;
            }}
        }}

        function clearChatHistory() {{
            const mdBox = document.getElementById('markdownOutput');
            if (!mdBox) return;
            mdBox.innerHTML = `
                <div class="chat-entry kaalu-entry" id="chatEntry-welcome">
                    <div class="chat-entry-header">
                        <div class="chat-sender-info">
                            <span class="chat-avatar-icon chat-avatar-kaalu">🤖</span>
                            <span class="chat-sender-name">Project Kaalu</span>
                            <span class="chat-tag tag-kaalu">ONLINE</span>
                        </div>
                        <div class="chat-timestamp">${{formatCurrentTime()}}</div>
                    </div>
                    <div class="chat-bubble kaalu-bubble">
                        <p style="color: #94a3b8; font-style: italic;">Chat buffer cleared. Ready for your next objective, Sir.</p>
                    </div>
                </div>
            `;
        }}

        function appendUserMessage(goal, queryId, timeStr) {{
            const mdBox = document.getElementById('markdownOutput');
            if (!mdBox) return;
            const entry = document.createElement('div');
            entry.className = 'chat-entry user-entry';
            entry.id = 'chatEntry-user-' + queryId;
            entry.innerHTML = `
                <div class="chat-entry-header user-header">
                    <div class="chat-sender-info">
                        <span class="chat-avatar-icon chat-avatar-user">👤</span>
                        <span class="chat-sender-name">Master Rohit</span>
                        <span class="chat-tag tag-user">YOU</span>
                    </div>
                    <div class="chat-timestamp">${{timeStr}}</div>
                </div>
                <div class="chat-bubble user-bubble">${{escapeHtml(goal)}}</div>
            `;
            mdBox.appendChild(entry);
            scrollChatToBottom();
        }}

        function appendPendingKaaluMessage(goal, queryId, timeStr) {{
            const mdBox = document.getElementById('markdownOutput');
            if (!mdBox) return;
            const entry = document.createElement('div');
            entry.className = 'chat-entry kaalu-entry';
            entry.id = 'chatEntry-kaalu-' + queryId;
            entry.innerHTML = `
                <div class="chat-entry-header">
                    <div class="chat-sender-info">
                        <span class="chat-avatar-icon chat-avatar-kaalu">🤖</span>
                        <span class="chat-sender-name">Project Kaalu</span>
                        <span class="chat-tag tag-kaalu reasoning" id="chatTag-${{queryId}}">REASONING</span>
                    </div>
                    <div class="chat-timestamp" id="chatTime-${{queryId}}">${{timeStr}}</div>
                </div>
                <div class="chat-bubble kaalu-bubble" id="chatBubble-${{queryId}}">
                    <div class="processing-placeholder">
                        <div class="processing-glow-badge">⚡ EXECUTING OBJECTIVE</div>
                        <h3 class="processing-goal-title">"${{escapeHtml(goal)}}"</h3>
                        <p class="processing-note" id="chatPendingNote-${{queryId}}">Kaalu is reasoning and delegating across sub-agents...</p>
                        <div class="processing-progress-track">
                            <div class="processing-progress-bar"></div>
                        </div>
                    </div>
                </div>
            `;
            mdBox.appendChild(entry);
            scrollChatToBottom();
        }}

        // Switch between Tab 1 and Tab 2
        function switchTab(tabNum) {{
            activeTab = tabNum;
            document.querySelectorAll('.tab-btn').forEach((b, idx) => {{
                b.classList.toggle('active', idx + 1 === tabNum);
            }});
            document.querySelectorAll('.tab-content').forEach((c, idx) => {{
                c.classList.toggle('active', idx + 1 === tabNum);
            }});
            if (tabNum === 1 && autoScroll) {{
                const screen = document.getElementById('terminalScreen');
                if (screen) screen.scrollTop = screen.scrollHeight;
            }}
        }}

        // ================= WEBSOCKET TERMINAL & TELEMETRY STREAM =================
        let termWs = null;
        function initTerminalWs() {{
            const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUri = proto + '//' + window.location.host + '/ws/terminal';
            
            try {{
                termWs = new WebSocket(wsUri);
                termWs.onopen = () => {{
                    appendLog('SYS', 'hub', 'WebSocket live terminal connected to RGS Central Bus.');
                }};
                termWs.onmessage = (event) => {{
                    try {{
                        const data = JSON.parse(event.data);
                        handleTelemetryEvent(data);
                    }} catch (err) {{
                        appendLog('RAW', 'hub', event.data);
                    }}
                }};
                termWs.onclose = () => {{
                    appendLog('SYS', 'hub', 'Terminal stream disconnected. Reconnecting in 3s...');
                    setTimeout(initTerminalWs, 3000);
                }};
            }} catch (e) {{
                console.error('Terminal WS init error:', e);
            }}
        }}

        function handleTelemetryEvent(data) {{
            const ts = data.timestamp || new Date().toLocaleTimeString();
            const src = (data.source || data.sender || 'hub').toLowerCase();
            const msg = data.message || data.log || data.action || JSON.stringify(data);
            appendLog(ts, src, msg, data);

            // Update live step status display with animated ellipsis
            updateStepStatus(data);

            // Handle hologram states and completion
            const type = data.type || data.action;
            if (type === 'finish') {{
                if (data.final_answer) {{
                    const qId = (data.query_id !== undefined && data.query_id !== null) ? Number(data.query_id) : currentQueryId;
                    renderOutput(data.final_answer, data.voice_response, qId, data.superseded === true, data.is_latest === false);
                }}
            }} else if (type === 'step' || type === 'step_start' || type === 'delegate' || type === 'observation') {{
                setHologramState('reasoning');
            }}
        }}

        // ================= STEP STATUS & ANIMATED PROCESSING =================
        function updateStepStatus(data) {{
            const bar = document.getElementById('stepStatusBar');
            const badge = document.getElementById('stepBadgeText');
            const dot = document.getElementById('stepIndicatorDot');
            const actionText = document.getElementById('stepActionText');
            const dots = document.getElementById('stepDots');
            if (!bar || !badge || !actionText) return;

            const type = data.type || data.action;
            let noteText = '';

            if (type === 'start') {{
                bar.classList.add('active');
                if (dot) dot.className = 'status-indicator-dot pulse';
                badge.textContent = 'INITIATING';
                actionText.textContent = data.goal ? `Analyzing: "${{data.goal}}"` : 'Analyzing objective';
                if (dots) dots.style.display = 'inline-flex';
                noteText = 'Initiating objective: ' + (data.goal || '');
            }} else if (type === 'step_start') {{
                bar.classList.add('active');
                if (dot) dot.className = 'status-indicator-dot pulse';
                const s = data.step || 1;
                const m = data.max_steps || 15;
                badge.textContent = `STEP ${{s}}/${{m}}`;
                actionText.textContent = 'Reasoning & Planning next action';
                if (dots) dots.style.display = 'inline-flex';
                noteText = `Step ${{s}}/${{m}}: Reasoning next action...`;
            }} else if (type === 'step') {{
                bar.classList.add('active');
                if (dot) dot.className = 'status-indicator-dot pulse';
                const s = data.step || 1;
                const m = data.max_steps || 15;
                badge.textContent = `STEP ${{s}}/${{m}}`;
                if (data.thought) {{
                    const t = data.thought.trim();
                    actionText.textContent = t.length > 70 ? t.substring(0, 70) + '...' : t;
                    noteText = `Step ${{s}}/${{m}}: ` + (t.length > 90 ? t.substring(0, 90) + '...' : t);
                }} else if (data.action) {{
                    actionText.textContent = `Action: ${{data.action}}`;
                    noteText = `Step ${{s}}/${{m}}: Action ${{data.action}}`;
                }}
                if (dots) dots.style.display = 'inline-flex';
            }} else if (type === 'delegate') {{
                bar.classList.add('active');
                if (dot) dot.className = 'status-indicator-dot pulse';
                const s = data.step || 1;
                const m = data.max_steps || 15;
                badge.textContent = `STEP ${{s}}/${{m}}`;
                const recipient = (data.recipient || 'sub-agent').toUpperCase();
                const taskAction = data.task_action ? ` (${{data.task_action}})` : '';
                actionText.textContent = `Delegating to ${{recipient}}${{taskAction}}`;
                noteText = `Step ${{s}}/${{m}}: Delegating to ${{recipient}}${{taskAction}}`;
                if (dots) dots.style.display = 'inline-flex';
            }} else if (type === 'observation') {{
                bar.classList.add('active');
                if (dot) dot.className = 'status-indicator-dot pulse';
                const recipient = (data.recipient || 'sub-agent').toUpperCase();
                actionText.textContent = `Received feedback from ${{recipient}}`;
                noteText = `Received feedback from ${{recipient}}`;
                if (dots) dots.style.display = 'inline-flex';
            }} else if (type === 'finish') {{
                bar.classList.remove('active');
                if (dot) {{
                    dot.className = 'status-indicator-dot';
                    dot.style.background = '#10b981';
                    dot.style.boxShadow = '0 0 8px #10b981';
                }}
                badge.textContent = data.step ? `STEP ${{data.step}} COMPLETE` : 'COMPLETED';
                actionText.textContent = 'Objective accomplished';
                if (dots) dots.style.display = 'none';
            }} else if (type === 'error') {{
                bar.classList.remove('active');
                if (dot) {{
                    dot.className = 'status-indicator-dot';
                    dot.style.background = '#f43f5e';
                    dot.style.boxShadow = '0 0 8px #f43f5e';
                }}
                badge.textContent = 'ERROR';
                actionText.textContent = data.message || 'Execution error';
                if (dots) dots.style.display = 'none';
            }}

            // Also update the active pending note in chat thread
            if (noteText) {{
                const targetQId = data.query_id !== undefined ? data.query_id : currentQueryId;
                const curNote = document.getElementById('chatPendingNote-' + targetQId);
                if (curNote) curNote.textContent = noteText;
            }}
        }}

        // ================= LIVE SPOKEN SUBTITLES (SYNCHRONIZED WITH AUDIO) =================
        let activeVoiceSubtitleTimer = null;

        function stopVoiceSubtitles() {{
            if (activeVoiceSubtitleTimer) {{
                clearTimeout(activeVoiceSubtitleTimer);
                activeVoiceSubtitleTimer = null;
            }}
            const cursor = document.getElementById('voiceSubtitleCursor');
            if (cursor) cursor.remove();
        }}

        function streamVoiceSubtitles(text) {{
            stopVoiceSubtitles();
            const vrBox = document.getElementById('voiceResponseText');
            if (!vrBox) return;

            if (!text || !text.trim()) {{
                vrBox.textContent = '';
                return;
            }}

            const cleanText = text.trim();
            const words = cleanText.split(/\\s+/);
            if (words.length === 0) return;

            vrBox.innerHTML = '<span id="voiceSubtitleContent"></span><span id="voiceSubtitleCursor" class="typewriter-cursor">▎</span>';
            const contentElem = document.getElementById('voiceSubtitleContent');

            let currentWordIdx = 0;
            let accumulatedText = '';

            function showNextWord() {{
                if (currentWordIdx >= words.length) {{
                    stopVoiceSubtitles();
                    if (contentElem) contentElem.textContent = cleanText;
                    return;
                }}

                const word = words[currentWordIdx];
                accumulatedText += (currentWordIdx > 0 ? ' ' : '') + word;
                if (contentElem) contentElem.textContent = accumulatedText;

                // Synchronized with Piper TTS natural speech pace (~310ms base + punctuation pause)
                let delay = 310;
                if (/[,;]$/.test(word)) {{
                    delay += 140;
                }} else if (/[.!?]$/.test(word)) {{
                    delay += 240;
                }} else if (/\\.\\.\\.$/.test(word)) {{
                    delay += 340;
                }}

                currentWordIdx++;
                activeVoiceSubtitleTimer = setTimeout(showNextWord, delay);
            }}

            showNextWord();
        }}

        // ================= FAST MARKDOWN TEXT STREAM (INTO CHAT BUBBLE) =================
        let activeMarkdownTimer = null;
        let activeFullMarkdown = '';
        let activeStreamingQueryId = null;

        function stopMarkdownStream() {{
            if (activeMarkdownTimer) {{
                clearInterval(activeMarkdownTimer);
                activeMarkdownTimer = null;
            }}
        }}

        function streamMarkdownIntoBubble(bubbleElem, markdownText, queryId) {{
            stopMarkdownStream();
            if (!bubbleElem) return;

            if (!markdownText || !markdownText.trim()) {{
                bubbleElem.innerHTML = '';
                return;
            }}

            activeFullMarkdown = markdownText.trim();
            activeStreamingQueryId = queryId;
            const tokens = activeFullMarkdown.split(/(\\s+)/);
            if (tokens.length <= 1) {{
                bubbleElem.innerHTML = parseMarkdown(activeFullMarkdown);
                bubbleElem.querySelectorAll('a').forEach(a => {{
                    a.setAttribute('target', '_blank');
                    a.setAttribute('rel', 'noopener noreferrer');
                }});
                scrollChatToBottom();
                return;
            }}

            // Fast markdown stream: ~28ms per step, completes smoothly in ~1.5 - 2s
            const totalTokens = tokens.length;
            const targetDurationMs = Math.min(2200, Math.max(700, totalTokens * 16));
            const stepIntervalMs = 28;
            const totalSteps = Math.max(1, Math.floor(targetDurationMs / stepIntervalMs));
            const tokensPerStep = Math.max(1, Math.ceil(totalTokens / totalSteps));

            let currentTokenIdx = 0;
            let accumulatedMd = '';

            bubbleElem.classList.remove('fadeInUp');
            void bubbleElem.offsetWidth;
            bubbleElem.classList.add('fadeInUp');

            activeMarkdownTimer = setInterval(() => {{
                const nextIdx = Math.min(tokens.length, currentTokenIdx + tokensPerStep);
                for (let i = currentTokenIdx; i < nextIdx; i++) {{
                    accumulatedMd += tokens[i];
                }}
                currentTokenIdx = nextIdx;

                bubbleElem.innerHTML = parseMarkdown(accumulatedMd);
                bubbleElem.querySelectorAll('a').forEach(a => {{
                    a.setAttribute('target', '_blank');
                    a.setAttribute('rel', 'noopener noreferrer');
                }});
                scrollChatToBottom();

                if (currentTokenIdx >= tokens.length) {{
                    stopMarkdownStream();
                    bubbleElem.innerHTML = parseMarkdown(activeFullMarkdown);
                    bubbleElem.querySelectorAll('a').forEach(a => {{
                        a.setAttribute('target', '_blank');
                        a.setAttribute('rel', 'noopener noreferrer');
                    }});
                    scrollChatToBottom();
                }}
            }}, stepIntervalMs);
        }}

        // Backward compatibility wrapper for existing tests
        function streamMarkdownOutput(markdownText) {{
            const bubble = document.getElementById('chatBubble-' + currentQueryId);
            if (bubble) {{
                streamMarkdownIntoBubble(bubble, markdownText, currentQueryId);
            }} else {{
                const mdBox = document.getElementById('markdownOutput');
                if (mdBox) mdBox.innerHTML = parseMarkdown(markdownText);
            }}
        }}

        function appendLog(ts, source, message, rawData = null) {{
            const screen = document.getElementById('terminalScreen');
            if (!screen) return;

            const line = document.createElement('div');
            line.className = 'log-line';
            line.dataset.source = source;

            // Apply filter
            if (currentFilter !== 'all' && source !== currentFilter) {{
                line.style.display = 'none';
            }}

            let tagClass = 'tag-hub';
            if (source.includes('kaalu')) tagClass = 'tag-kaalu';
            else if (source.includes('faulkner')) tagClass = 'tag-faulkner';
            else if (source.includes('android')) tagClass = 'tag-android';
            else if (source.includes('sys')) tagClass = 'tag-system';

            line.innerHTML = `
                <span class="log-ts">${{ts}}</span>
                <span class="log-tag ${{tagClass}}">${{source.toUpperCase()}}</span>
                <span class="log-msg">${{escapeHtml(message)}}</span>
            `;

            screen.appendChild(line);

            if (autoScroll) {{
                screen.scrollTop = screen.scrollHeight;
            }}
        }}

        function escapeHtml(text) {{
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}

        function filterLogs(src) {{
            currentFilter = src;
            document.querySelectorAll('.filter-btn').forEach(btn => {{
                btn.classList.toggle('active', btn.dataset.filter === src);
            }});
            document.querySelectorAll('.log-line').forEach(line => {{
                if (src === 'all' || line.dataset.source === src) {{
                    line.style.display = 'flex';
                }} else {{
                    line.style.display = 'none';
                }}
            }});
        }}

        function clearTerminal() {{
            const screen = document.getElementById('terminalScreen');
            if (screen) {{
                screen.innerHTML = '<div class="log-line"><span class="log-ts">SYS</span><span class="log-tag tag-hub">HUB</span><span class="log-msg">Terminal buffer cleared.</span></div>';
            }}
        }}

        function toggleAutoScroll() {{
            autoScroll = !autoScroll;
            const btn = document.getElementById('autoScrollBtn');
            if (btn) btn.textContent = '📜 Auto-Scroll: ' + (autoScroll ? 'ON' : 'OFF');
        }}

        function copyTerminalLogs() {{
            const screen = document.getElementById('terminalScreen');
            if (screen) {{
                navigator.clipboard.writeText(screen.innerText).then(() => {{
                    alert('Terminal logs copied to clipboard.');
                }});
            }}
        }}

        // ================= GOAL SUBMISSION =================
        async function executeGoal(goalText) {{
            if (!goalText || !goalText.trim()) return;
            const goal = goalText.trim();

            stopActiveVoice();
            stopVoiceSubtitles();

            // Finalize any previously streaming markdown bubble immediately before starting new query
            if (activeMarkdownTimer && activeStreamingQueryId !== null) {{
                const prevBubble = document.getElementById('chatBubble-' + activeStreamingQueryId);
                if (prevBubble && activeFullMarkdown) {{
                    prevBubble.innerHTML = parseMarkdown(activeFullMarkdown);
                    prevBubble.querySelectorAll('a').forEach(a => {{
                        a.setAttribute('target', '_blank');
                        a.setAttribute('rel', 'noopener noreferrer');
                    }});
                }}
                stopMarkdownStream();
            }}

            currentQueryId++;
            const thisQueryId = currentQueryId;
            const timeStr = formatCurrentTime();

            appendLog(timeStr, 'kaalu', 'User Objective: ' + goal);
            setHologramState('reasoning');

            // 1. Append User Message Bubble to persistent chat history
            appendUserMessage(goal, thisQueryId, timeStr);

            // 2. Append Pending Kaalu Card to persistent chat history
            appendPendingKaaluMessage(goal, thisQueryId, timeStr);

            // 3. Update Step Status Bar on avatar
            updateStepStatus({{
                type: 'start',
                source: 'kaalu',
                goal: goal,
                query_id: thisQueryId,
                message: 'Initiating objective: ' + goal
            }});

            const vrBox = document.getElementById('voiceResponseText');
            if (vrBox) {{
                vrBox.innerHTML = '<span style="color: #64748b; font-style: italic;">Awaiting Kaalu response...</span>';
            }}

            const vt = document.getElementById('voiceTranscript');
            if (vt) vt.textContent = 'Processing: "' + goal + '"...';

            try {{
                const resp = await fetch('/api/kaalu/goal', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ goal: goal, query_id: thisQueryId }})
                }});
                const data = await resp.json();
                if (data.final_answer) {{
                    renderOutput(data.final_answer, data.voice_response, thisQueryId, data.superseded === true, data.is_latest === false);
                }}
            }} catch (err) {{
                console.error('Goal submission failed:', err);
                appendLog('ERR', 'system', 'Execution error: ' + err.message);
                updateStepStatus({{
                    type: 'error',
                    query_id: thisQueryId,
                    message: 'Execution error: ' + err.message
                }});
                const bubble = document.getElementById('chatBubble-' + thisQueryId);
                if (bubble) {{
                    bubble.innerHTML = '<p style="color: #f43f5e;"><strong>Execution error:</strong> ' + escapeHtml(err.message) + '</p>';
                }}
                setHologramState('idle');
            }}
        }}

        function submitTerminalCommand() {{
            const inp = document.getElementById('terminalInput');
            if (!inp || !inp.value.trim()) return;
            const cmd = inp.value.trim();
            commandHistory.push(cmd);
            historyIndex = commandHistory.length;
            inp.value = '';
            executeGoal(cmd);
        }}

        function submitAssistantInput() {{
            const inp = document.getElementById('assistantInput');
            if (!inp || !inp.value.trim()) return;
            const val = inp.value.trim();
            inp.value = '';
            executeGoal(val);
        }}

        // Terminal input keyboard navigation
        document.addEventListener('DOMContentLoaded', () => {{
            const termInput = document.getElementById('terminalInput');
            if (termInput) {{
                termInput.addEventListener('keydown', (e) => {{
                    if (e.key === 'Enter') {{
                        submitTerminalCommand();
                    }} else if (e.key === 'ArrowUp') {{
                        if (historyIndex > 0) {{
                            historyIndex--;
                            termInput.value = commandHistory[historyIndex] || '';
                        }}
                    }} else if (e.key === 'ArrowDown') {{
                        if (historyIndex < commandHistory.length - 1) {{
                            historyIndex++;
                            termInput.value = commandHistory[historyIndex] || '';
                        }} else {{
                            historyIndex = commandHistory.length;
                            termInput.value = '';
                        }}
                    }}
                }});
            }}

            const asstInput = document.getElementById('assistantInput');
            if (asstInput) {{
                asstInput.addEventListener('keydown', (e) => {{
                    if (e.key === 'Enter') {{
                        submitAssistantInput();
                    }}
                }});
            }}

            const wts = document.getElementById('welcomeTimestamp');
            if (wts) wts.textContent = formatCurrentTime();

            initTerminalWs();
            initSpeechRecognition();
        }});

        // ================= TAB 2: SPEECH RECOGNITION (EARS) & INTERRUPT =================
        function isEchoOfKaalu(text) {{
            if (!text || !lastSpokenText) return false;
            const cand = text.toLowerCase().trim().replace(/^[,.!?\\s]+|[,.!?\\s]+$/g, '');
            if (cand.length < 4) return false;
            if (lastSpokenText.includes(cand)) return true;
            const candWords = cand.split(/\\s+/).filter(w => w.length > 2);
            if (candWords.length >= 3) {{
                let match = 0;
                for (const w of candWords) {{
                    if (lastSpokenText.includes(w)) match++;
                }}
                if (match / candWords.length >= 0.75) return true;
            }}
            return false;
        }}

        function updateVoiceStatus(state, message) {{
            const ind = document.getElementById('voiceIndicator');
            const dot = document.getElementById('voiceStatusDot');
            const txt = document.getElementById('voiceStatusText');
            const btn = document.getElementById('micToggleLabel');
            if (txt && message) txt.textContent = message;

            if (!ind || !dot) return;

            if (state === 'active') {{
                ind.className = 'voice-indicator active';
                dot.style.background = '#38bdf8';
                dot.style.boxShadow = '0 0 8px #38bdf8';
                if (btn) btn.textContent = 'Mute Microphone';
            }} else if (state === 'hearing') {{
                ind.className = 'voice-indicator active';
                dot.style.background = '#f59e0b';
                dot.style.boxShadow = '0 0 10px #f59e0b';
            }} else if (state === 'blocked') {{
                ind.className = 'voice-indicator';
                dot.style.background = '#f43f5e';
                dot.style.boxShadow = '0 0 8px #f43f5e';
                if (btn) btn.textContent = 'Enable Microphone';
            }} else if (state === 'reconnecting') {{
                ind.className = 'voice-indicator';
                dot.style.background = '#a855f7';
                dot.style.boxShadow = '0 0 8px #a855f7';
            }} else if (state === 'muted') {{
                ind.className = 'voice-indicator';
                dot.style.background = '#64748b';
                dot.style.boxShadow = 'none';
                if (btn) btn.textContent = 'Enable Microphone';
            }}
        }}

        function setupSpeechRecognition() {{
            const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRec) {{
                const vt = document.getElementById('voiceTranscript');
                if (vt) vt.textContent = 'Web Speech API not supported in this browser. Use Chrome or Edge.';
                updateVoiceStatus('blocked', '⚠️ Web Speech API Unavailable');
                return null;
            }}

            if (recognition) {{
                try {{
                    recognition.onstart = null;
                    recognition.onend = null;
                    recognition.onerror = null;
                    recognition.onresult = null;
                    recognition.onspeechstart = null;
                    recognition.onaudiostart = null;
                    recognition.abort();
                }} catch (e) {{}}
                recognition = null;
            }}

            try {{
                recognition = new SpeechRec();
                recognition.continuous = true;
                recognition.interimResults = true;
                recognition.lang = 'en-US';
                recognition.maxAlternatives = 1;

                recognition.onstart = () => {{
                    isRecognizing = true;
                    isStartingRecognition = false;
                    updateVoiceStatus('active', '🎙️ Kaalu Ears Active (Listening...)');
                }};

                recognition.onaudiostart = () => {{
                    isRecognizing = true;
                    const ring = document.getElementById('hologramRing');
                    if (ring && !ring.classList.contains('reasoning') && !ring.classList.contains('speaking')) {{
                        ring.classList.add('hearing');
                    }}
                }};

                // When speech begins -> STOP ANY ACTIVE VOICE IMMEDIATELY & START ANIMATION
                recognition.onspeechstart = () => {{
                    console.log('User speech detected: Stopping active voice playback.');
                    stopActiveVoice();
                    setHologramState('hearing');
                    updateVoiceStatus('hearing', '👂 Hearing speech...');
                }};

                recognition.onresult = (event) => {{
                    let interim = '';
                    let finalTranscript = '';

                    for (let i = event.resultIndex; i < event.results.length; ++i) {{
                        if (event.results[i].isFinal) {{
                            finalTranscript += event.results[i][0].transcript;
                        }} else {{
                            interim += event.results[i][0].transcript;
                        }}
                    }}

                    const vt = document.getElementById('voiceTranscript');
                    if (interim && vt) {{
                        vt.textContent = 'Hearing: "' + interim + '"...';
                        if (isKaaluSpeaking) {{
                            stopActiveVoice();
                            setHologramState('hearing');
                        }}
                    }}

                    if (finalTranscript && finalTranscript.trim()) {{
                        const cleanGoal = finalTranscript.trim();
                        // Ignore self-echo if microphone picked up Kaalu's own TTS output
                        if (isEchoOfKaalu(cleanGoal)) {{
                            console.log('Filtered out acoustic echo of Kaalu voice:', cleanGoal);
                            if (vt) vt.textContent = 'Ready for objective...';
                            return;
                        }}

                        if (vt) vt.textContent = 'Understood: "' + cleanGoal + '"';
                        executeGoal(cleanGoal);
                    }}
                }};

                recognition.onerror = (event) => {{
                    console.warn('Speech recognition error:', event.error);
                    isStartingRecognition = false;
                    if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {{
                        isRecognizing = false;
                        updateVoiceStatus('blocked', '🚫 Mic Access Blocked - Click to Allow');
                        const vt = document.getElementById('voiceTranscript');
                        if (vt) vt.textContent = 'Microphone blocked. Click "Enable Microphone" to grant access.';
                    }} else if (event.error === 'network') {{
                        updateVoiceStatus('reconnecting', '🔄 Reconnecting speech engine...');
                        scheduleRecognitionRestart(1200);
                    }} else if (event.error === 'no-speech') {{
                        // Standard Chrome timeout after silence - will restart cleanly
                    }} else if (event.error !== 'aborted') {{
                        const vt = document.getElementById('voiceTranscript');
                        if (vt) vt.textContent = 'Speech note: ' + event.error;
                    }}
                }};

                recognition.onend = () => {{
                    isRecognizing = false;
                    isStartingRecognition = false;
                    const ring = document.getElementById('hologramRing');
                    if (ring && ring.classList.contains('hearing')) {{
                        ring.classList.remove('hearing');
                    }}
                    if (micActive) {{
                        scheduleRecognitionRestart(250);
                    }} else {{
                        updateVoiceStatus('muted', '🔇 Microphone Muted');
                    }}
                }};

                return recognition;
            }} catch (err) {{
                console.error('Speech recognition setup failed:', err);
                isStartingRecognition = false;
                return null;
            }}
        }}

        function scheduleRecognitionRestart(delayMs = 300) {{
            if (!micActive) return;
            if (restartTimer) clearTimeout(restartTimer);
            restartTimer = setTimeout(() => {{
                safeStartRecognition();
            }}, delayMs);
        }}

        function safeStartRecognition() {{
            if (!micActive || isRecognizing || isStartingRecognition) return;
            isStartingRecognition = true;

            if (!recognition) {{
                setupSpeechRecognition();
            }}

            try {{
                recognition.start();
            }} catch (e) {{
                isStartingRecognition = false;
                if (e.name === 'InvalidStateError' || (e.message && e.message.includes('already started'))) {{
                    isRecognizing = true;
                }} else {{
                    console.warn('Speech start note, resetting instance:', e.message);
                    setupSpeechRecognition();
                    scheduleRecognitionRestart(600);
                }}
            }}
        }}

        function initSpeechRecognition() {{
            setupSpeechRecognition();
            safeStartRecognition();

            // Periodic watchdog to keep ears perpetually active
            setInterval(() => {{
                if (micActive && !isRecognizing && !isStartingRecognition) {{
                    safeStartRecognition();
                }}
            }}, 4000);

            // Re-arm on window focus or user click anywhere on page (satisfies Chrome gesture requirement)
            window.addEventListener('focus', () => {{
                if (micActive && !isRecognizing) {{
                    safeStartRecognition();
                }}
            }});

            document.addEventListener('click', () => {{
                if (micActive && !isRecognizing) {{
                    safeStartRecognition();
                }}
            }}, {{ once: false }});
        }}

        async function toggleMic() {{
            micActive = !micActive;
            const btn = document.getElementById('micToggleLabel');
            if (micActive) {{
                if (btn) btn.textContent = 'Mute Microphone';
                updateVoiceStatus('active', '🎙️ Kaalu Ears Active (Listening...)');
                const vt = document.getElementById('voiceTranscript');
                if (vt) vt.textContent = 'Listening for your voice...';

                // Request mic permission on user gesture
                if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {{
                    try {{
                        const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
                        stream.getTracks().forEach(t => t.stop());
                    }} catch (permErr) {{
                        console.warn('Mic permission error:', permErr);
                    }}
                }}

                setupSpeechRecognition();
                safeStartRecognition();
            }} else {{
                if (btn) btn.textContent = 'Enable Microphone';
                updateVoiceStatus('muted', '🔇 Microphone Muted');
                const vt = document.getElementById('voiceTranscript');
                if (vt) vt.textContent = 'Microphone muted. Type objective or click to enable.';
                if (restartTimer) clearTimeout(restartTimer);
                if (recognition) {{
                    try {{ recognition.abort(); }} catch (e) {{}}
                }}
                isRecognizing = false;
                isStartingRecognition = false;
            }}
        }}

        async function stopActiveVoice() {{
            const wasSpeaking = isKaaluSpeaking;
            isKaaluSpeaking = false;
            if (speakingTimeout) {{
                clearTimeout(speakingTimeout);
                speakingTimeout = null;
            }}
            stopVoiceSubtitles();
            setHologramState('idle');

            if (termWs && termWs.readyState === WebSocket.OPEN) {{
                try {{
                    termWs.send(JSON.stringify({{ action: 'stop_voice' }}));
                }} catch (e) {{}}
            }}

            try {{
                await fetch('/voice/stop', {{ method: 'POST' }});
                if (wasSpeaking) {{
                    appendLog('SYS', 'hub', 'Voice playback interrupted.');
                }}
            }} catch (e) {{
                console.error('Stop voice failed:', e);
            }}
        }}

        function setHologramState(state) {{
            const ring = document.getElementById('hologramRing');
            if (!ring) return;
            ring.className = 'hologram-wrapper ' + state;

            const video = document.getElementById('avatarVideo');
            if (video && video.paused) {{
                video.play().catch(() => {{}});
            }}
        }}

        function renderOutput(finalAnswer, voiceResponse, queryId, superseded = false, isNotLatest = false) {{
            const qId = (queryId !== undefined && queryId !== null) ? Number(queryId) : currentQueryId;
            const now = Date.now();
            if (lastRenderedAnswer === finalAnswer && (now - lastRenderTime) < 1500 && lastRenderedQId === qId) {{
                return;
            }}
            lastRenderedAnswer = finalAnswer;
            lastRenderTime = now;
            lastRenderedQId = qId;

            let bubble = document.getElementById('chatBubble-' + qId);
            if (!bubble) {{
                const mdBox = document.getElementById('markdownOutput');
                if (mdBox) {{
                    const entry = document.createElement('div');
                    entry.className = 'chat-entry kaalu-entry';
                    entry.id = 'chatEntry-kaalu-' + qId;
                    entry.innerHTML = `
                        <div class="chat-entry-header">
                            <div class="chat-sender-info">
                                <span class="chat-avatar-icon chat-avatar-kaalu">🤖</span>
                                <span class="chat-sender-name">Project Kaalu</span>
                                <span class="chat-tag tag-kaalu" id="chatTag-${{qId}}">ASSISTANT</span>
                            </div>
                            <div class="chat-timestamp" id="chatTime-${{qId}}">${{formatCurrentTime()}}</div>
                        </div>
                        <div class="chat-bubble kaalu-bubble" id="chatBubble-${{qId}}"></div>
                    `;
                    mdBox.appendChild(entry);
                    bubble = document.getElementById('chatBubble-' + qId);
                }}
            }}

            const timeEl = document.getElementById('chatTime-' + qId);
            if (timeEl) {{
                timeEl.textContent = formatCurrentTime();
            }}
            const tagEl = document.getElementById('chatTag-' + qId);
            if (tagEl) {{
                tagEl.className = 'chat-tag tag-kaalu';
                tagEl.textContent = 'ASSISTANT';
            }}

            const spokenText = voiceResponse || finalAnswer || 'Sir, request accomplished.';

            // Query supersession rule:
            // If another query was submitted (qId < currentQueryId) OR superseded flag is true OR isNotLatest is true:
            // This is an OLDER query:
            // Just show it as chat in text output without voice audio or subtitles!
            const isSuperseded = (!isNaN(qId) && qId < currentQueryId) || superseded === true || isNotLatest === true;
            if (isSuperseded) {{
                console.log(`[Superseded] Query #${{qId}} completed but current active Query is #${{currentQueryId}}. Skipping voice output.`);
                if (bubble) {{
                    bubble.innerHTML = parseMarkdown(finalAnswer);
                    bubble.querySelectorAll('a').forEach(a => {{
                        a.setAttribute('target', '_blank');
                        a.setAttribute('rel', 'noopener noreferrer');
                    }});
                }}
                scrollChatToBottom();
                return;
            }}

            // LATEST active query:
            // 1. Spoken voice subtitles stream in sync with the audio
            streamVoiceSubtitles(spokenText);

            // 2. Stream Markdown text into bubble
            if (bubble) {{
                streamMarkdownIntoBubble(bubble, finalAnswer, qId);
            }}

            // 3. Set Hologram to speaking
            setHologramState('speaking');
            isKaaluSpeaking = true;
            lastSpokenText = (spokenText || '').toLowerCase();
            const words = (spokenText || '').split(/\\s+/).length;
            const speakDuration = Math.max(2500, Math.min(22000, words * 340));
            if (speakingTimeout) clearTimeout(speakingTimeout);
            speakingTimeout = setTimeout(() => {{
                isKaaluSpeaking = false;
                setHologramState('idle');
            }}, speakDuration);
        }}
    </script>
</body>
</html>
"""
