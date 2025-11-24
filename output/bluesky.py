# -*- coding: utf-8 -*-
import  traceback, re, ffmpeg, httpx, base64, io, sys, magic, html
from PIL import Image 
from operator import itemgetter
from atproto import  models, client_utils, AtUri, IdResolver
from linkpreview import link_preview
from main.functions import logger
from main.connections import bsky_connect
from main.db import database
from settings import settings

# Keeping a memory of reply references for the run to avoid having to do a bunch of repeat lookups
reply_references = {}

# Function for processing output queue
def output(queue):
    logger.info("Posting queue to Bluesky.")
    for item in queue:
        try:
            if item["type"] == "repost":
                repost(item)
            else:
                post(item)
        except Exception as e:
            if item["post"]:
                database.failed_post(item["id"], "bluesky")
            logger.error(f"Failed to post {item['id']}: {e}")
            logger.debug(traceback.format_exc())

# Function for sending post
def post(item):
    bluesky_client = bsky_connect()
    text_content = item["post"].text_content("bluesky")
    reply_to = None
    root_ref = None
    reply_ref = None
    urls = item["post"].info["urls"]
    tags = item["post"].info["tags"]
    # putting media in a new variable so that it can be removed after posting
    media = item["post"].media
    media_type = None
    if media:
        media_type = item["post"].info["media"]["type"]
    reply = False
    if item["type"] == "reply":
        reply = True
    for text_post in text_content:
        logger.info(f"Posting \"{text_post}\" to Bluesky")
        # If post contains a single URL, attempting to create a link preview (or repost, if link is to a Bluesky post)
        embed = None
        if len(urls) == 1:
            embed = create_embed(urls[0], media, media_type)
        if embed:
            # If an embed is created, the media has already been added
            media = []
            # If an embed is created, and the URL is at the very end of the post,
            # The URL is removed.
            if text_post.endswith(urls[0]):
                text_post = text_post.replace(urls[0], "")
                urls = []
        bluesky_post = build_post(text_post, urls, tags)
        # Preparing to post as reply, unless the post it is replying to has not been crossposted
        if reply:
            logger.info(f"Posting as a reply")
            # Fetching reply_id. If post is a reply without a reply_id this means
            # post is replying to "itself", as it is a longer post being split into smaller chunks.
            reply_id = item["post"].info["reply_id"]
            if not reply_id:
                reply_id = item["id"]
            post_id, post_uri = database.get_id(reply_id, "bluesky")
            if not post_id or post_id in ["skipped", "FailedToPost", "duplicate"]:
                logger.info(f"Can't continue thread since {item['post'].info['reply_id']} has not been crossposted")
                continue
            reply_ref, root_ref = get_post_ref(post_uri, post_id)
            reply_to = models.AppBskyFeedPost.ReplyRef(parent=reply_ref, root=root_ref)
        # Posting with images
        if media and media_type == "image":
            images = []
            image_alts = []
            aspect_ratios = []
            for media_item in media:
                with open(media_item["filename"], 'rb') as f:
                    images.append(f.read())
                image_alts.append(media_item["alt"])
                aspect_ratios.append(get_aspect_ratio(media_item["filename"], "image"))
            logger.debug(f"bluesky_client.send_images({bluesky_post}, images={images}, image_alts={image_alts}, image_aspect_ratios={aspect_ratios},reply_to={reply_to})")
            reply_ref = models.create_strong_ref(
                            bluesky_client.send_images(
                                bluesky_post,
                                images=images,
                                image_alts=image_alts,
                                image_aspect_ratios=aspect_ratios,
                                reply_to=reply_to
                            )
                        )
            # Emptying media array after posting
            media = []
        # Posting with video
        elif media and media_type == "video":
            # No service today supports more than one video per post, but the videos are still stored in a list so that they can be handled
            # similarly to images. Until then, the single item is simply extracted.
            video_data = media[0]
            with open(video_data["filename"], 'rb') as f:
                video = f.read()
            aspect_ratio = get_aspect_ratio(video_data["filename"], "video")
            logger.debug(f"bluesky_client.send_video({bluesky_post},video={video},video_alt={video_data['alt']},video_aspect_ratio={aspect_ratio})")
            reply_ref = models.create_strong_ref(
                        bluesky_client.send_video(
                            bluesky_post,
                            video=video,
                            video_alt=video_data["alt"],
                            video_aspect_ratio=aspect_ratio
                        )
                    )
            # Emptying media array after posting
            media = []
        # Posting regular post (might include media as an embed)
        else:
            logger.info(f"bluesky_client.send_post({bluesky_post},reply_to={reply_to}")
            reply_ref = models.create_strong_ref(
                bluesky_client.send_post(
                    bluesky_post,
                    reply_to=reply_to,
                    embed=embed
                )
            )
        # No root_ref it means the post is the start of the thread, i.e. the root.
        if not root_ref:
            root_ref = reply_ref
        # Adding reply references to local cache
        reply_references[reply_ref.cid] = {
            "reply_ref": reply_ref,
            "root_ref": root_ref
        }
        # If long posts have had to be split subsequent posts are to be treated as replies
        reply = True
        database.update(item["id"], "bluesky", reply_ref.cid, reply_ref.uri)
        set_reply_settings(item["post"], reply_ref.uri)

