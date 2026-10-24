# book-reader-pi13

A word-by-word EPUB reader for a Raspberry Pi with a 240×240 screen and 12 physical buttons.

Books are shown one word at a time in the middle of the screen (RSVP-style speed reading). How long each word stays depends on its length and punctuation, and you can make the reading faster or slower, pause it, skip ahead or go back. Each book remembers where you stopped.

![Button layout](layout.png)

## Features

- Reads `.epub` files straight from the `books/` folder. No conversion needed.
- Word-by-word display with a delay that adapts to each word:
  - longer words stay on screen longer
  - words ending with `.` stay 2× longer, words ending with `,` stay 1.5× longer
- Adjustable speed in 10% steps, kept between 50% and 150% of the base delay.
- Pause/play, jump ±10 words, previous/next chapter.
- Five progress bars around the word (chapter, book in chapters, book in words, battery, delay), which can all be hidden with one button for distraction-free reading.
- Progress saved per book (chapter and word) in `book_progression.pkl`.
- Menus driven only by the physical buttons: main menu, books list (scrolling, titles cut to fit the screen), options. Selection wraps around from the last entry to the first.
- Eight themes: dark, light, matrix, pastel, sepia, red, blue and amber, chosen in **Options** and remembered in `settings.pkl` (dark on first launch).
- Interface in English, French or Spanish, chosen in **Options** and remembered in `settings.pkl` (English on first launch).
- "Exit to Debian" and "Shutdown Pi" from the main menu.
- Runs on Windows for development, with the keyboard standing in for the GPIO buttons.

## Requirements

- Python 3.9+ with tkinter
- On Windows (development): `pip install keyboard`
- On Raspberry Pi (Linux): `gpiozero` (preinstalled on Raspberry Pi OS, otherwise `pip install gpiozero`)

## Usage

1. Put your `.epub` files in the `books/` folder next to `run_ui.py`.
2. Start the reader:

   ```bash
   python run_ui.py
   ```

3. Open **Books list**, pick a book, and reading starts where you last stopped.

The script detects the platform on its own: on Windows it listens to the keyboard, on Linux it listens to the GPIO buttons.

> Every visible file in `books/` is listed, so keep only `.epub` files there: opening anything else fails.

## Controls

Each button is wired between its GPIO pin and ground; the internal pull-up is enabled. The key in the third column does the same thing as the button when running on Windows.

| Button              | GPIO | Key | While reading                     | In menus              |
|---------------------|------|-----|-----------------------------------|-----------------------|
| Left square (top)   | 23   | E   | Hide / show the progress bars     | —                     |
| Top left            | 19   | A   | Toggle fullscreen                 | Toggle fullscreen     |
| Left top            | 5    | Z   | *(reserved: voice reading)*       | —                     |
| Left left           | 16   | Q   | Previous chapter                  | —                     |
| Left right          | 13   | D   | Next chapter                      | —                     |
| Left down           | 6    | S   | Pause / play                      | —                     |
| Right square (top)  | 14   | U   | *(reserved: switch % / absolute)* | —                     |
| Top right           | 26   | O   | Save progress, back to books      | Back to main menu     |
| Right top           | 15   | I   | Faster (−10% delay)               | Move selection up     |
| Right left          | 12   | J   | Go back 10 words                  | —                     |
| Right right         | 21   | L   | Skip 10 words                     | Validate selection    |
| Right down          | 20   | K   | Slower (+10% delay)               | Move selection down   |

> Progress is saved when you leave a book with the top right button. Closing the program in any other way while reading loses the progress made in that session.

Jumps of 10 words stay inside the current chapter. Hiding the progress bars is kept while the program runs, even when you open another book.

## Reader screen

```
┌──────────────────────────────────┐
│ [▓▓▓░░░] Page  120 / 2 040 words │  current chapter, in words
│ [▓░░░░░] Book     3 / 27 pages   │  book, in chapters
│ [▓░░░░░] Words 9 500 / 81 000    │  book, in words
│                                  │
│             current              │
│                                  │
│ [▓▓▓░░░] Battery : 42 %          │
│ [▓▓▓░░░] Delay : 100%            │  empty = 50%, full = 150%
└──────────────────────────────────┘
```

