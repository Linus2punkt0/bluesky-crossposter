from settings.paths import *
from loguru import logger
import json, os, shutil, arrow

# Function for writing new lines to the database
def db_write(skeet, tweet, toot, failed, database):
    ids = { 
        "twitter_id": tweet,
        "mastodon_id": toot
    }
    data = {
        "ids": ids,
        "failed": failed
    }
    # When running, the code saves the database to memory, so instead of just saving the post to the database file,
    # we also save it to the open database. This also overwrites the version of the post in memory in case
    # an ID that was missing because of a previous failure. 
    database[skeet] = data
    row = {
        "skeet": skeet,
        "ids": ids,
        "failed": failed
        }
    json_string = json.dumps(row)
    # If the database file exists we want to append to it, otherwise we create it anew.
    if os.path.exists(database_path):
        append_write = 'a'
    else:
        append_write = 'w'
    # Skipping adding posts to db file if they are already in it.
    if not is_in_db(json_string):
        logger.info("Adding to database: " + json_string)
        file = open(database_path, append_write)
        file.write(json_string + "\n")
        file.close()
    return database

# Function for reading database file and saving values in a dictionary
def db_read():
    database = {}
    if not os.path.exists(database_path):
        return database
    with open(database_path, 'r') as file:
        for line in file:
            try:
                json_line = json.loads(line)
            except:
                continue
            skeet = json_line["skeet"]
            ids = json_line["ids"]
            ids = db_convert(ids)
            failed = {"twitter": 0, "mastodon": 0}
            if "failed" in json_line:
                failed = json_line["failed"]
            line_data = {
                "ids": ids,
                "failed": failed
            }
            database[skeet] = line_data
    return database;

# After changing from camelCase to snake_case, old database entries will have to be converted.
def db_convert(ids_in):
    ids_out = {}
    try:
        ids_out["twitter_id"] = ids_in["twitter_id"]
    except:
        ids_out["twitter_id"] = ids_in["twitterId"]
    try:
        ids_out["mastodon_id"] = ids_in["mastodon_id"]
    except:
        ids_out["mastodon_id"] = ids_in["mastodonId"]
    return ids_out


# Function for checking if a line is already in the database-file
def is_in_db(line):
     if not os.path.exists(database_path):
         return False
     with open(database_path, 'r') as file:
        content = file.read()
        if line in content:
            return True
        else:
            return False
        
# Since we are working with a version of the database in memory, at the end of the run
# we completely overwrite the database on file with the one in memory.
# This does kind of make it uneccessary to write each new post to the file while running,
# but in case the program fails halfway through it gives us kind of a backup.
def save_db(database):
    logger.info("Saving new database")
    append_write = "w"
    for skeet in database:
        row = {
            "skeet": skeet,
            "ids": database[skeet]["ids"],
            "failed": database[skeet]["failed"]
        }
        jsonString = json.dumps(row)
        file = open(database_path, append_write)
        file.write(jsonString + "\n")
        file.close()
        append_write = "a"
        
# Every twelve hours a backup of the database is saved, in case something happens to the live database.
# If the live database contains fewer lines than the backup it means something has probably gone wrong,
# and before the live database is saved as a backup, the current backup is saved as a new file, so that
# it can be recovered later.
def db_backup():
    if not os.path.isfile(database_path) or (os.path.isfile(backup_path)
        and arrow.Arrow.fromtimestamp(os.stat(backup_path).st_mtime) > arrow.utcnow().shift(hours = -24)):
        return
    if os.path.isfile(backup_path):
        if count_lines(backup_path) <= count_lines(database_path):
            os.remove(backup_path)
        else:
            date = arrow.utcnow().format("YYMMDD")
            os.rename(backup_path, backup_path + "_" + date)
            logger.error("Current backup file contains more entries than current live database, backup saved")
    shutil.copyfile(database_path, backup_path)
    logger.info("Backup of database taken")


# Function for counting lines in a file
def count_lines(file):
    count = 0;
    with open(file, 'r') as file:
        for count, line in enumerate(file):
            pass
    return count
