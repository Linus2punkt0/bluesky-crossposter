from copy import deepcopy
from main.functions import logger, split_text
from settings.paths import image_path
import random, string, urllib, requests
import settings.settings as settings

class Post():
        # A post is initiated with a dict containing the following fields
        # info = {
        #     "text": None,
        #     "urls": [],
        #     "tags": [],
        #     "reply_id": None,
        #     "quote_id": None,
        #     "quote_url": None,
        #     "media": None,
        #     "language": None,
        #     "privacy": None,
        #     "repost": None,
        #     "created_at": None,
        # }

    # Basic information about posts to different services
    service_parameters = {
        "twitter": {
            "post_length": 280,
            "url_length": 23
        },
        "mastodon": {
            "post_length": 500,
            "url_length": 23
        },
        "bluesky": {
            "post_length": 300,
            "url_length": 29
        },
    }

    def __init__(self, post_info):
        logger.debug(f"Generating post based on {post_info}")
        self.info = post_info
        # Empty list for putting media in
        self.media = []

    # Takes post info and generated test posts fit for a specific service.
    def text_content(self, service, addition = ""):
        # If post has no text, returning an array with an empty string in it
        if not self.info["text"]:
            return [""]
        # Making a copy of the text and then shortening the URL according to the shortening rules for the specific service
        # Allowing for an addiction to be made, since sometimes Mastodon adds a quoted post as a url
        text = deepcopy(self.info["text"]) + addition
        text = self.shorten_urls(text, service)
        # Turning string into a list of strings short enough to fit the target service
        posts = split_text(text, self.service_parameters[service]["post_length"])
        for i, text in enumerate(posts):
            posts[i] = self.restore_urls(text, service)
        return posts
            
    # Getting video and images
    def get_media(self):
        if self.info["media"]["type"] == "image":
            self.get_images()
        elif self.info["media"]["type"] == "video":
            self.get_video()
        
   # Function for getting included images. 
    def get_images(self):
        for image in self.info["media"]["items"]:
            # Giving the image just a random filename
            filename = ''.join(random.choice(string.ascii_lowercase) for i in range(10)) + ".jpg"
            filename = image_path + filename
            # Downloading fullsize version of image
            urllib.request.urlretrieve(image["url"], filename)
            # Saving image info in a dictionary and adding it to the list.
            image_info = {
                "filename": filename,
                "alt": image["alt"]
            }
            self.media.append(image_info)

    # Function for getting included video. 
    def get_video(self):
        for video in self.info["media"]:
            # Giving the video just a random filename
            filename = ''.join(random.choice(string.ascii_lowercase) for i in range(10)) + ".mp4"
            filename = image_path + filename
            response = requests.get(video["url"])
            if response.status_code != 200:
                logger.error("Failed to download: %s." % response.text)
                return 
            if 'video' not in response.headers.get('Content-Type', ''):
                logger.error("Response is not a valid video file.")
                return
            with open(filename, 'wb') as f:
                f.write(response.content)
            logger.info("Video successfully downloaded to %s." % filename)
            self.media.append({
                "filename": filename,
                "alt": video["alt"]
            })
    
    # Adding the url to a quoted post to the text, if the quote post setting is set to True
    def quote_link(self):
        if settings.quote_posts and self.info["quote_url"] not in self.info["text"]:
            self.info["text"] += "\n" + self.info["quote_url"]
            self.info["urls"].append(self.info["quote_url"])
        elif not settings.quote_posts:
            return False
        return True
    
    # Checking if a post is supposed to post to a specific service
    def post_toggle(self, service):
        if self.lang_toggle(service) and settings.privacy[self.info["privacy"]][service]:
            return True

    # This function uses the language selection as a way to select which posts should be crossposted.
    def lang_toggle(self, service):
        if not settings.lang_toggle[service]:
            return True
        if self.info["language"] and settings.lang_toggle[service] in self.info["language"]:
            return (not settings.post_default)
        else:
            return settings.post_default
    
    # Functions for shortening and restoring URLs, used to calculate post length
    def shorten_urls(self, text, service):
        max_url_length = self.service_parameters[service]["url_length"]
        i = 1
        for url in self.info["urls"]:
            # If the length of the URL is longer than the max url length, it is replaced with a shortened version
            if len(url) > max_url_length:
                text = self.info["text"].replace(url, str(i).zfill(2)+ "_" + url[:max_url_length-3])
            i += 1
        logger.debug(f"Shortened urls: {text}")
        return text

    # When a post contains a shortened url, it is restored to full length
    def restore_urls(self, text, service):
        max_url_length = self.service_parameters[service]["url_length"]
        i = 1
        for url in self.info["urls"]:
            # Restoring URLs to their original form
            if len(url) > max_url_length:
                text = text.replace(str(i).zfill(2)+ "_" + url[:max_url_length-3], url)
            i += 1
        return text
