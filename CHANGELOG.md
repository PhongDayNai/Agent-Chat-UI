# Changelog

All notable changes to Agent Chat UI are documented in this file.

## [2.1] - 2026-05-08

### Added

- Added work progress phase that shows "Working for Xs" during AI response generation
- Added final answer split protocol with `[[final_answer]]` marker
- Added runtime limits controls in config

### Changed

- Reordered ThinkingPhaseHeader layout: title → timer → arrow with reduced spacing
- Changed "Worked" to "Worked for {timer}" in work summary header
- Rendered assistant messages as phased timeline with collapsible work phases
- Collapsed work phases during final answers for cleaner presentation

## [2.0] - 2026-04-30

### Added

- Added Chat, Character, and Agent modes with mode-specific controls.
- Added Character Mode with synced character profiles, favorites, and per-character capability overrides for files, URLs, and terminal access.
- Added Agent Mode as the focused home for terminal-assisted local workflows.
- Added message builder helpers so each mode can compose prompts with the right system, character, attachment, URL, and terminal context.
- Added a message header with title, subtitle, and optional context usage display.
- Added per-mode context usage settings in the config file. Agent Mode shows context usage by default; Chat and Character modes keep it hidden by default.
- Added runtime context window detection for compatible servers through `/slots`, `/props`, and model metadata fallback.
- Added token counting through server `/tokenize`, optional local tokenizer fallback, and a final character-count estimate fallback.
- Added a small loading animation for streamed completion token counts, then replaced it with the final token count when streaming finishes.

### Changed

- Refactored the main window into focused mixins to keep the codebase easier to maintain.
- Polished the sidebar and mode controls so connected server settings and character controls take less space.
- Refined the default prompt behavior to answer in the user's language and mirror the user's style of address.
- Improved file-only message behavior with better default text for new attachments and references to related previous attachments.
- Improved streaming auto-follow behavior so the chat follows long responses when the user is at the bottom and stops following when the user scrolls away.
- Hid the vertical chat scrollbar to reduce visual noise.
- Updated the context usage arrow icon to render in green.

### Fixed

- Fixed chat auto-follow not re-enabling after the user scrolled back to the bottom while a response was still streaming.
- Fixed streaming focus behavior that could pull the view back to the latest token while the user was trying to scroll away.
- Fixed scrollbar flicker during long streamed responses.
- Fixed a missing clipboard image directory import in widget code.

## [1.2] - 2026-04-27

### Added

- Added OS keychain storage for API key secrets.
- Added keychain verification documentation.

### Changed

- Continued storing API key metadata in the app config while moving secret values into the operating system keychain when available.

[2.1]: https://github.com/PhongDayNai/Agent-Chat-UI/compare/v2.0...HEAD
[2.0 beta]: https://github.com/PhongDayNai/Agent-Chat-UI/compare/v1.2...v2.0
[1.2]: https://github.com/PhongDayNai/Agent-Chat-UI/releases/tag/v1.2