Each bar fills with the accent color as it progresses, and its text stays readable on both the filled and the empty part. Large numbers are grouped by three with spaces (`81 000`).

"Pages" are the chapters of the EPUB (one per entry of the EPUB spine). The battery value is a placeholder for now. At the end of a chapter the screen shows "finished page": press next chapter to go on.

## Configuration

All settings are in the `CONFIGURATION` dictionary at the top of `run_ui.py`:

| Key                      | Default      | Purpose                                                   |
|--------------------------|--------------|-----------------------------------------------------------|
| `FULLSCREEN_ON_STARTUP`  | `False`      | Start in fullscreen                                       |
| `RESOLUTION`             | `"240x240"`  | Window size                                               |
| `BOOKS_FOLDER`           | `books/` next to the script | Where the EPUB files are                   |
| `BOOKS_VISIBLE_AT_ONCE`  | `4`          | Number of books shown at once in the list                 |
| `BOOK_PROGRESSION_FILE`  | `book_progression.pkl` next to the script | Saved progress of every book  |
| `SETTINGS_FILE`          | `settings.pkl` next to the script | Saved user settings (theme, language) |
| `GENERAL_DELAY`          | `0.15`       | Base delay (seconds) at 100% for a reference-size word    |
| `STEP_PERCENTAGE`        | `10`         | Speed change per button press                             |
| `MIN_DELAY_PERCENTAGE`   | `50`         | Lowest delay the user can set (fastest reading)           |
| `MAX_DELAY_PERCENTAGE`   | `150`        | Highest delay the user can set (slowest reading)          |
| `WORD_SIZE_REFERENCE`    | `5`          | Word length that gets exactly the base delay              |
| `OFFSET_DELAY_MS`        | `0.15`       | Constant delay (seconds) added to every word              |
| `DOT_DELAY`              | `2.0`        | Multiplier for words ending with `.`                      |
| `COMMA_DELAY`            | `1.5`        | Multiplier for words ending with `,`                      |
| `JUMP_WORDS_QTY`         | `10`         | Words skipped by the jump buttons                         |
| `WORD_FONT_SIZE`         | `42`         | Font size of the current word                             |
| `INFO_FONT_SIZE`         | `20`         | Font size of the progress bar texts                       |
| `LOGGING`                | `False`      | Print what the program does to the console                |

Display time of a word:

```
delay = OFFSET_DELAY_MS + punctuation × (len(word) / WORD_SIZE_REFERENCE) × GENERAL_DELAY × (speed% / 100)
```

Colors for the themes are in the `THEMES` dictionary, three per theme (`BASE_COLOR`, `SURFACE_COLOR`, `ACCENT_COLOR`). Each entry added there also appears in the options menu; add a `theme_<name>` key to `TRANSLATIONS` to give it a translated name.

Every on-screen text is in the `TRANSLATIONS` dictionary, one entry per language (`en`, `fr`, `es`). To add a language, copy the `en` block under a new code and translate its values: it then appears in the options menu. A missing key falls back to English.

Settings saved by older versions (with the `dark_mode` flag) are converted to the dark or light theme automatically.

## Raspberry Pi notes

- "Shutdown Pi" runs `sudo shutdown -h now`, so the user running the script needs passwordless sudo (the default `pi` user has it).
- On Windows, "Shutdown Pi" really shuts down the PC (`shutdown /s /t 0`): be careful while developing.
- To start the reader at boot, launch `python /path/to/run_ui.py` from the desktop autostart of your Pi.

## Project structure

```
book-reader-pi13/
├── run_ui.py               # the whole application
├── books/                  # your .epub files
├── book_progression.pkl    # saved progress (created automatically)
├── settings.pkl            # saved settings (created automatically)
└── layout.png              # button layout
```

## Roadmap

- Voice reading through a speaker (left top button)
- Switch the progress texts between percentage and absolute values (right square button)
- Real battery level
- Go to the next chapter automatically at the end of a chapter
- Save progress on exit and shutdown, not only when leaving a book
