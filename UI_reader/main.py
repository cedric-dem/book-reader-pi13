import html
import re
import tkinter as tk
import xml.etree.ElementTree as ET
import zipfile
import os
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import PurePosixPath
import pickle

from config import (
	BACKGROUND_COLOR,
	COMMA_DELAY,
	DOT_DELAY,
	GENERAL_DELAY,
	OFFSET_DELAY_MS,
	SCREEN_SIZE,
	STEP_PERCENTAGE,
	WORD_SIZE_REFERENCE,
	JUMP_WORDS_QTY, BOOK_PROGRESSION_FILE,
)

class _TextExtractor(HTMLParser):
	def __init__(self) -> None:
		super().__init__()
		self.parts: list[str] = []

	def handle_data(self, data: str) -> None:
		cleaned = data.strip()
		if cleaned:
			self.parts.append(cleaned)

def read_epub_file(epub_file_path: str) -> list[list[str]]:
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
			chapter_text = epub_zip.read(str(chapter_path)).decode("utf-8", errors = "ignore")
			chapter_text = re.sub(r"<[^>]+>", " ", chapter_text)
			chapter_text = html.unescape(chapter_text)
			words = re.findall(r"\S+", chapter_text)

			pages.append(words)

		return pages

def get_books_list() -> list[str]:
	books_list = os.listdir("books")
	books_list.sort()
	return books_list

def analyze_all_books():
	L = get_books_list()
	for book in L:
		print("=> Current book", book)
		this = read_epub_file("books/" + book)

		sizes = []
		for page in this:
			sizes.append(len(page))
		sizes.sort()
		print("===> nb pages : ", len(this))  # , " page sizes ", sizes)

@dataclass
class ReaderState:
	current_book: str = "La bible.epub"
	selected_book_index: int = 0
	current_word_index: int = 0
	current_page_index: int = 0
	current_view: str = "menu"
	is_paused: bool = False
	word_update_after_id: str | None = None
	speed_percentage: int = 100

def load_state_if_any():
	print("=> load prog")
	if os.path.exists(BOOK_PROGRESSION_FILE):
		with open(BOOK_PROGRESSION_FILE, "rb") as f:
			data = pickle.load(f)
			return data
	else:
		return {}

def save_current_state(current_book, current_page_index, current_word_index):
	print("=> save prog")
	current_state = load_state_if_any()

	# add current book
	current_state[current_book] = {"current_page_index": current_page_index, "current_word_index": current_word_index}

	# print("===> keys current", current_state)

	# save progression
	with open(BOOK_PROGRESSION_FILE, "wb") as f:
		pickle.dump(current_state, f)

