from settings.auth import *
from settings.paths import *
from local.functions import *
import settings.settings as settings
import  os, shutil, re, arrow

# This function uses the language selection as a way to select which posts should be crossposted.
def lang_toggle(langs, service):
    if service == "twitter":
        lang_toggle = settings.twitter_lang
    elif service == "mastodon":
        lang_toggle = settings.mastodon_lang
    else:
        write_log("Something has gone very wrong.", "error")
        exit()
    if not lang_toggle:
        return True
    if langs and lang_toggle in langs:
        return (not settings.post_default)
    else:
        return settings.post_default

# Function for correctly counting post length
def post_length(post):
    # Twitter shortens urls to 23 characters
    short_url_length = 23
    length = len(post)
    # Finding all urls and calculating how much shorter the post will be after shortening
    regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
    urls = re.findall(regex, post)
    for url in urls:
        url_length = len(url[0])
        if url_length > short_url_length:
            length = length - (url_length - short_url_length)
    return length



# Function for writing to the log file
def write_log(message, type = "message"):
    if settings.log_level == "none" or (settings.log_level == "error" and type == "message"):
        return;
    now = arrow.utcnow().format("DD/MM/YYYY HH:mm:ss")
    date = arrow.utcnow().format("YYMMDD")
    message = str(now) + " (" + type.upper() + "): " + str(message) + "\n"
    print(message)
    log = log_path + date + ".log"
    if os.path.exists(log):
        append_write = 'a'
    else:
        append_write = 'w'
    dst = open(log, append_write)
    dst.write(message)
    dst.close()

# Cleaning up downloaded images
def cleanup():
    write_log("Deleting local images")
    for filename in os.listdir(image_path):
        if (filename == ".gitignore"):
            continue
        file_path = os.path.join(image_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            write_log('Failed to delete %s. Reason: %s' % (file_path, e), "error")

# Following two functions deals with the post per hour limit

# Function for reading post log and checking number of posts sent in last hour
def post_cache_read():
    write_log("Reading cache of recent posts.")
    cache = {}
    timelimit = arrow.utcnow().shift(hours = -1)
    if not os.path.exists(post_cache_path):
        write_log(post_cache_path + " not found.")
        return cache
    with open(post_cache_path, 'r') as file:
        for line in file:
            try:
                post_id = line.split(";")[0]
                timestamp = int(line.split(".")[1])
                timestamp = arrow.Arrow.fromtimestamp(timestamp)
            except Exception as error:
                write_log(error, "error")
                continue
            if timestamp > timelimit:
                cache[post_id] = timestamp
    return cache;

def post_cache_write(cache):
    write_log("Saving post cache.")
    append_write = "w"
    for post_id in cache:
        timestamp = str(cache[post_id].timestamp())
        file = open(post_cache_path, append_write)
        file.write(post_id + ";" + timestamp + "\n")
        file.close()
        append_write = "a"

# The timelimit specifies the cutoff time for which posts are crossposted. This is usually based on the 
# post_time_limit in settings, but if overflow_posts is set to "skip", meaning any posts that could
# not be posted due to the hourly post max limit is to be skipped, then the timelimit is instead set to
# when the last post was sent.
def get_post_time_limit(cache):
    timelimit = arrow.utcnow().shift(hours = -settings.post_time_limit)
    if settings.overflow_posts != "skip":
        return timelimit
    for post_id in cache:
        if timelimit < cache[post_id]:
            timelimit = cache[post_id]
    return timelimit

