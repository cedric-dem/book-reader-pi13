import html
import os
import pickle
import queue
import re
import subprocess
import sys
import tkinter as tk
import tkinter.font as tkfont
import xml.etree.ElementTree as ET
import zipfile
from pathlib import PurePosixPath

CONFIGURATION = {
    # True: the app starts in fullscreen, False: it starts in a RESOLUTION sized window
    "FULLSCREEN_ON_STARTUP": True,
    "RESOLUTION": "240x240",
    # Folder containing the books, next to this script
    "BOOKS_FOLDER": os.path.join(os.path.dirname(os.path.abspath(__file__)), "books"),
    # How many books fit on the 240x240 screen at once, the list scrolls with the selection
    "BOOKS_VISIBLE_AT_ONCE": 4,
    # Reading progression of every book (page and word index), saved next to this script
    "BOOK_PROGRESSION_FILE": os.path.join(os.path.dirname(os.path.abspath(__file__)), "book_progression.pkl"),
    # User settings changed from the options menu (e.g. the theme), saved next to this script
    "SETTINGS_FILE": os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.pkl"),

    # --- Word by word reading (same values as UI_reader/config.py) ---
    "GENERAL_DELAY": 0.15,  # initial delay for 100% speed and word size reference
    "STEP_PERCENTAGE": 10,  # percentage granularity of speed setting
    "WORD_SIZE_REFERENCE": 5,  # words longer than that will be displayed for longer
    "OFFSET_DELAY_MS": 0.15,  # constant offset
    "DOT_DELAY": 2.0,  # words ending with dot will take this as long
    "COMMA_DELAY": 1.5,  # words ending with comma will take this as long
    "JUMP_WORDS_QTY": 10,  # jump that amount when required
    # Font sizes of the reader screen, scaled down for the 240x240 screen
    "WORD_FONT_SIZE": 42,
    "INFO_FONT_SIZE": 20,
}

# Colors used by every screen, one set per theme (chosen in the options menu, in this order)
THEMES = {
    "dark": {
        "BACKGROUND_COLOR": "#0F0F0F",
        "BUTTON_COLOR": "#2A2A2A",
        "BUTTON_ACTIVE_COLOR": "#444444",
        "TEXT_COLOR": "#FFFFFF",
        "HIGHLIGHT_COLOR": "#FFFFFF",  # background of the selected menu entry
        "HIGHLIGHT_TEXT_COLOR": "#0F0F0F",  # text of the selected menu entry
    },
    "light": {
        "BACKGROUND_COLOR": "#F2F2F2",
        "BUTTON_COLOR": "#D9D9D9",
        "BUTTON_ACTIVE_COLOR": "#BFBFBF",
        "TEXT_COLOR": "#111111",
        "HIGHLIGHT_COLOR": "#111111",
        "HIGHLIGHT_TEXT_COLOR": "#F2F2F2",
    },
    "matrix": {  # green text on a black background
        "BACKGROUND_COLOR": "#000000",
        "BUTTON_COLOR": "#0A1F0A",
        "BUTTON_ACTIVE_COLOR": "#143D14",
        "TEXT_COLOR": "#00FF41",
        "HIGHLIGHT_COLOR": "#00FF41",
        "HIGHLIGHT_TEXT_COLOR": "#000000",
    },
    "pastel": {  # soft lavender and pink tones with dark plum text
        "BACKGROUND_COLOR": "#FDF6F0",
        "BUTTON_COLOR": "#E6DDF5",
        "BUTTON_ACTIVE_COLOR": "#D4C4EE",
        "TEXT_COLOR": "#4A3B5C",
        "HIGHLIGHT_COLOR": "#F7C6D9",
        "HIGHLIGHT_TEXT_COLOR": "#4A3B5C",
    },
}


