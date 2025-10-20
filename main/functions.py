import  os, shutil, re, sys, traceback, requests
from loguru import logger
from settings.auth import *
from settings.paths import *
from settings import settings
from main.service_parameters import service_parameters




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

def split_text(text, service):
    posts = []
    urls = []
    # Twitter has some over eager URL handling that needs to be accounted for
    potential_urls = re.findall(r" [a-z0-9.]*\.[a-z0-9]{2,30}[.,!?]{0,3} ", f" {text.lower()} ")
    if service == "twitter" and potential_urls:
        logger.info(f"Found following strings that Twitter might interpret as URLS: {" ".join(potential_urls).replace("  ", ", ")}")
        urls = find_mistaken_urls(potential_urls, service)
    if check_length(text, service, urls):
        return [text]
    logger.info(f"Splitting text \"{text}\" into chunks.")
    logger.info("Attempting to split by paragraph.")
    # Split the text into paragraphs
    paragraphs = text.split("\n")
    i = 0
    while i < len(paragraphs):
        post = paragraphs[i]
        o = i + 1
        # Adding together sections until character limit is reached, trying to fit as much as possible into one post
        while o < len(paragraphs) and check_length(f'{post}\n{paragraphs[o]}', service, urls):
            post += f"\n{paragraphs[o]}"
            o += 1
        # If the newly created post is short enough, it is added to the post array.
        if check_length(post, service, urls):
            posts.append(post)
        # Otherwise it is split further
        else:
            posts += split_paragraphs(post, service, urls)
        # o will be the number in the array just after the last one that was just added
        i = o
    # Deleting empty items from post array
    for index, value in enumerate(posts):
        if not value or value.isspace():
            del posts[index]
    logger.debug(posts)
    return posts


# If a paragraph is too long, it is split into sentances
def split_paragraphs(text, service, urls):
    logger.info("Attempting to split by sentence.")
    posts = []
    # Split the text into sentences
    sentences = re.split(r"(?<=[.!?])\s+", text)
    i = 0
    while i < len(sentences):
        post = sentences[i]
        o = i + 1
        # Adding together sections until character limit is reached, trying to fit as much as possible into one post
        while o < len(sentences) and check_length(f'{post} {sentences[o]}', service, urls):
            post += f" {sentences[o]}"
            o += 1
        if check_length(post, service, urls):
            posts.append(post)
        else:
            posts += split_sentences(post, service, urls)
        # o will be the number in the array just after the last one that was just added
        i = o
    return posts

# If a sentence is too long, attempting to split it at logical points (commas, colons)
def split_sentences(text, service, urls):
    logger.info("Attempting to split by other delimiter (commas etc).")
    posts = []
    # Split the text into words
    words = re.split(r"(?<=[,:])\s+", text)
    i = 0
    while i < len(words):
        post = words[i]
        o = i + 1
        # Adding together sections until character limit is reached, trying to fit as much as possible into one post
        while o < len(words) and check_length(f'{post},{words[o]}', service, urls):
            post += f" {words[o]}"
            o += 1
        if check_length(post, service, urls):
            posts.append(post)
        else:
            posts += split_subsentences(post, service, urls)
        # o will be the number in the array just after the last one that was just added
        i = o
    return posts

# If strings are still too long, splitting by word.
def split_subsentences(text, service, urls):
    logger.info("Attempting to split by word.")
    posts = []
    # Split the text into words
    words = text.split(" ")
    i = 0
    while i < len(words):
        post = words[i]
        o = i + 1
        # Adding together sections until character limit is reached, trying to fit as much as possible into one post
        while o < len(words) and check_length(f'{post} {words[o]}', service, urls):
            post += f" {words[o]}"
            o += 1
        if check_length(post, service, urls):
            posts.append(post)
        else:
            posts += split_words(post, service, urls)
        # o will be the number in the array just after the last one that was just added
        i = o
    return posts

# This is the last resort, if some madman posts just a massive string of characters
def split_words(text, service, urls):
    logger.info("Attempting to split by character (what the hell are you trying to post?).")
    posts = []
    # Split the text into single characters
    characters = list(text)
    i = 0
    while i < len(characters):
        post = characters[i]
        o = i + 1
        # Adding together sections until character limit is reached, trying to fit as much as possible into one post
        while o < len(characters) and check_length(f'{post}{characters[o]}', service, urls):
            post += f"{characters[o]}"
            o += 1
        posts.append(post)
        # o will be the number in the array just after the last one that was just added
        i = o
    return posts

# Checking length against service, taking into account that some characters are counted double by some services 
# and that Twitter has some over eager URL handling
def check_length(string, service, urls):
    max_length = service_parameters[service]["post_length"]
    string_length = len(string)
    for url in urls:
        if url["url"] in string.lower():
            logger.debug(f"Accounting for delta of {url["delta"]} caused by {url["url"]}")
            string_length += url["delta"]
    for character in service_parameters[service]["spec_chars"]:
        instances = string.count(character["char"])
        string_length += instances * character["add"]
    logger.debug(f"\"{string}\" will be viewed as {string_length} characters by {service}.")
    return(string_length <= max_length)

# Function for getting a list of valid TLDs from IANA
def get_tlds():
    if hasattr(get_tlds, "_data"):
        return get_tlds._data
    logger.info("Getting list of TLDs from IANA.")
    resp = requests.get("https://data.iana.org/TLD/tlds-alpha-by-domain.txt")
    get_tlds._data = resp.content.decode('utf-8').lower().split("\n")[1:-1]
    return get_tlds._data
        
# Twitter will match any combination of characters with a period followed by a valid TLD as a URL and recalculate 
# the length of the post based on that. This function will check for any such "URLs" and adjust accordingly
def find_mistaken_urls(potential_urls, service):
    tlds = get_tlds()
    # Finding any "URLs"
    urls = []
    for url in potential_urls:
        url = re.sub(r'[^a-zA-Z0-9]+$', '', url).strip()
        logger.info(f"Checking if {url} is a valid url.")
        tld = url.split(".")[-1]
        if tld not in tlds:
            logger.info(f"{tld} is not a valid TLD, skipping.")
            continue
        # Calculating delta between actual "URL" length, and standard Twitter URL length
        delta = service_parameters[service]["url_length"] - len(url.strip())
        if delta != 0:
            modifier = {
                "url": url.strip(),
                "delta": delta
            }
            urls.append(modifier)
    logger.debug(f"Found urls {urls}")
    return urls