class ReaderApp:
	def __init__(self, root: tk.Tk) -> None:
		self.root = root
		self.state = ReaderState()
		self.pages_list = read_epub_file("books/" + self.state.current_book)
		self.books_list = get_books_list()

		self.root.title("Word Reader")
		self.root.geometry(f"{SCREEN_SIZE[0]}x{SCREEN_SIZE[1]}")
		self.root.resizable(False, False)
		self.root.configure(bg = BACKGROUND_COLOR)

		self.current_word = tk.Label(root, text = "", font = ("Arial", 50), anchor = "center", justify = "center", bg = "black", fg = "white", )

		self.menu_title_label = tk.Label(root, text = "Menu", font = ("Arial", 32, "bold"), bg = BACKGROUND_COLOR, fg = "white", )

		self.menu_books_label = tk.Label(root, text = "", font = ("Arial", 14), justify = "left", bg = BACKGROUND_COLOR, fg = "white", )

		self.page_progression_label = tk.Label(root, text = "This page progression :\n", font = ("Arial", 14), anchor = "w", justify = "left", bg = BACKGROUND_COLOR, fg = "white", )

		self.book_progression_label = tk.Label(root, text = "Book progression :\n ", font = ("Arial", 14), anchor = "e", justify = "right", bg = BACKGROUND_COLOR, fg = "white", )

		self.battery_label = tk.Label(root, text = "Battery :\n36 %", font = ("Arial", 14), anchor = "w", justify = "left", bg = BACKGROUND_COLOR, fg = "white", )

		self.speed_label = tk.Label(root, text = "Delay :\n", font = ("Arial", 14), anchor = "e", justify = "right", bg = BACKGROUND_COLOR, fg = "white", )

		self.root.bind("<Key>", self.key_pressed)
		self.root.protocol("WM_DELETE_WINDOW", self.on_close)

		self.show_menu()

	def update_page_progression_label(self) -> None:
		if not self.pages_list:
			self.page_progression_label.config(text = "This page progression:\n0 / 0 words")
			return

		current_page_words = self.pages_list[self.state.current_page_index]
		total_words = len(current_page_words)
		current_word = min(self.state.current_word_index, total_words)
		self.page_progression_label.config(
			text = f"This page progression:\n{current_word} / {total_words} words"
		)

	def update_book_progression_label(self) -> None:
		total_pages = len(self.pages_list)

		if total_pages == 0:
			self.book_progression_label.config(text = "Book progression:\n0 / 0 pages")
			return

		current_page = min(self.state.current_page_index + 1, total_pages)
		self.book_progression_label.config(
			text = f"Book progression:\n{current_page} / {total_pages} pages"
		)

	def on_close(self) -> None:
		self.cancel_word_update()
		self.root.destroy()

	def update_speed_label(self) -> None:
		self.speed_label.config(text = f"Delay :\n{self.state.speed_percentage:.0f}%")

	def calculate_delay_seconds(self, word: str) -> float:
		word_size_coefficient = len(word) / WORD_SIZE_REFERENCE

		if word.endswith("."):
			punctuation_coefficient = DOT_DELAY
		elif word.endswith(","):
			punctuation_coefficient = COMMA_DELAY
		else:
			punctuation_coefficient = 1

		return OFFSET_DELAY_MS + (
				punctuation_coefficient
				* word_size_coefficient
				* GENERAL_DELAY
				* (self.state.speed_percentage / 100)
		)

	def update_word(self) -> None:
		if self.state.is_paused:
			return

		self.update_page_progression_label()

		if len(self.pages_list[self.state.current_page_index]) == 0:
			self.current_word.config(text = "empty page")  # todo change this

		else:
			if self.state.current_word_index < len(self.pages_list[self.state.current_page_index]):
				word = self.pages_list[self.state.current_page_index][self.state.current_word_index]
				# print("current page : ",self.pages_list[self.state.current_page_index])
				self.current_word.config(text = word)
				# print(word)

				delay_seconds = self.calculate_delay_seconds(word)

				self.state.current_word_index = (self.state.current_word_index + 1)
				self.update_page_progression_label()

				self.state.word_update_after_id = self.root.after(
					int(delay_seconds * 1000), self.update_word
				)
			else:
				self.current_word.config(text = "finished page")  # automatically go to the next page ?

	def cancel_word_update(self) -> None:
		if self.state.word_update_after_id is not None:
			self.root.after_cancel(self.state.word_update_after_id)
			self.state.word_update_after_id = None

	def show_menu(self) -> None:
		self.state.current_view = "menu"
		self.cancel_word_update()

		self.current_word.place_forget()
		self.page_progression_label.place_forget()
		self.book_progression_label.place_forget()
		self.battery_label.place_forget()
		self.speed_label.place_forget()
		self.update_menu_books_label()

		self.menu_title_label.place(
			x = int(0.1 * SCREEN_SIZE[0]),
			y = int(0.05 * SCREEN_SIZE[1]),
			width = int(0.8 * SCREEN_SIZE[0]),
			height = int(0.05 * SCREEN_SIZE[1]),
		)
		self.menu_books_label.place(
			x = int(0.05 * SCREEN_SIZE[0]),
			y = int(0.15 * SCREEN_SIZE[1]),
			width = int(0.9 * SCREEN_SIZE[0]),
			height = int(0.8 * SCREEN_SIZE[1]),
		)

	def update_menu_books_label(self) -> None:
		menu_lines: list[str] = []

		for index, book_name in enumerate(self.books_list):
			prefix = ">" if index == self.state.selected_book_index else " "
			menu_lines.append(f"{prefix} {book_name}")

		self.menu_books_label.config(text = "\n".join(menu_lines))

	def show_reader(self) -> None:
		if self.state.current_view == "reader":
			return

		self.state.current_view = "reader"
		self.state.is_paused = False
		self.menu_title_label.place_forget()
		self.menu_books_label.place_forget()

		self.current_word.place(
			x = int(0 * SCREEN_SIZE[0]),
			y = int(0.30 * SCREEN_SIZE[1]),
			width = int(1.0 * SCREEN_SIZE[0]),
			height = int(0.40 * SCREEN_SIZE[1]),
		)
		self.page_progression_label.place(
			x = int(0.02 * SCREEN_SIZE[0]),
			y = int(0.02 * SCREEN_SIZE[1]),
			width = int(0.36 * SCREEN_SIZE[0]),
			height = int(0.09 * SCREEN_SIZE[1]),
		)
		self.book_progression_label.place(
			x = int(0.62 * SCREEN_SIZE[0]),
			y = int(0.02 * SCREEN_SIZE[1]),
			width = int(0.36 * SCREEN_SIZE[0]),
			height = int(0.09 * SCREEN_SIZE[1]),
		)
		self.battery_label.place(
			x = int(0.02 * SCREEN_SIZE[0]),
			y = int(0.89 * SCREEN_SIZE[1]),
			width = int(0.36 * SCREEN_SIZE[0]),
			height = int(0.09 * SCREEN_SIZE[1]),
		)
		self.speed_label.place(
			x = int(0.62 * SCREEN_SIZE[0]),
			y = int(0.89 * SCREEN_SIZE[1]),
			width = int(0.36 * SCREEN_SIZE[0]),
			height = int(0.09 * SCREEN_SIZE[1]),
		)

		self.update_word()

	def select_book(self, book_name: str) -> None:

		self.state.current_book = book_name
		self.pages_list = read_epub_file("books/" + book_name)
		self.update_speed_label()

		whole_state = load_state_if_any()
		if self.state.current_book in whole_state:
			self.state.current_word_index = whole_state[self.state.current_book]["current_word_index"]
			self.state.current_page_index = whole_state[self.state.current_book]["current_page_index"]
		else:
			self.state.current_word_index = 0
			self.state.current_page_index = 0

		self.update_book_progression_label()
		self.show_reader()
		print(f"Opening book: {book_name}")

	def update_speed(self, increase: bool) -> None:
		if increase:
			self.state.speed_percentage += STEP_PERCENTAGE
			print(f"Delay increased : {self.state.speed_percentage:.2f}%")
			self.update_speed_label()
			return

		if self.state.speed_percentage > STEP_PERCENTAGE + 1:
			self.state.speed_percentage -= STEP_PERCENTAGE
			print(f"Delay decreased : {self.state.speed_percentage:.2f}%")
			self.update_speed_label()
		else:
			print("Min delay reached")

	def key_pressed(self, event: tk.Event) -> None:
		key = event.char.lower()

		if self.state.current_view == "menu":
			self.key_press_menu(key)
			return

		else:
			self.key_press_book(key)
			return

	def key_press_menu(self, key: str) -> None:
		if key == "1":
			self.state.selected_book_index = (self.state.selected_book_index - 1) % len(self.books_list)
			self.update_menu_books_label()
		elif key == "2":
			self.state.selected_book_index = (self.state.selected_book_index + 1) % len(self.books_list)
			self.update_menu_books_label()
		elif key == "3":
			book_name = get_books_list()[self.state.selected_book_index]
			self.select_book(book_name)

	def key_press_book(self, key: str) -> None:
		if key == "1":
			self.update_speed(increase = False)

		elif key == "2":
			self.update_speed(increase = True)

		elif key == "4":
			print("Previous page")
			self.cancel_word_update()
			self.state.current_word_index = 0
			if self.state.current_page_index > 0:
				self.state.current_page_index -= 1
			else:
				print("Page is already 0")
			self.update_word()
			self.update_book_progression_label()

		elif key == "5":
			print("Next page")
			self.cancel_word_update()
			self.state.current_word_index = 0
			if self.state.current_page_index < len(self.pages_list) - 1:
				self.state.current_page_index += 1
			else:
				print("Page is max")
			self.update_word()
			self.update_book_progression_label()

		elif key == "7":
			if self.state.current_word_index > JUMP_WORDS_QTY:
				self.state.current_word_index -= JUMP_WORDS_QTY
				print("Go back " + str(JUMP_WORDS_QTY) + " words, now at ", self.state.current_word_index)
			else:
				print("Too early on the page (word", str(self.state.current_word_index), ") to jump", JUMP_WORDS_QTY, " words back")

		elif key == "8":
			if self.state.current_word_index + JUMP_WORDS_QTY < len(self.pages_list[self.state.current_page_index]):
				self.state.current_word_index += JUMP_WORDS_QTY
				print("Jump " + str(JUMP_WORDS_QTY) + " words, now at ", self.state.current_word_index)
			else:
				print("Too late on the page (word", str(self.state.current_word_index), ") to jump", JUMP_WORDS_QTY, " words back")

		elif key == "0":
			print("Pause")
			self.state.is_paused = not self.state.is_paused
			if self.state.is_paused:
				self.cancel_word_update()
				print("Pause")
			else:
				print("Resume")
				self.update_word()

		elif key == "9":
			save_current_state(self.state.current_book, self.state.current_page_index, self.state.current_word_index)
			self.show_menu()
			print("Home")

if __name__ == "__main__":
	# analyze_all_books()

	try:
		root = tk.Tk()
	except tk.TclError as error:
		print("Tkinter could not start. If you're on Linux without a desktop, check DISPLAY/X11 setup.")
		raise SystemExit(1) from error

	ReaderApp(root)
	root.mainloop()
	root.mainloop()
