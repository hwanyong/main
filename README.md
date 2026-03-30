# agbridge (Antigravity Bridge Daemon)

*Read this in other languages: [English](README.md), [한국어](README_ko.md)*

> [!CAUTION]
> **Terms of Service Warning — Read Before Installing**
> 
> This program is built purely for **experimental purposes**. While the tool functions as intended, **account stability cannot be guaranteed.** Google has been issuing ToS violation bans on accounts connected to unofficial proxies and automation tools like this one. 
>
> **Using this proxy is highly likely to violate Google's Terms of Service, and a small number of users have reported their Google accounts being banned or shadow-banned (restricted access without explicit notification). You must proceed at your own risk.**
>
> **By using this tool, you acknowledge and agree to the following:**
> - This is an unofficial tool not endorsed or approved by Google.
> - Your account may be suspended or permanently banned.
> - You assume all risks and responsibilities associated with using this proxy, including account loss or data loss.
>
> *"Don’t misuse our Services. For example, don’t interfere with our Services or try to access them using a method other than the interface and the instructions that we provide."* 
> — **Google Terms of Service**
>
> **Recommendation:** Do not use your main account. Use a burner account instead, and optionally add it to your main account's family plan if needed.

---

## 📖 Introduction

**agbridge (Antigravity Bridge Daemon Client)** is a parallel control and message queue routing tool designed to externally operate embedded AI agents within Visual Studio Code (VS Code) on macOS.

It acts as a bridge, allowing developers to control the usually sandboxed VS Code AI agent panels using external CLI commands by leveraging macOS's built-in Accessibility API. Through this tool, you can send prompts to AI agents on a per-workspace basis and manage independent conversation sessions directly from your terminal environment.

## ✨ Features

- **Parallel Agent Control**: Send prompts to AI agents running across multiple VS Code windows (workspaces) simultaneously using an external terminal command (`agbridge ask`).
- **Message Queue Routing**: Even if multiple scripts or processes attempt to input simultaneously, the central daemon manages the queue to ensure messages are delivered to agents sequentially without conflict.
- **Stateful Session Management**: Gives a stateless IDE panel UI environment persistent state. It caches chat history and progress within a `.ag-sessions` directory in each project, allowing users to list past sessions (`session list`) and reconnect (`session connect`).
- **Workspace Isolation**: Using the `--workspace` option, the tool can target background project windows accurately, keeping instructions isolated to the specified workspace even if it's not currently focused.
- **Global Input Locking**: Prevents race conditions, mouse focus hijacking, and keyboard input leaks during the split-second transmission of commands to the AI panel, ensuring perfectly isolated typing.

## ⚙️ Implementation Principles

This program operates based on the following technical principles:

1. **macOS Accessibility API (AXUIElement)**  
   Instead of bypassing web API limits or reverse-engineering unofficial internal WebSockets, `agbridge` retrieves the native macOS accessibility tree to dynamically locate and manipulate (UI Automation) VS Code elements on the screen (such as text areas and submit buttons). 
2. **Daemon-Client Architecture**  
   When a user invokes the `agbridge` CLI, the command payload is sent via IPC or sockets to a permanently running background daemon (`LaunchAgent`). The daemon exclusively handles all the complex thread management and queuing required for direct UI manipulation.
3. **DOM-based Layout Scraping**  
   It periodically (or forcibly via `info --refresh`) scrapes the accessibility tree of the IDE panel to extract active AI runtime environments, chatbot model info, and the titles of open sessions, caching them in `registry.json` for lightning-fast retrieval.
