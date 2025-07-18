# Basic information about posts to different services.
# post_length is max post length for service.
# url_length is the length URLs are shortened to
# spec_chars are character that are counted as more than one character by service.
# Add shows how many characters need to be added to total for each instance.
service_parameters = {
    "twitter": {
        "post_length": 280,
        "url_length": 23,
        "spec_chars": [
            {
                "char": "•",
                "add": 1
            }
            ]
    },
    "mastodon": {
        "post_length": 500,
        "url_length": 23,
        "spec_chars": []
    },
    "bluesky": {
        "post_length": 300,
        "url_length": 29,
        "spec_chars": []
    },
}