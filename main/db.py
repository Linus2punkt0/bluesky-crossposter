import json, os, shutil, arrow
from settings.paths import *
from main.post import Post
from main.functions import count_lines, get_outputs
from settings import settings
from main.functions import logger


# Post database class
class Database():
    # A list of all available services
    services = ["bluesky", "mastodon", "twitter"]

    def __init__(self):
        # This tracks if there have been updates to the database this run, and if not the database is not resaved at the end
        self.updated = False
        # Backup function takes a backup of the database once a day.
        self.backup()
        self.read_db_file()
        self.read_cache()
        self.outputs = get_outputs()

    # Function for getting the corresponding ID for a specific service
    def get_id(self, origin_id, service):
        if not origin_id or origin_id not in self.post_list:
            return None
        id = self.post_list[origin_id]["services"][service]["id"]
        # For bluesky the uri is also needed in order to repost and respond.
        if service == "bluesky": 
            uri = self.post_list[origin_id]["services"][service]["uri"]
            return id, uri
        return id

    # Reading database.json
    def read_db_file(self):
        logger.info("Reading local database")
        self.post_list = {}
        db_data = []
        if not os.path.exists(database_path):
            return
        file = open(database_path, 'r')
        for line in file:
            try:
                db_data.append(json.loads(line))
            except:
                continue
        file.close()
        # If the database doesn't contain the origin field, this means it is
        # still in the old format and needs to be converted.
        if db_data and "origin" not in db_data[0]:
            logger.info("Updating database.")
            self.convert_db(db_data)
            return
        for line in db_data:
            # Setting the identifying id to the ID relating to the current input source, unless the post has not been
            # posted to that service, in which case the ID from the posts origin will be used.
            if line["services"][settings.input_source]["id"] not in ["skipped", "FailedToPost", "duplicate", ""]:
                self.post_list[str(line["services"][settings.input_source]["id"])] = line
            else:
                self.post_list[str(line["services"][line["origin"]]["id"])] = line

    # Checking if an ID exists in the database (adding if not), and if so, if it has already been posted to all required outputs.
    def posted(self, id, services = [], uri = None):
        # If the ID is found it means it has not been deleted, and so it is removed from the array of deleted posts
        if id in self.deleted:
            logger.info(f"Removing post {id} from potentially deleted posts.")
            self.deleted.remove(id)
        # If the ID is not in the database, it is added
        if id not in self.post_list:
            logger.info(f"{id} not found in post list")
            self.add(id, uri)
            return False
        # If no service is given, function checks all active outputs
        if not services:
            services = self.outputs
        for service in services:
            logger.info(f"Checking if {id} has been posted to {service}")
            logger.debug(self.post_list[id]["services"][service]["id"])
            if settings.outputs[service] and not self.post_list[id]["services"][service]["id"]:
                return False
            if self.post_list[id]["services"][service]["id"] == "FailedToPost":
                logger.info(f"{id} has reached error limit for {service}.")
            else:
                logger.info(f"{id} has already been posted to {service}.")
        return True
    
    # Checking if a post has reached failure limit or has been skipped. 
    def not_posted(self, id, services = []):
        # If no service is given, function checks all active outputs
        if not services:
            services = self.outputs
        # Only if all services has been skipped or failed, returns True
        for service in services:
            if not self.post_list[id]["services"][service]["id"] or self.post_list[id]["services"][service]["id"] not in ["skipped", "FailedToPost", "duplicate"]:
                return False
        return True

    # Adding new ID to database
    def add(self, id, uri = None):
        logger.info("Adding post to database")
        self.updated = True
        self.post_list[id] = {
            "origin": settings.input_source,
            "services": self.create_entry()
        }
        # Setting the ID of the post from the input source
        self.post_list[id]["services"][settings.input_source]["id"] = id
        # Adding uri if applicable. This only applies for Bluesky
        if uri:
            self.post_list[id]["services"]["bluesky"]["uri"] = uri
        # For any service that is not the input, and not included in active outputs, setting the id to "skipped"
        for service in self.post_list[id]["services"]:
            if service != settings.input_source and settings.outputs[service] == False:
                self.post_list[id]["services"][service]["id"] = "skipped"

    # Removing post from db and cache
    def remove(self, id):
        logger.info(f"Deleting post {id} from database.")
        del self.post_list[id]
        del self.cache[id]

    # Updating database and cache when a post is sent
    def update(self, input_id, service, output_id = None, uri = None):
        # For reposts no new output_id is given, only the cache is updated
        if output_id:
            self.post_list[str(input_id)]["services"][service]["id"] = output_id
        if uri:
            self.post_list[input_id]["services"][service]["uri"] = uri
        self.cache[str(input_id)] = arrow.utcnow()
        self.updated = True

    # Setting a post for a service to skipped
    def skip(self, id, service):
        if not self.post_list[str(id)]["services"][service]["id"]:
            self.updated = True
            self.post_list[str(id)]["services"][service]["id"] = "skipped"

    #  Saving database to file
    def save(self):
        logger.info("Saving database")
        append_write = "w"
        for id in self.post_list:
            json_string = json.dumps(self.post_list[id])
            file = open(database_path, append_write)
            file.write(json_string + "\n")
            file.close()
            append_write = "a"
        self.save_cache()

    # If a post failed to send, increasing the failure counter for that service. If it reaches the max_retries-limit, setting the post ID to "FailedToPost"
    def failed_post(self, id, service):
        self.post_list[id]["services"][service]["failure"] += 1
        if self.post_list[id]["services"][service]["failure"] >= settings.max_retries:
            self.post_list[id]["services"][service]["id"] = "FailedToPost"


    # Reading cache-file
    def read_cache(self):
        logger.info("Reading cache of recent posts.")
        self.cache = {}
        # Adding all recent posts to deleted, and removing them when they are confirmed to not be.
        self.deleted = []
        timelimit = arrow.utcnow().shift(hours = -1)
        if not os.path.exists(post_cache_path):
            logger.info(f"{post_cache_path} not found.")
            return
        with open(post_cache_path, 'r') as file:
            for line in file:
                try:
                    post_id = str(line.split(";")[0])
                    timestamp = int(line.split(";")[1].split(".")[0])
                    timestamp = arrow.Arrow.fromtimestamp(timestamp)
                except Exception as e:
                    logger.error(e)
                    continue
                if timestamp > timelimit:
                    self.cache[post_id] = timestamp
                    self.deleted.append(post_id)
        logger.debug(f"Cache: {self.cache}")
        logger.debug(f"Deleted: {self.deleted}")

    # Saving cache to file
    def save_cache(self):
        logger.info("Saving cache.")
        logger.debug(self.cache)
        if not self.cache:
            if os.path.exists(post_cache_path):
                os.remove(post_cache_path)
            logger.info("Post cache is empty, removing cache file.")
            return
        logger.info("Saving post cache.")
        append_write = "w"
        for post_id in self.cache:
            timestamp = str(self.cache[post_id].timestamp())
            file = open(post_cache_path, append_write)
            file.write(f"{post_id};{timestamp}\n")
            file.close()
            append_write = "a"

    # The timelimit specifies the cutoff time for which posts are crossposted. This is usually based on the 
    # post_time_limit in settings, but if overflow_posts is set to "skip", meaning any posts that could
    # not be posted due to the hourly post max limit is to be skipped, then the timelimit is instead set to
    # when the last post was sent.
    def get_post_time_limit(self):
        timelimit = arrow.utcnow().shift(hours = -settings.post_time_limit)
        if settings.overflow_posts != "skip":
            return timelimit
        for post_id in self.cache:
            if timelimit < self.cache[post_id]:
                timelimit = self.cache[post_id]
        return timelimit

    # Every twelve hours a backup of the database is saved, in case something happens to the live database.
    # If the live database contains fewer lines than the backup it means something has probably gone wrong,
    # and before the live database is saved as a backup, the current backup is saved as a new file, so that
    # it can be recovered later.
    def backup(self):
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

    # If database is in old format, this function will read it and convert it to the new.
    def convert_db(self, db_data):
        # Making a backup of the old database before converting
        logger.info(f"Backing up database to {database_path}_old before converting.")
        shutil.copyfile(database_path, f"{database_path}_old")
        for line in db_data:
            # Since the old format only used bluesky as input, it will always be the origin
            post = {
                "origin": "bluesky",
                "services": self.create_entry()
            }
            # Entering data from old database
            post["services"]["bluesky"] = {
                                            "id": line["skeet"],
                                            "uri": "",
                                            "failure": 0
                                        }
            post["services"]["twitter"] = {
                                            "id": line["ids"]["twitter_id"],
                                            "failure": line["failed"]["twitter"],
                                        }
            post["services"]["mastodon"] = {
                                            "id": line["ids"]["mastodon_id"],
                                            "failure": line["failed"]["mastodon"],
                                        }
            self.post_list[post["services"][settings.input_source]["id"]] = post

    # Dynamically creating empty entry for a post containing every available service
    def create_entry(self):
        services = {}
        for service in self.services:
            services[service] = {
                        "id": "",
                        "failure": 0
                    }
            # Bluesky requires both CID and URI to interact with posts.
            # Bluesky really is needlessly complicated.
            if service == "bluesky":
                services[service]["uri"] = ""
        return services

# Initiating database
database = Database()