# Function for reposting
def repost(item):
    bluesky_client = bsky_connect()
    post_id, post_uri = database.get_id(item["id"], "bluesky")
    response = bluesky_client.repost(uri=post_uri, cid=post_id)
    database.update(item["id"], "bluesky")
    logger.info(f"reposted post {post_id}")
    logger.debug(response)

# Function for deleting post. Takes ID of post from origin (Mastodon)
def delete_post(origin_id):
    bluesky_client = bsky_connect()
    post_id, post_uri = database.get_id(origin_id, "bluesky")
    logger.info(f"Deleting post {post_id} ({post_uri})")
    try:
        bluesky_client.delete_post(post_uri)
    except Exception as e:
        logger.error(f"Failed to delete {post_id}: {e}")
        logger.debug(traceback.format_exc())

# Bluesky's post builder is honestly such a pain in the ass. 
def build_post(text, urls, hashtags):
    logger.info(f"Building post from text \"{text}\", urls \"{urls}\" and hashtags \"{hashtags}\"")
    post = client_utils.TextBuilder()
    included = []
    # Going through the urls and tags and checking if they are found in this part of the post (since posts are sometimes split into several parts).
    # Checking for their position in the post in order to process them in the correct order.
    # As they are processed, they get reversed to stop the same url/tag being matched to several times.
    for url in urls:
        logger.info(f"Checking if url \"{url}\" in text \"{text}\"")
        match = re.search(re.escape(url), text.replace("\n", " "))
        logger.debug(match)
        if match:
            logger.info(f"{url} found in text!")
            included.append({"position": match.start(), "string": url, "type": "url"})
            # Reversing url
            text = text.replace(url, url[::-1], 1)
    for tag in hashtags:
        logger.info(f"Checking if tag \"{tag}\" in text \"{text}\"")
        match = re.search(f"#{tag}", text.replace("\n", " "))
        if match:
            logger.info(f"{tag} found in text!")
            included.append({"position": match.start(), "string": tag, "type": "tag"})
            # Reversing tag
            text = text.replace(f"#{tag}", f"#{tag[::-1]}", 1)
    # If not links or tags found, making a post from just the text
    if not included:
        logger.info("No tags or urls was included in the post.")
        return post.text(text)
    # Sorting tags and urls by position in text
    included = sorted(included, key=itemgetter('position'))
    logger.debug(included)
    # Going through tags and urls one by one, splitting the text string at each so that the parts can be added correctly.
    for item in included:
        if item["type"] == "url":
            parts = text.split(item["string"][::-1])
            post.text(parts[0])
            urls.remove(item["string"])
            # Urls aren't automatically shortened as they are on the other services, so it has to be done in the code.
            display_url = shorten_url(item["string"])
            post.link(display_url, item["string"])
        elif item["type"] == "tag":
            parts = text.split(f'#{item["string"][::-1]}')
            post.text(parts[0])
            hashtags.remove(item["string"])
            post.tag(f'#{item["string"]}', item["string"])
        text = parts[1]
    return post

