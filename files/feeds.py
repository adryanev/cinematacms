from django.conf import settings
from django.contrib.postgres.search import SearchQuery
from django.contrib.syndication.views import Feed
from django.db.models import Q
from django.urls import reverse
from django.utils.feedgenerator import Rss201rev2Feed

from . import helpers, lists
from .models import Category, Media
from .stop_words import STOP_WORDS


class MediaRSSFeed(Rss201rev2Feed):
    def rss_attributes(self):
        attrs = super(MediaRSSFeed, self).rss_attributes()
        attrs["xmlns:media"] = "http://search.yahoo.com/mrss/"
        attrs["xmlns:atom"] = "http://www.w3.org/2005/Atom"
        return attrs

    def add_item_elements(self, handler, item):
        """Callback to add elements to each item (item/entry) element."""
        super(MediaRSSFeed, self).add_item_elements(handler, item)

        if "media:title" in item:
            handler.addQuickElement("media:title", item["title"])
        if "media:description" in item:
            handler.addQuickElement("media:description", item["description"])

        if "content_url" in item:
            content = dict(url=item["content_url"])
            if "content_width" in item:
                content["width"] = str(item["content_width"])
            if "content_height" in item:
                content["height"] = str(item["content_height"])
            handler.addQuickElement("media:content", "", content)

        if "thumbnail_url" in item:
            thumbnail = dict(url=item["thumbnail_url"])
            if "thumbnail_width" in item:
                thumbnail["width"] = str(item["thumbnail_width"])
            if "thumbnail_height" in item:
                thumbnail["height"] = str(item["thumbnail_height"])
            handler.addQuickElement("media:thumbnail", "", thumbnail)

        if "keywords" in item:
            handler.addQuickElement("media:keywords", item["keywords"])

    def add_root_elements(self, handler):
        super().add_root_elements(handler)
        if self.feed["author_name"] is not None:
            handler.startElement("author", {})
            handler.addQuickElement("name", self.feed["author_name"])
            handler.endElement("author")
        if self.feed.get("published") is not None:
            handler.startElement("published", {})
            handler.addQuickElement("name", self.feed["published"])
            handler.endElement("published")


class IndexRSSFeed(Feed):
    feed_type = MediaRSSFeed
    title = "Latest Media"
    link = "/rss"
    description = "Latest Media RSS feed"

    def items(self):
        basic_query = Q(state="public", is_reviewed=True, encoding_status="success")
        media = Media.objects.filter(basic_query).order_by("-add_date")
        media = media.prefetch_related("user")
        return media[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.summary

    def item_author_name(self, item):
        return item.user.username

    def item_pubdate(self, item):
        return item.add_date

    def item_updateddate(self, item):
        return item.edit_date

    def item_link(self, item):
        return reverse("get_media") + "?m={0}".format(item.friendly_token)

    def item_extra_kwargs(self, item):
        item = {
            "media:title": item.title,
            "media:description": item.summary,
            "content_width": 720,
            "thumbnail_url": f"{settings.SSL_FRONTEND_HOST}/{item.poster_url}",
            "content_url": f"{settings.SSL_FRONTEND_HOST}/{item.get_absolute_url()}",
            "thumbnail_width": 720,
        }
        return item


class SearchRSSFeed(Feed):
    feed_type = MediaRSSFeed
    description = "Latest Media RSS feed"

    def link(self, obj):
        return f"/rss/search"

    def get_object(self, request):
        category = request.GET.get("c", "")
        topic = request.GET.get("topic", "")
        language = request.GET.get("language", "")
        country = request.GET.get("country", "")
        tag = request.GET.get("t", "")
        query = request.GET.get("q", "")

        basic_query = Q(state="public", is_reviewed=True)
        media = Media.objects.filter(basic_query)

        if category:
            media = media.filter(category__title=category)
        elif tag:
            media = media.filter(tags__title=tag)
        elif topic:
            media = media.filter(topics__title__contains=topic)
        elif language:
            language = {
                value: key for key, value in dict(lists.video_languages).items()
            }.get(language)
            media = media.filter(media_language=language)
        elif country:
            country = {
                value: key for key, value in dict(lists.video_countries).items()
            }.get(country)
            media = media.filter(media_country=country)
        elif query:
            query = helpers.clean_query(query)
            q_parts = [
                q_part.strip("y")
                for q_part in query.split()
                if q_part not in STOP_WORDS
            ]
            if q_parts:
                query = SearchQuery(q_parts[0] + ":*", search_type="raw")
                for part in q_parts[1:]:
                    query &= SearchQuery(part + ":*", search_type="raw")
            else:
                query = None
        if query:
            media = media.filter(search=query)

        media = media.order_by("-add_date").prefetch_related("user")

        return media

    def items(self, objects):
        return objects[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.summary

    def item_author_name(self, item):
        return item.user.username

    def item_pubdate(self, item):
        return item.add_date

    def item_updateddate(self, item):
        return item.edit_date

    def item_link(self, item):
        return reverse("get_media") + "?m={0}".format(item.friendly_token)

    def item_extra_kwargs(self, item):
        item = {
            "media:title": item.title,
            "media:description": item.summary,
            "content_width": 720,
            "thumbnail_url": f"{settings.SSL_FRONTEND_HOST}/{item.poster_url}",
            "content_url": f"{settings.SSL_FRONTEND_HOST}/{item.get_absolute_url()}",
            "thumbnail_width": 720,
        }
        return item
