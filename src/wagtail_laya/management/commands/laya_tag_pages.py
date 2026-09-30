"""Bulk tag pages with Laya.

    manage.py laya_tag_pages blog.BlogPage --threshold 0.7 --apply
    manage.py laya_tag_pages blog.BlogPage --field feeling_tags

Without --apply it only prints suggestions. With --apply it adds tags to a
new draft revision, and with --publish it publishes that revision too.
Without --field every field in the model's ``laya_tag_fields`` is processed.
A page Laya answers with an error is reported and skipped; if Laya cannot be
reached or started at all, the command stops.
"""

from dataclasses import replace

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

from wagtail_laya import client as laya_client
from wagtail_laya.article import Article
from wagtail_laya.errors import LayaError, LayaUnavailable
from wagtail_laya.models import LayaTaggableMixin


class Command(BaseCommand):
    help = "Suggest or apply Laya tags for all live pages of a page model."

    def add_arguments(self, parser):
        parser.add_argument("model", help="app_label.ModelName of a LayaTaggableMixin page")
        parser.add_argument("--field", action="append", dest="fields", help="Tag field(s) to process")
        parser.add_argument("--threshold", type=float, default=None)
        parser.add_argument("--max-tags", type=int, default=None)
        parser.add_argument("--apply", action="store_true", help="Save suggestions as a draft")
        parser.add_argument("--publish", action="store_true", help="Publish after applying")
        parser.add_argument("--ids", nargs="*", type=int, help="Restrict to these page IDs")

    def handle(self, *args, **options):
        model = apps.get_model(options["model"])
        if not issubclass(model, LayaTaggableMixin):
            raise CommandError(f"{options['model']} does not use LayaTaggableMixin")

        overrides = {}
        if options["threshold"] is not None:
            overrides["threshold"] = options["threshold"]
        if options["max_tags"] is not None:
            overrides["max_tags"] = options["max_tags"]

        names = options["fields"] or list(model.laya_tag_fields)
        try:
            tag_fields = [replace(model.laya_tag_field(name), **overrides) for name in names]
        except LookupError as exc:
            raise CommandError(str(exc)) from None

        queryset = model.objects.live()
        if options["ids"]:
            queryset = queryset.filter(id__in=options["ids"])

        backend = laya_client.get_backend()
        for page in queryset.iterator():
            changed = False
            for tag_field in tag_fields:
                label = f"[{page.id}] {page.title} / {tag_field.name}"
                article = Article.from_page(page, tag_field.name)
                try:
                    suggestions = tag_field.suggest(article, backend=backend)
                except LayaUnavailable as exc:
                    raise CommandError(str(exc)) from None
                except LayaError as exc:
                    self.stderr.write(f"{label}: {exc}")
                    continue

                summary = ", ".join(f"{s.name} ({s.percent}%)" for s in suggestions) or "-"
                self.stdout.write(f"{label}: {summary}")

                if options["apply"] and suggestions:
                    getattr(page, tag_field.name).add(*(s.name for s in suggestions))
                    changed = True

            if changed:
                revision = page.save_revision(log_action=True)
                if options["publish"]:
                    revision.publish()