def read_epub_file(epub_file_path: str) -> list[list[str]]:
    # Returns the book as a list of pages (one per chapter of the EPUB spine), each page a list of words
    with zipfile.ZipFile(epub_file_path) as epub_zip:
        container_xml = ET.fromstring(epub_zip.read("META-INF/container.xml"))
        rootfile_path = container_xml.find(
            ".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile"
        )

        if rootfile_path is None:
            raise ValueError("EPUB package file not found")

        package_path = rootfile_path.attrib.get("full-path", "")
        package_dir = PurePosixPath(package_path).parent
        package_xml = ET.fromstring(epub_zip.read(package_path))

        namespace = {"opf": "http://www.idpf.org/2007/opf"}
        manifest_by_id = {
            item.attrib["id"]: item.attrib["href"]
            for item in package_xml.findall(".//opf:manifest/opf:item", namespace)
            if item.attrib.get("id") and item.attrib.get("href")
        }

        pages: list[list[str]] = []
        for item_ref in package_xml.findall(".//opf:spine/opf:itemref", namespace):
            item_id = item_ref.attrib.get("idref")
            if not item_id or item_id not in manifest_by_id:
                continue

            chapter_path = package_dir / manifest_by_id[item_id]
            chapter_text = epub_zip.read(str(chapter_path)).decode("utf-8", errors="ignore")
            chapter_text = re.sub(r"<[^>]+>", " ", chapter_text)
            chapter_text = html.unescape(chapter_text)
            words = re.findall(r"\S+", chapter_text)

            pages.append(words)

        return pages


def load_state_if_any():
    print("=> load prog")
    progression_file = CONFIGURATION["BOOK_PROGRESSION_FILE"]
    if os.path.exists(progression_file):
        with open(progression_file, "rb") as f:
            data = pickle.load(f)
            return data
    else:
        return {}


def save_current_state(current_book, current_page_index, current_word_index):
    print("=> save prog")
    current_state = load_state_if_any()

    # add current book
    current_state[current_book] = {"current_page_index": current_page_index, "current_word_index": current_word_index}

    # save progression
    with open(CONFIGURATION["BOOK_PROGRESSION_FILE"], "wb") as f:
        pickle.dump(current_state, f)


# Settings used on first launch, when no settings file exists yet
DEFAULT_SETTINGS = {
    "theme": "dark",  # one of the THEMES names
}


def load_settings():
    settings = dict(DEFAULT_SETTINGS)
    settings_file = CONFIGURATION["SETTINGS_FILE"]
    if os.path.exists(settings_file):
        with open(settings_file, "rb") as f:
            settings.update(pickle.load(f))
    # Settings saved by older versions only had "dark_mode" (True/False): turn it into a theme
    if "dark_mode" in settings:
        dark_mode = settings.pop("dark_mode")
        if settings["theme"] == DEFAULT_SETTINGS["theme"]:
            settings["theme"] = "dark" if dark_mode else "light"
    # Unknown theme name (e.g. removed from THEMES): back to the default one
    if settings["theme"] not in THEMES:
        settings["theme"] = DEFAULT_SETTINGS["theme"]
    return settings


def save_settings(settings):
    print("=> save settings")
    with open(CONFIGURATION["SETTINGS_FILE"], "wb") as f:
        pickle.dump(settings, f)