def create_embed(url, media, media_type):
    bluesky_client = bsky_connect()
    try:
        post_ref = None
        # If the URL is for a bluesky post, attempting to create a quote post
        if re.search(r"https://bsky.app/profile/(.*)/post", url):
            post_ref = get_post_ref_from_url(url)
        # Creating media embeds if post is a quote post and includes media
        media_embed = None
        if post_ref and media:
            media_embed = create_media_embeds(media, media_type)
            # If embedding the media failed, skipping embedding and do a regular post.
            if not media_embed:
                return None
        # Creating quote post with media
        if media_embed:
            logger.info("Creating quote post with media embed")
            logger.debug(media_embed)
            return models.AppBskyEmbedRecordWithMedia.Main(
                record=models.AppBskyEmbedRecord.Main(record=post_ref),
                media=media_embed
            )
        # If no media, just posting a quote post
        if post_ref:
            logger.info("Creating quote post")
            return models.AppBskyEmbedRecord.Main(record=post_ref)
        # It's not possible to include both media embeds and a url preview. 
        if media:
            return None
        # Creating URL preview
        logger.info("Creating URL preview.")
        preview = link_preview(url)
        img_data = None
        # Getting image for preview, either from URL or from base64-string
        if preview.image and preview.image.startswith("http"):
            img_data = httpx.get(preview.image).content
        elif preview.image and preview.image.startswith("data:image/png;base64"):
            img_data = base64.b64decode(preview.image.split(",")[1])
        elif preview.image:
            logger.warning("Preview image in unknown format, skipping.")
            logger.debug(preview.image)
        mime = magic.from_buffer(io.BytesIO(img_data).read(2048), mime=True)
        if not mime.startswith("image"):
            logger.info(f"Preview image data not an image type: {mime}")
            img_data = None
        if img_data and sys.getsizeof(img_data) > 976560:
            logger.warning(f"Preview image too large to post ({sys.getsizeof(img_data)} is larger than max size 976560)")
            img_data = limit_img_size(img_data, 976560)
        image = None
        # Uploading image data
        if img_data:
            image = bluesky_client.upload_blob(img_data).blob
        title = ""
        if preview.title:
            title = html.unescape(preview.title)
        description = ""
        if preview.description:
            description = html.unescape(preview.description)
        # If no info is found for the preview, skipping creating one
        if not title and not description and not image:
            return None
        return models.AppBskyEmbedExternal.Main(
            external=models.AppBskyEmbedExternal.External(
                title=title,
                description=description,
                uri=url,
                thumb=image
            ),
        )
    except Exception as e:
        logger.error(f"failed to create embed, error {e}")
        logger.debug(traceback.format_exc())
        return None

def limit_img_size(image_data, target_filesize):
    logger.info("Attempting to reduce size of preview image")
    try:
        img = img_orig = Image.open(io.BytesIO(image_data))
        aspect = img.size[0] / img.size[1]
        while True:
            with io.BytesIO() as buffer:
                img.save(buffer, format="PNG")
                data = buffer.getvalue()
            filesize = len(data)    
            size_deviation = filesize / target_filesize
            logger.debug("size: {}; factor: {:.3f}".format(filesize, size_deviation))

            if size_deviation <= 1:
                return data
            else:
                # filesize not good enough => adapt width and height
                # use sqrt of deviation since applied both in width and height
                new_width = img.size[0] / size_deviation**0.5    
                new_height = new_width / aspect
                # resize from img_orig to not lose quality
                img = img_orig.resize((int(new_width), int(new_height)))
    except Exception as e:
        logger.error(f"Failed to shrink preview image: {e}")
        logger.debug(traceback.format_exc())
        return None

# Creating media embeds, in case post is a quote post.
def create_media_embeds(media, media_type):
    logger.info(f"Creating {media_type} embed")
    logger.debug(media)
    try:
        if media_type == "video":
            embed = create_video_embed(media[0])
        else:
            embed = create_image_embeds(media)
        return embed
    except Exception as e:
        logger.error(f"failed to embed media, error {e}")
        logger.debug(traceback.format_exc())
        return None

# Creating image embed
def create_image_embeds(images):
    bluesky_client = bsky_connect()
    logger.debug(f"Embedding images: {images}")
    image_embeds = []
    for image_data in images:
        logger.info(f"Uploading {image_data['filename']}")
        with open(image_data["filename"], "rb") as f:
            image = f.read()
        blob = bluesky_client.upload_blob(image).blob
        image_embed = models.AppBskyEmbedImages.Image(
                    image=blob,
                    alt=image_data["alt"],
                    aspect_ratio=get_aspect_ratio(image_data["filename"], "image"),
                )
        logger.debug(image_embed)
        image_embeds.append(image_embed)
    logger.debug(images)
    embed = models.AppBskyEmbedImages.Main(images=image_embeds)
    return embed

