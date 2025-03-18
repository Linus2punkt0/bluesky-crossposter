import  os, shutil, re, sys, traceback
from loguru import logger
from settings.auth import *
from settings.paths import *
from settings import settings



# Setting up logging
logger.remove()
log_format = "<yellow>{time:YYYY-MM-DD HH:mm:ss}</yellow> <lvl>[{level}]: {message}</lvl> <yellow>({function} {file}:{line})</yellow>"
logger.add(sys.stdout, format=log_format, level=settings.log_level)
logger.add("%s/crossposter_{time:YYMMDD}.log" % log_path,
        level=settings.log_level,
        format=log_format, 
        rotation="00:00", retention="1 week")

# Getting queues for all active outputs, excluding the input
def get_outputs():
    services = []
    for output in settings.outputs:
        if settings.outputs[output] and settings.input_source != output:
            services.append(output)
    return services

# Extracing URLs from string
def extract_urls(string):
    regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
    url = re.findall(regex, string)
    return [x[0] for x in url]

# Cleaning up HTML
CLEANR = re.compile('<.*?>') 
def clean_html(raw_html):
  cleantext = re.sub(CLEANR, '', raw_html)
  return cleantext


# Cleaning up downloaded images and videos
def cleanup():
    logger.info("Deleting local images")
    for filename in os.listdir(image_path):
        if (filename == ".gitkeep"):
            continue
        file_path = os.path.join(image_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            logger.error(f'Failed to delete {file_path}. Reason: {e}')
            logger.debug(traceback.format_exc())


# Function for counting lines in a file
def count_lines(file):
    count = 0;
    with open(file, 'r') as file:
        for count, _ in enumerate(file):
            pass
    return count

# Functions for splitting posts into smaller chunks if necessary

def split_text(text, max_chars):
    posts = []
    # Split the text into paragraphs
    paragraphs = text.split("\n")
    # Removing empty paragraphs
    paragraphs = list(filter(None, paragraphs))
    i = 0
    while i < len(paragraphs):
        post = paragraphs[i]
        o = i + 1
        # Adding together sections until character limit is reached, trying to fit as much as possible into one post
        while o < len(paragraphs) and len(f'{post}\n{paragraphs[o]}') <= max_chars:
            post += f"\n{paragraphs[o]}"
            o += 1
        # If the newly created post is short enough, it is added to the post array.
        if len(post) <= max_chars:
            posts.append(post)
        # Otherwise it is split further
        else:
            posts += split_paragraphs(post, max_chars)
        # o will be the number in the array just after the last one that was just added
        i = o
    return posts

# If a paragraph is too long, it is split into sentances
def split_paragraphs(text, max_chars):
    posts = []
    # Split the text into sentences
    sentences = re.split(r"(?<=[.!?])\s+", text)
    i = 0
    while i < len(sentences):
        post = sentences[i]
        o = i + 1
        # Adding together sections until character limit is reached, trying to fit as much as possible into one post
        while o < len(sentences) and len(f'{post} {sentences[o]}') <= max_chars:
            post += f" {sentences[o]}"
            o += 1
        if len(post) <= max_chars:
            posts.append(post)
        else:
            posts += split_sentences(post, max_chars)
        # o will be the number in the array just after the last one that was just added
        i = o
    return posts

# If a sentence is too long, attempting to split it at logical points (commas, colons)
def split_sentences(text, max_chars):
    posts = []
    # Split the text into words
    words = re.split(r"(?<=[,:])\s+", text)
    i = 0
    while i < len(words):
        post = words[i]
        o = i + 1
        # Adding together sections until character limit is reached, trying to fit as much as possible into one post
        while o < len(words) and len(f'{post},{words[o]}') <= max_chars:
            post += f" {words[o]}"
            o += 1
        if len(post) <= max_chars:
            posts.append(post)
        else:
            posts += split_subsentences(post, max_chars)
        # o will be the number in the array just after the last one that was just added
        i = o
    return posts

# If strings are still too long, splitting by word.
def split_subsentences(text, max_chars):
    posts = []
    # Split the text into words
    words = text.split(" ")
    i = 0
    while i < len(words):
        post = words[i]
        o = i + 1
        # Adding together sections until character limit is reached, trying to fit as much as possible into one post
        while o < len(words) and len(f'{post} {words[o]}') <= max_chars:
            post += f" {words[o]}"
            o += 1
        if len(post) <= max_chars:
            posts.append(post)
        else:
            posts += split_words(post, max_chars)
        # o will be the number in the array just after the last one that was just added
        i = o
    return posts

# This is the last resort, if some madman posts just a massive string of characters
def split_words(text, max_chars):
    posts = []
    # Split the text into single characters
    characters = list(text)
    i = 0
    while i < len(characters):
        post = characters[i]
        o = i + 1
        # Adding together sections until character limit is reached, trying to fit as much as possible into one post
        while o < len(characters) and len(f'{post}{characters[o]}') <= max_chars:
            post += f"{characters[o]}"
            o += 1
        posts.append(post)
        # o will be the number in the array just after the last one that was just added
        i = o
    return posts


