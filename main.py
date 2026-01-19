import json
import asyncio
import os
import pymorphy3
from thefuzz import process
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

# Налаштування
TOKEN = "8584569416:AAFqma1jwU6K9r3UfWUkG3-hB04wUnBQhwo"
DATA_FILE = "dictionary.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()
morph = pymorphy3.MorphAnalyzer(lang='uk')


# --- РОБОТА З ДАНИМИ ---

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"alphabet": {}, "words": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"alphabet": {}, "words": {}}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


db = load_data()


def get_reverse_dicts():
    rev_alphabet = {v: k for k, v in db["alphabet"].items()}
    rev_words = {}
    for olu_word, ua_translations in db["words"].items():
        for ua_word in ua_translations.split('/'):
            rev_words[ua_word.strip().lower()] = olu_word
    return rev_alphabet, rev_words


# --- РОЗУМНИЙ ПЕРЕКЛАД ---

def translate_text(text):
    words_list = text.split()
    translated_words = []

    rev_alphabet, rev_words = get_reverse_dicts()
    olu_vocab = list(db["words"].keys())
    ua_vocab = list(rev_words.keys())

    olu_chars = sorted(db["alphabet"].keys(), key=len, reverse=True)
    ua_chars = sorted(rev_alphabet.keys(), key=len, reverse=True)

    for word in words_list:
        is_capitalized = word[0].isupper() if word else False
        clean_word = word.lower().strip(".,!?")  # Прибираємо розділові знаки
        translation = ""

        # 1. Прямий пошук (Точний збіг)
        if clean_word in db["words"]:
            translation = db["words"][clean_word].split('/')[0]
        elif clean_word in rev_words:
            translation = rev_words[clean_word]

        # 2. Пошук за початковою формою (Лематизація для УКР)
        else:
            parsed = morph.parse(clean_word)[0]
            normal_form = parsed.normal_form

            if normal_form in rev_words:
                translation = rev_words[normal_form]

            # 3. Нечіткий пошук (Схожі слова)
            else:
                # Вмикаємо нечіткий пошук тільки для слів довше 3 символів
                if len(clean_word) > 3:
                    best_olu = process.extractOne(clean_word, olu_vocab) if olu_vocab else None
                    best_ua = process.extractOne(clean_word, ua_vocab) if ua_vocab else None

                    # Піднімаємо поріг до 95 (майже повний збіг)
                    if best_olu and best_olu[1] >= 95:
                        translation = db["words"][best_olu[0]].split('/')[0]
                    elif best_ua and best_ua[1] >= 95:
                        translation = rev_words[best_ua[0]]
                    else:
                        translation = None
                else:
                    translation = None

                # 4. Якщо нечіткий пошук не дав результату — транслітерація
                if translation is None:
                    is_olukhen = any(char in db["alphabet"] for char in clean_word if
                                     char not in "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя")
                    current_alphabet = db["alphabet"] if is_olukhen else rev_alphabet
                    current_keys = olu_chars if is_olukhen else ua_chars

                    temp_word = clean_word
                    res = ""
                    i = 0
                    while i < len(temp_word):
                        match_found = False
                        for key in current_keys:
                            if temp_word.startswith(key, i):
                                res += current_alphabet[key]
                                i += len(key)
                                match_found = True
                                break
                        if not match_found:
                            res += temp_word[i]
                            i += 1
                    translation = res

        if is_capitalized:
            translation = translation.capitalize()
        translated_words.append(translation)

    return " ".join(translated_words)


# --- ОБРОБНИКИ КОМАНД ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Я готовий! Надішли мені текст для перекладу або використай /list.")


@dp.message(Command("add_word"))
async def add_word(message: types.Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.answer("Формат: `/add_word олухенська українська`", parse_mode="Markdown")
    db["words"][args[1].lower()] = args[2].lower()
    save_data(db)
    await message.answer(f"Слово **{args[1]}** додано!", parse_mode="Markdown")


@dp.message(Command("list"))
async def list_words(message: types.Message):
    if not db["words"]: return await message.answer("Словник порожній.")
    lines = [f"• **{k}** — {v}" for k, v in db["words"].items()]
    await message.answer("Словник:\n" + "\n".join(lines[:50]), parse_mode="Markdown")


# --- ОБРОБНИК ТЕКСТУ (ЗАВЖДИ ОСТАННІЙ) ---

@dp.message()
async def handle_all_messages(message: types.Message):
    if not message.text: return
    # Якщо це не команда, перекладаємо
    if not message.text.startswith('/'):
        result = translate_text(message.text)
        await message.answer(result)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())