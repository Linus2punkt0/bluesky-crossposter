from atproto import Client
import typing as t
import typing_extensions as te
from pydantic import Field
from atproto_client.models.languages import DEFAULT_LANGUAGE_CODE1
from atproto_client.exceptions import LoginRequiredError
from atproto_client.utils import TextBuilder
from atproto_client import models

# A wrapper class for the atproto client with expanded features
class ExpandedClient(Client):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._limit = self._remaining = self._reset = None

    def get_rate_limit(self):
        return self._limit, self._remaining, self._reset

    def _invoke(self, *args, **kwargs):
        self.response = super()._invoke(*args, **kwargs)
        if not self.response.headers.get("RateLimit-Limit"):
            return self.response
        self._limit = self.response.headers.get("RateLimit-Limit")
        self._remaining = self.response.headers.get("RateLimit-Remaining")
        self._reset = self.response.headers.get("RateLimit-Reset")

        return self.response
    
    def send_post(
        self,
        text: t.Union[str, TextBuilder],
        profile_identify: t.Optional[str] = None,
        reply_to: t.Optional['models.AppBskyFeedPost.ReplyRef'] = None,
        embed: t.Optional[
            t.Union[
                'models.AppBskyEmbedImages.Main',
                'models.AppBskyEmbedExternal.Main',
                'models.AppBskyEmbedRecord.Main',
                'models.AppBskyEmbedRecordWithMedia.Main',
                'models.AppBskyEmbedVideo.Main',
            ]
        ] = None,
        labels: t.Optional[t.List[str]] = None,
        langs: t.Optional[t.List[str]] = None,
        facets: t.Optional[t.List['models.AppBskyRichtextFacet.Main']] = None,
    ) -> 'models.AppBskyFeedPost.CreateRecordResponse':
        """Send post.

        Note:
            If `profile_identify` is not provided will be sent to the current profile.

            The default language is ``en``.
            Available languages are defined in :py:mod:`atproto.xrpc_client.models.languages`.

        Args:
            text: Text of the post.
            profile_identify: Handle or DID. Where to send post.
            reply_to: Root and parent of the post to reply to.
            embed: Embed models that should be attached to the post.
            langs: List of used languages in the post.
            facets: List of facets (rich text items).

        Returns:
            :obj:`models.AppBskyFeedPost.CreateRecordResponse`: Reference to the created record.

        Raises:
            :class:`atproto.exceptions.AtProtocolError`: Base exception.
        """
        if isinstance(text, TextBuilder):
            facets = text.build_facets()
            text = text.build_text()

        repo = self.me and self.me.did
        if profile_identify:
            repo = profile_identify

        if not repo:
            raise LoginRequiredError
        
        current_labels = []
        for label in labels:
            current_labels.append(models.ComAtprotoLabelDefs.SelfLabel(val=label))

        labels = models.ComAtprotoLabelDefs.SelfLabels(
            values=current_labels
        )

        if not langs:
            langs = [DEFAULT_LANGUAGE_CODE1]

        record = models.AppBskyFeedPost.Record(
            created_at=self.get_current_time_iso(),
            text=text,
            reply=reply_to,
            embed=embed,
            labels=labels,
            langs=langs,
            facets=facets,
        )
        return self.app.bsky.feed.post.create(repo, record)
    
    def send_images(
        self,
        text: t.Union[str, TextBuilder],
        images: t.List[bytes],
        image_alts: t.Optional[t.List[str]] = None,
        profile_identify: t.Optional[str] = None,
        reply_to: t.Optional['models.AppBskyFeedPost.ReplyRef'] = None,
        labels: t.Optional[t.List[str]] = None,
        langs: t.Optional[t.List[str]] = None,
        facets: t.Optional[t.List['models.AppBskyRichtextFacet.Main']] = None,
        image_aspect_ratios: t.Optional[t.List['models.AppBskyEmbedDefs.AspectRatio']] = None,
    ) -> 'models.AppBskyFeedPost.CreateRecordResponse':
        """Send post with multiple attached images (up to 4 images).

        Note:
            If `profile_identify` is not provided will be sent to the current profile.

        Args:
            text: Text of the post.
            images: List of binary images to attach. The length must be less than or equal to 4.
            image_alts: List of text version of the images.
                        The length should be shorter than or equal to the length of `images`.
            profile_identify: Handle or DID. Where to send post.
            reply_to: Root and parent of the post to reply to.
            langs: List of used languages in the post.
            facets: List of facets (rich text items).
            image_aspect_ratios: List of aspect ratios of the images.
                        The length should be shorter than or equal to the length of `images`.

        Returns:
            :obj:`models.AppBskyFeedPost.CreateRecordResponse`: Reference to the created record.

        Raises:
            :class:`atproto.exceptions.AtProtocolError`: Base exception.
        """
        if image_alts is None:
            image_alts = [''] * len(images)
        else:
            # padding with empty string if len is insufficient
            diff = len(images) - len(image_alts)
            image_alts = image_alts + [''] * diff  # [''] * (minus) => []

        if image_aspect_ratios is None:
            aligned_image_aspect_ratios = [None] * len(images)
        else:
            # padding with None if len is insufficient
            diff = len(images) - len(image_aspect_ratios)
            aligned_image_aspect_ratios = image_aspect_ratios + [None] * diff

        uploads = [self.upload_blob(image) for image in images]
        embed_images = [
            models.AppBskyEmbedImages.Image(alt=alt, image=upload.blob, aspect_ratio=aspect_ratio)
            for alt, upload, aspect_ratio in zip(image_alts, uploads, aligned_image_aspect_ratios)
        ]

        return self.send_post(
            text,
            profile_identify=profile_identify,
            reply_to=reply_to,
            embed=models.AppBskyEmbedImages.Main(images=embed_images),
            labels=labels,
            langs=langs,
            facets=facets,
        )
    
    def send_video(
        self,
        text: t.Union[str, TextBuilder],
        video: bytes,
        video_alt: t.Optional[str] = None,
        profile_identify: t.Optional[str] = None,
        reply_to: t.Optional['models.AppBskyFeedPost.ReplyRef'] = None,
        labels: t.Optional[t.List[str]] = None,
        langs: t.Optional[t.List[str]] = None,
        facets: t.Optional[t.List['models.AppBskyRichtextFacet.Main']] = None,
        video_aspect_ratio: t.Optional['models.AppBskyEmbedDefs.AspectRatio'] = None,
    ) -> 'models.AppBskyFeedPost.CreateRecordResponse':
        """Send post with attached video.

        Note:
            If `profile_identify` is not provided will be sent to the current profile.

        Args:
            text: Text of the post.
            video: Binary video to attach.
            video_alt: Text version of the video.
            profile_identify: Handle or DID. Where to send post.
            reply_to: Root and parent of the post to reply to.
            langs: List of used languages in the post.
            facets: List of facets (rich text items).
            video_aspect_ratio: Aspect ratio of the video.

        Returns:
            :obj:`models.AppBskyFeedPost.CreateRecordResponse`: Reference to the created record.

        Raises:
            :class:`atproto.exceptions.AtProtocolError`: Base exception.
        """
        if video_alt is None:
            video_alt = ''

        upload = self.upload_blob(video)

        return self.send_post(
            text,
            profile_identify=profile_identify,
            reply_to=reply_to,
            embed=models.AppBskyEmbedVideo.Main(video=upload.blob, alt=video_alt, aspect_ratio=video_aspect_ratio),
            langs=langs,
            labels=labels,
            facets=facets,
        )