class GUI():
    def __init__(self):
        self.root = tk.Tk()
        self.root.geometry(CONFIGURATION["RESOLUTION"])
        self.root.attributes("-fullscreen", CONFIGURATION["FULLSCREEN_ON_STARTUP"])

        self.settings = load_settings()
        self.theme_name = self.settings["theme"]
        self.screen_frame = None
        self.current_screen = None  # function that builds the screen currently displayed

        # Menu entries of the current screen: list of (label widget, callback)
        self.menu_items = []
        self.selected_index = 0
        # Scrolling: None = all entries shown, otherwise only this many entries are shown,
        # starting at first_visible_index
        self.visible_item_count = None
        self.first_visible_index = 0

        # Physical buttons (keyboard / GPIO) fire from other threads, and tkinter
        # must only be touched from the main thread. They push actions in this
        # queue, and the main loop executes them.
        self.pending_actions = queue.Queue()
        # Set when the window is destroyed: tkinter can't even be asked if the window
        # exists after that (winfo_exists raises an error), so we remember it ourselves
        self.is_closed = False

        # Reading state (same as ReaderState in UI_reader/main.py)
        self.current_book = None  # file name of the book being read
        self.pages_list = []  # pages of the current book, each page a list of words
        self.current_page_index = 0
        self.current_word_index = 0
        self.is_paused = False
        self.word_update_after_id = None  # id of the scheduled update_word, to cancel it
        self.speed_percentage = 100
        # Labels of the reader screen, created by create_reader
        self.current_word_label = None
        self.page_progression_label = None
        self.book_progression_label = None
        self.battery_label = None
        self.speed_label = None

        self.show_screen(self.create_main_menu)
        self.root.after(20, self.process_pending_actions)

    def run(self):
        # Blocks until the window is closed
        self.root.mainloop()

    def run_in_ui(self, action):
        # Thread safe: schedule an action to be run by the tkinter main loop
        self.pending_actions.put(action)

    def process_pending_actions(self):
        while not self.pending_actions.empty():
            action = self.pending_actions.get_nowait()
            action()
            if self.is_closed:
                return  # window was closed by the action (exit)
        self.root.after(20, self.process_pending_actions)

    # --- Theme / screen helpers ---
    @property
    def theme(self):
        return THEMES[self.theme_name]

    def show_screen(self, build_function, keep_selection=False):
        # Destroy the current screen and build a new one with the current theme
        previous_index = self.selected_index
        # Stop the word by word reading: its labels are destroyed with the screen
        self.cancel_word_update()
        if self.screen_frame is not None:
            self.screen_frame.destroy()
        self.root.configure(bg=self.theme["BACKGROUND_COLOR"])
        self.screen_frame = tk.Frame(self.root, bg=self.theme["BACKGROUND_COLOR"])
        self.screen_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.current_screen = build_function
        self.menu_items = []
        self.visible_item_count = None  # a screen that needs scrolling sets it in its build function
        self.first_visible_index = 0
        build_function()

        if keep_selection and previous_index < len(self.menu_items):
            self.selected_index = previous_index
        else:
            self.selected_index = 0
        self.update_highlight()

    def make_title(self, text, pack=True):
        title = tk.Label(self.screen_frame, text=text,
                         bg=self.theme["BACKGROUND_COLOR"], fg=self.theme["TEXT_COLOR"],
                         font=("Helvetica", 14, "bold"))
        if pack:
            title.pack(pady=(0, 8))
        return title

    def make_menu_item(self, text, callback, pack=True):
        # A Label, not a Button: entries can't be clicked, only selected with the physical buttons
        item = tk.Label(self.screen_frame, text=text,
                        bg=self.theme["BUTTON_COLOR"], fg=self.theme["TEXT_COLOR"],
                        font=("Helvetica", 11))
        if pack:
            item.pack(fill="x", expand=True, pady=3)
        self.menu_items.append((item, callback))
        return item

    def place_in_rows(self, widgets, first_row=0, width=0.90, height=0.15, margin=0.025):
        # Stack the widgets from the top (starting at row "first_row"), each one centered horizontally,
        # "width" and "height" of the screen, with "margin" of blank space above and below it
        row_height = margin + height + margin
        for row, widget in enumerate(widgets, start=first_row):
            widget.place(relx=(1 - width) / 2, rely=row * row_height + margin,
                         relwidth=width, relheight=height)

    # --- Menu navigation ---
    def update_highlight(self):
        if self.visible_item_count is not None:
            self.update_visible_items()
        for index, (item, _) in enumerate(self.menu_items):
            if index == self.selected_index:
                item.configure(bg=self.theme["HIGHLIGHT_COLOR"],
                               fg=self.theme["HIGHLIGHT_TEXT_COLOR"],
                               font=("Helvetica", 11, "bold"))
            else:
                item.configure(bg=self.theme["BUTTON_COLOR"],
                               fg=self.theme["TEXT_COLOR"],
                               font=("Helvetica", 11))

    def update_visible_items(self):
        # Move the visible window so the selected entry is always on screen
        if self.selected_index < self.first_visible_index:
            self.first_visible_index = self.selected_index
        elif self.selected_index >= self.first_visible_index + self.visible_item_count:
            self.first_visible_index = self.selected_index - self.visible_item_count + 1

        # Hide every entry, then show only the ones in the window (in order), in the rows below the title
        for item, _ in self.menu_items:
            item.place_forget()
        last_visible_index = self.first_visible_index + self.visible_item_count
        visible_items = [item for item, _ in self.menu_items[self.first_visible_index:last_visible_index]]
        self.place_in_rows(visible_items, first_row=1)

    def select_previous(self):
        if not self.menu_items:
            return
        # wraps around: from the first entry, go to the last one
        self.selected_index = (self.selected_index - 1) % len(self.menu_items)
        self.update_highlight()

    def select_next(self):
        if not self.menu_items:
            return
        # wraps around: from the last entry, go back to the first one
        self.selected_index = (self.selected_index + 1) % len(self.menu_items)
        self.update_highlight()

    def validate_selection(self):
        if not self.menu_items:
            return
        _, callback = self.menu_items[self.selected_index]
        callback()

    # --- Main menu ---
    def create_main_menu(self):
        # Sizes are percentages of the whole screen: no padding around this menu
        self.screen_frame.pack_configure(padx=0, pady=0)
        menu_entries = [
            ("Books list", self.open_books_list),
            ("Options", self.open_options),
            ("Exit to Debian", self.exit_to_debian),
            ("Shutdown Pi", self.shutdown_pi),
        ]
        # Title and buttons: 90% of the width, 15% of the height, 2.5% blank space above and below
        widgets = [self.make_title("Main menu", pack=False)]
        for label, callback in menu_entries:
            widgets.append(self.make_menu_item(label, callback, pack=False))
        self.place_in_rows(widgets)

    def open_books_list(self):
        print("Books list selected")
        self.show_screen(self.create_books_list)

    def open_options(self):
        print("Options selected")
        self.show_screen(self.create_options_menu)

    def exit_to_debian(self):
        print("Exit to Debian selected, closing the reader")
        # Closing the window ends mainloop, the end of the script then stops the button listeners
        self.is_closed = True
        self.root.destroy()

    def shutdown_pi(self):
        print("Shutdown Pi selected, shutting down the computer")
        if sys.platform.startswith('win'):
            command = ["shutdown", "/s", "/t", "0"]
        elif sys.platform.startswith('linux'):
            # needs sudo rights without password (default "pi" user on Raspberry Pi OS has them)
            command = ["sudo", "shutdown", "-h", "now"]
        else:
            print(f"Shutdown not supported on platform: {sys.platform}")
            return
        try:
            subprocess.run(command, check=True)
        except (OSError, subprocess.CalledProcessError) as error:
            print(f"Shutdown failed: {error}")

    # --- Books list ---
    def get_books(self):
        # File names of all the books, sorted alphabetically (ignoring upper/lower case)
        folder = CONFIGURATION["BOOKS_FOLDER"]
        if not os.path.isdir(folder):
            print(f"Books folder not found: {folder}")
            return []
        books = [name for name in os.listdir(folder)
                 if os.path.isfile(os.path.join(folder, name)) and not name.startswith(".")]
        return sorted(books, key=str.lower)

    def create_books_list(self):
        # Sizes are percentages of the whole screen: no padding around this list
        self.screen_frame.pack_configure(padx=0, pady=0)
        # Title and the visible books: 90% of the width, 15% of the height, 2.5% blank space above and below
        books = self.get_books()
        self.place_in_rows([self.make_title(f"Books : {len(books)}", pack=False)])
        if not books:
            # Plain text, not a menu entry: nothing to select, top right button goes back
            no_books_label = tk.Label(self.screen_frame, text="No books found",
                                      bg=self.theme["BACKGROUND_COLOR"], fg=self.theme["TEXT_COLOR"],
                                      font=("Helvetica", 11))
            self.place_in_rows([no_books_label], first_row=1)
            return

        self.visible_item_count = CONFIGURATION["BOOKS_VISIBLE_AT_ONCE"]
        # Longer book names are cut with "..." so they fill the whole width of the entry
        # (measured with the bold font of the selected entry, the widest of the two)
        bold_font = tkfont.Font(family="Helvetica", size=11, weight="bold")
        text_padding = 6  # blank space between the left edge of the entry and the book name
        available_width = int(self.screen_width() * 0.90) - 2 * text_padding - 4  # minus padding and border
        for book in books:
            name = os.path.splitext(book)[0]  # hide the ".epub" extension
            name = self.fit_text(name, bold_font, available_width)
            # default argument so each entry keeps its own book (not the last one of the loop)
            item = self.make_menu_item(name, lambda book=book: self.read_book(book), pack=False)
            item.configure(anchor="w", padx=text_padding)  # book names aligned left in their entry

    def screen_width(self):
        # Width of the window in pixels: the whole screen in fullscreen, else the RESOLUTION width
        if CONFIGURATION["FULLSCREEN_ON_STARTUP"]:
            return self.root.winfo_screenwidth()
        return int(CONFIGURATION["RESOLUTION"].split("x")[0])

    def fit_text(self, text, font, max_width):
        # Keep the text as is if it fits, else cut it as little as possible and end it with "..."
        if font.measure(text) <= max_width:
            return text
        while text and font.measure(text.rstrip() + "...") > max_width:
            text = text[:-1]
        return text.rstrip() + "..."

    def read_book(self, book_name):
        # book_name is the file name inside the books folder, e.g. "Le petit prince.epub"
        print(f"Book selected: {book_name}")
        self.current_book = book_name
        self.pages_list = read_epub_file(os.path.join(CONFIGURATION["BOOKS_FOLDER"], book_name))

        # Restore the saved progression of this book, if any
        whole_state = load_state_if_any()
        if self.current_book in whole_state:
            self.current_word_index = whole_state[self.current_book]["current_word_index"]
            self.current_page_index = whole_state[self.current_book]["current_page_index"]
        else:
            self.current_word_index = 0
            self.current_page_index = 0

        self.show_screen(self.create_reader)
        print(f"Opening book: {book_name}")

    # --- Reader (word by word) ---
    def create_reader(self):
        self.is_paused = False
        background = self.theme["BACKGROUND_COLOR"]
        text_color = self.theme["TEXT_COLOR"]
        info_font = ("Helvetica", CONFIGURATION["INFO_FONT_SIZE"])

        self.current_word_label = tk.Label(self.screen_frame, text="",
                                           font=("Helvetica", CONFIGURATION["WORD_FONT_SIZE"]),
                                           anchor="center", justify="center", bg=background, fg=text_color)
        self.page_progression_label = tk.Label(self.screen_frame, text="This page progression :\n",
                                               font=info_font, anchor="w", justify="left",
                                               bg=background, fg=text_color)
        self.book_progression_label = tk.Label(self.screen_frame, text="Book progression :\n",
                                               font=info_font, anchor="e", justify="right",
                                               bg=background, fg=text_color)
        self.battery_label = tk.Label(self.screen_frame, text="Battery :\n42 %",
                                      font=info_font, anchor="w", justify="left",
                                      bg=background, fg=text_color)
        self.speed_label = tk.Label(self.screen_frame, text="Delay :\n",
                                    font=info_font, anchor="e", justify="right",
                                    bg=background, fg=text_color)

        # Same layout as UI_reader/main.py: word in the middle, one info label in each corner
        self.current_word_label.place(relx=0.0, rely=0.30, relwidth=1.0, relheight=0.40)
        self.page_progression_label.place(relx=0.0, rely=0.0, relwidth=0.48, relheight=0.12)
        self.book_progression_label.place(relx=0.52, rely=0.0, relwidth=0.48, relheight=0.12)
        self.battery_label.place(relx=0.0, rely=0.88, relwidth=0.48, relheight=0.12)
        self.speed_label.place(relx=0.52, rely=0.88, relwidth=0.48, relheight=0.12)

        self.update_speed_label()
        self.update_book_progression_label()
        self.update_word()

    def update_page_progression_label(self):
        if not self.pages_list:
            self.page_progression_label.config(text="This page progression:\n0 / 0 words")
            return

        current_page_words = self.pages_list[self.current_page_index]
        total_words = len(current_page_words)
        current_word = min(self.current_word_index, total_words)
        self.page_progression_label.config(
            text=f"This page progression:\n{current_word} / {total_words} words"
        )

    def update_book_progression_label(self):
        total_pages = len(self.pages_list)

        if total_pages == 0:
            self.book_progression_label.config(text="Book progression:\n0 / 0 pages")
            return

        current_page = min(self.current_page_index + 1, total_pages)
        self.book_progression_label.config(
            text=f"Book progression:\n{current_page} / {total_pages} pages"
        )

    def update_speed_label(self):
        self.speed_label.config(text=f"Delay :\n{self.speed_percentage:.0f}%")

    def calculate_delay_seconds(self, word):
        word_size_coefficient = len(word) / CONFIGURATION["WORD_SIZE_REFERENCE"]

        if word.endswith("."):
            punctuation_coefficient = CONFIGURATION["DOT_DELAY"]
        elif word.endswith(","):
            punctuation_coefficient = CONFIGURATION["COMMA_DELAY"]
        else:
            punctuation_coefficient = 1

        return CONFIGURATION["OFFSET_DELAY_MS"] + (
                punctuation_coefficient
                * word_size_coefficient
                * CONFIGURATION["GENERAL_DELAY"]
                * (self.speed_percentage / 100)
        )

    def update_word(self):
        if self.is_paused:
            return

        if not self.pages_list:
            self.current_word_label.config(text="empty book")
            return

        self.update_page_progression_label()

        if len(self.pages_list[self.current_page_index]) == 0:
            self.current_word_label.config(text="empty page")  # todo change this

        else:
            if self.current_word_index < len(self.pages_list[self.current_page_index]):
                word = self.pages_list[self.current_page_index][self.current_word_index]
                self.current_word_label.config(text=word)

                delay_seconds = self.calculate_delay_seconds(word)

                self.current_word_index = self.current_word_index + 1
                self.update_page_progression_label()

                self.word_update_after_id = self.root.after(
                    int(delay_seconds * 1000), self.update_word
                )
            else:
                self.current_word_label.config(text="finished page")  # automatically go to the next page ?

    def cancel_word_update(self):
        if self.word_update_after_id is not None:
            self.root.after_cancel(self.word_update_after_id)
            self.word_update_after_id = None

    def update_speed(self, increase):
        # Same as UI_reader/main.py: the percentage is a delay, higher = slower reading
        if increase:
            self.speed_percentage += CONFIGURATION["STEP_PERCENTAGE"]
            print(f"Delay increased : {self.speed_percentage:.2f}%")
            self.update_speed_label()
            return

        if self.speed_percentage > CONFIGURATION["STEP_PERCENTAGE"] + 1:
            self.speed_percentage -= CONFIGURATION["STEP_PERCENTAGE"]
            print(f"Delay decreased : {self.speed_percentage:.2f}%")
            self.update_speed_label()
        else:
            print("Min delay reached")

    def decrease_delay(self):
        # Same as key "1" in UI_reader/main.py, only does something on the reader screen
        if self.current_screen != self.create_reader:
            return
        self.update_speed(increase=False)

    def increase_delay(self):
        # Same as key "2" in UI_reader/main.py, only does something on the reader screen
        if self.current_screen != self.create_reader:
            return
        self.update_speed(increase=True)

    def previous_page(self):
        # Same as key "4" in UI_reader/main.py, only does something on the reader screen
        if self.current_screen != self.create_reader:
            return
        print("Previous page")
        self.cancel_word_update()
        self.current_word_index = 0
        if self.current_page_index > 0:
            self.current_page_index -= 1
        else:
            print("Page is already 0")
        self.update_word()
        self.update_book_progression_label()

    def next_page(self):
        # Same as key "5" in UI_reader/main.py, only does something on the reader screen
        if self.current_screen != self.create_reader:
            return
        print("Next page")
        self.cancel_word_update()
        self.current_word_index = 0
        if self.current_page_index < len(self.pages_list) - 1:
            self.current_page_index += 1
        else:
            print("Page is max")
        self.update_word()
        self.update_book_progression_label()

    def jump_words_back(self):
        # Same as key "7" in UI_reader/main.py, only does something on the reader screen
        if self.current_screen != self.create_reader:
            return
        jump = CONFIGURATION["JUMP_WORDS_QTY"]
        if self.current_word_index > jump:
            self.current_word_index -= jump
            print("Go back " + str(jump) + " words, now at ", self.current_word_index)
        else:
            print("Too early on the page (word", str(self.current_word_index), ") to jump", jump,
                  " words back")

    def jump_words_forward(self):
        # Same as key "8" in UI_reader/main.py, only does something on the reader screen
        if self.current_screen != self.create_reader:
            return
        jump = CONFIGURATION["JUMP_WORDS_QTY"]
        if self.current_word_index + jump < len(self.pages_list[self.current_page_index]):
            self.current_word_index += jump
            print("Jump " + str(jump) + " words, now at ", self.current_word_index)
        else:
            print("Too late on the page (word", str(self.current_word_index), ") to jump", jump,
                  " words forward")

    def toggle_pause(self):
        # Same as key "0" in UI_reader/main.py, only does something on the reader screen
        if self.current_screen != self.create_reader:
            return
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.cancel_word_update()
            print("Pause")
        else:
            print("Resume")
            self.update_word()

    def right_right_action(self):
        # Runs in the UI thread: jump forward while reading, validate the selection in the menus
        if self.current_screen == self.create_reader:
            self.jump_words_forward()
        else:
            self.validate_selection()

    # --- Options menu ---
    def create_options_menu(self):
        # Sizes are percentages of the whole screen: no padding around this menu
        self.screen_frame.pack_configure(padx=0, pady=0)
        # Title and one entry per option: 90% of the width, 15% of the height, 2.5% blank space above and below
        widgets = [self.make_title("Options", pack=False)]
        # A single theme entry: each validation switches to the next theme (back to the first after the last)
        widgets.append(self.make_menu_item(f"Theme : {self.theme_name.capitalize()}",
                                           self.next_theme, pack=False))
        self.place_in_rows(widgets)

    def next_theme(self):
        names = list(THEMES)
        self.set_theme(names[(names.index(self.theme_name) + 1) % len(names)])

    def set_theme(self, name):
        self.theme_name = name
        print(f"Theme: {name}")
        self.settings["theme"] = name
        save_settings(self.settings)
        # Rebuild the current screen so the new colors are applied, keep the highlighted entry
        self.show_screen(self.current_screen, keep_selection=True)

    def back_to_main_menu(self):
        self.show_screen(self.create_main_menu)

    # --- Physical buttons (called from the keyboard / GPIO threads) ---
    def top_left_btn(self):
        print("Top left button pressed")
        is_full = bool(self.root.attributes("-fullscreen"))  # could be defined in nit
        self.root.attributes("-fullscreen", not is_full)

    def left_top_btn(self):
        print("left top button pressed")

    def left_left_btn(self):
        print("left left button pressed")
        self.run_in_ui(self.previous_page)

    def left_right_btn(self):
        print("left right button pressed")
        self.run_in_ui(self.next_page)

    def left_down_btn(self):
        print("left down button pressed")
        self.run_in_ui(self.toggle_pause)

    def top_right_btn(self):
        print("top right button pressed")
        self.run_in_ui(self.go_back)

    def go_back(self):
        # Runs in the UI thread: depends on the screen currently displayed
        if self.current_screen in (self.create_books_list, self.create_options_menu):
            self.back_to_main_menu()
        elif self.current_screen == self.create_reader:
            self.back_to_books_list()

    def back_to_books_list(self):
        # Same as key "9" in UI_reader/main.py: save the progression, then back to the book selection
        save_current_state(self.current_book, self.current_page_index, self.current_word_index)
        self.show_screen(self.create_books_list)
        print("Back to books list")

    def right_top_btn(self):
        print("right top button pressed")
        self.run_in_ui(self.right_top_action)
        # TODO enable/disable voice reading using speaker

    def right_top_action(self):
        # Runs in the UI thread: decrease the delay while reading, otherwise navigate the menu
        if self.current_screen == self.create_reader:
            self.decrease_delay()
        else:
            self.select_previous()

    def right_down_action(self):
        # Runs in the UI thread: increase the delay while reading, otherwise navigate the menu
        if self.current_screen == self.create_reader:
            self.increase_delay()
        else:
            self.select_next()

    def right_left_btn(self):
        print("right left button pressed")
        self.run_in_ui(self.jump_words_back)

    def right_right_btn(self):
        print("right right button pressed")
        self.run_in_ui(self.right_right_action)

    def right_down_btn(self):
        print("right down button pressed")
        self.run_in_ui(self.right_down_action)