# Creating video embed
def create_video_embed(video_data):
    bluesky_client = bsky_connect()
    with open(video_data["filename"], "rb") as f:
        video = f.read()
    blob = bluesky_client.upload_blob(video)
    embed = models.AppBskyEmbedVideo.Main(
        video=blob.blob,
        alt=video_data["alt"],
        video_aspect_ratio=get_aspect_ratio(video_data["filename"], "video")
    )
    return embed

# Shortening URLs as Bluesky doesn't automatically do this.
def shorten_url(url):
    display_url = url.split("/", 2)[2]
    if len(display_url) > 30:
        display_url = display_url[:27] + "..."
    return display_url

# To post in a thread, both the ref to the post being replied to, and the root of the thread is needed. 
# This function fetches both.
def get_post_ref(uri, cid):
    bluesky_client = bsky_connect()
    if cid in reply_references:
        return reply_references[cid]["reply_ref"], reply_references[cid]["root_ref"]
    response = bluesky_client.app.bsky.feed.get_post_thread(params={"uri": uri})
    reply_ref = models.create_strong_ref(response.thread.post.record)
    if response.thread.post.record.reply:
        root_ref = models.create_strong_ref(response.thread.post.record.reply.root)
    else:
        root_ref = reply_ref
    reply_references[cid] = {
            "reply_ref": reply_ref,
            "root_ref": root_ref
        }
    return reply_ref, root_ref

# Function for getting post ref from url
def get_post_ref_from_url(url):
    bluesky_client = bsky_connect()
    try:
        resolver = IdResolver()
        # Extract the handle and post rkey from the URL
        url_parts = url.split('/')
        handle = url_parts[4]  # Username in the URL
        post_rkey = url_parts[6]  # Post Record Key in the URL
        # Resolve the DID for the username
        did = resolver.handle.resolve(handle)
        if not did:
            print(f'Could not resolve DID for handle "{handle}".')
            return None
        # Fetch the post record
        return models.create_strong_ref(bluesky_client.get_post(post_rkey, did))
    except (ValueError, KeyError) as e:
        print(f'Error fetching post for URL {url}: {e}')
        logger.debug(traceback.format_exc())
        return None

# In order for images and videos to look correct, aspect ratios need to be included. 
def get_aspect_ratio(file, type):
    if type == "video":
        video_stream = ffmpeg.probe(file, select_streams = "v")["streams"][0]
        aspect_ratio = models.AppBskyEmbedDefs.AspectRatio(height=video_stream["height"], width=video_stream["width"])
    else:
        image = Image.open(file)
        aspect_ratio = models.AppBskyEmbedDefs.AspectRatio(height=image.height, width=image.width)
    return aspect_ratio

# Translating post reply settings to Bluesky specifics. More information about this in readme
def set_reply_settings(post, post_uri):
    bluesky_client = bsky_connect()
    logger.info("Setting reply settings for post.")
    reply_settings = "everybody"
    if settings.allow_reply == "inherit":
        reply_settings = settings.privacy[post.info["privacy"]]["bluesky"]
    elif settings.allow_reply == "following":
        reply_settings = "following"
    elif settings.allow_reply == "mentioned":
        reply_settings = "mentioned"
    if reply_settings == "everybody":
        logger.info("Everybody can reply, no change made.")
        return
    # Creating threadgate object
    if reply_settings == "mentioned":
        logger.info("Mentioned users can reply")
        threadgate = models.AppBskyFeedThreadgate.MentionRule()
    elif reply_settings == "following":
        logger.info("Followers can reply")
        threadgate = models.AppBskyFeedThreadgate.FollowingRule()
    else:
        logger.info(f"Users in list {reply_settings} can reply")
        threadgate = models.AppBskyFeedThreadgate.ListRule(list=reply_settings)
    rkey = AtUri.from_str(post_uri).rkey
    record = models.AppBskyFeedThreadgate.Record(
        post=post_uri,
        allow=[
            threadgate
        ],
        created_at=bluesky_client.get_current_time_iso(),
    )
    bluesky_client.app.bsky.feed.threadgate.create(bluesky_client.me.did, record, rkey)