# Build the window first, register the button listeners, THEN start the tkinter loop
# (mainloop blocks, so anything after it only runs once the window is closed)
main_GUI = GUI()

# check to know if dev on win or using raspberry, todo improve that
if sys.platform.startswith('win'):
    print("Running on Windows")
    import keyboard

    # Register the callback functions for specific keys

    keyboard.on_press_key('a', lambda e: main_GUI.top_left_btn() if e.name == 'a' else None)

    keyboard.on_press_key('z', lambda e: main_GUI.left_top_btn() if e.name == 'z' else None)
    keyboard.on_press_key('q', lambda e: main_GUI.left_left_btn() if e.name == 'q' else None)
    keyboard.on_press_key('d', lambda e: main_GUI.left_right_btn() if e.name == 'd' else None)
    keyboard.on_press_key('s', lambda e: main_GUI.left_down_btn() if e.name == 's' else None)

    keyboard.on_press_key('o', lambda e: main_GUI.top_right_btn() if e.name == 'o' else None)

    keyboard.on_press_key('i', lambda e: main_GUI.right_top_btn() if e.name == 'i' else None)
    keyboard.on_press_key('l', lambda e: main_GUI.right_right_btn() if e.name == 'l' else None)
    keyboard.on_press_key('j', lambda e: main_GUI.right_left_btn() if e.name == 'j' else None)
    keyboard.on_press_key('k', lambda e: main_GUI.right_down_btn() if e.name == 'k' else None)

elif sys.platform.startswith('linux'):
    print("Running on Linux")
    from gpiozero import Button

    # Define the GPIO pins used for input buttons
    # button_pins = [16, 5, 13, 6, 26, 19, 21, 20, 15, 12, 14, 23]
    button_pins = [19, 5, 16, 13, 6, 26, 15, 12, 21, 20]

    #TODO add pins 14 and 23, they should switch between progression of book and page to percentage  / absolute value


    # Define the event function that runs when any button is pressed
    def on_button_pressed(button):
        current_pin = str(button.pin)  # todo
        if current_pin == "GPIO19":
            print("Pin 19 pressed")
            main_GUI.top_left_btn()
        elif current_pin == "GPIO5":
            print("Pin 5 pressed")
            main_GUI.left_top_btn()
        elif current_pin == "GPIO16":
            print("Pin 16 pressed")
            main_GUI.left_left_btn()
        elif current_pin == "GPIO13":
            print("Pin 13 pressed")
            main_GUI.left_right_btn()
        elif current_pin == "GPIO6":
            print("Pin 6 pressed")
            main_GUI.left_down_btn()
        elif current_pin == "GPIO26":
            print("Pin 26 pressed")
            main_GUI.top_right_btn()
        elif current_pin == "GPIO15":
            print("Pin 15 pressed")
            main_GUI.right_top_btn()
        elif current_pin == "GPIO12":
            print("Pin 12 pressed")
            main_GUI.right_left_btn()
        elif current_pin == "GPIO21":
            print("Pin 21 pressed")
            main_GUI.right_right_btn()
        elif current_pin == "GPIO20":
            print("Pin 20 pressed")
            main_GUI.right_down_btn()
        else:
            print("Not found pin")


    # Create Button instances and assign the event handler
    buttons = []
    for pin in button_pins:
        btn = Button(pin, pull_up=True)
        # Assign the callback function (gpiozero automatically passes the button object)
        btn.when_pressed = on_button_pressed
        buttons.append(btn)

    print("Listening for button presses...")

else:
    print(f"Running on an unsupported platform: {sys.platform}")

print("Finish mapping strokes")

# The tkinter loop keeps the script alive (replaces the old sleep loop / signal.pause)
try:
    main_GUI.run()
except KeyboardInterrupt:
    print("Program interrupted by the user")

print("Reader closed")
