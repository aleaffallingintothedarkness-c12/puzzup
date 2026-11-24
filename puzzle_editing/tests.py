import logging
from datetime import datetime
from typing import NamedTuple

import django.urls as urls
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.test import TestCase
from django.test.utils import override_settings

from . import status
from .models import Puzzle
from .models import Round
from .models import TestsolveParticipation
from .models import TestsolveSession
from .models import User

logging.disable(logging.DEBUG)  # there's a particular template lookup failure
# in a view that really doesn't seem relevant


def create_user(name):
    return User.objects.create_user(
        username=name, email=name + "@example.com", password=name + "secret"
    )


@override_settings(DISCORD_BOT_TOKEN=None)
class Misc(TestCase):
    def setUp(self):
        self.a = User.objects.create_user(
            username="a", email="a@example.com", password="secret"
        )
        self.b = User.objects.create_user(
            username="b", email="b@example.com", password="password"
        )
        self.c = User.objects.create_user(
            username="c", email="c@example.com", password="password"
        )
        self.eic = User.objects.create_user(
            username="eic", email="eic@example.com", password="super-secret"
        )

        # editor
        permission = Permission.objects.get(
            content_type=ContentType.objects.get_for_model(Round),
            codename="change_round",
        )
        self.eic_group = Group.objects.create(name='EIC')
        self.eic_group.permissions.add(permission)

        self.a.user_permissions.add(permission)
        self.eic.groups.add(self.eic_group)

        self.puzzle1 = Puzzle(
            name="Spoilery Title",
            codename="codename",
            status=status.TESTSOLVING,
            status_mtime=datetime.fromtimestamp(0),
        )
        self.puzzle1.save()
        self.puzzle1.authors.add(self.a)
        self.puzzle1.spoiled.add(self.a)
        self.puzzle2 = Puzzle(
            name="Spoilery Title 2",
            codename="codename 2",
            status_mtime=datetime.fromtimestamp(0),
        )
        self.puzzle2.save()
        self.puzzle2.authors.add(self.b)
        self.puzzle2.spoiled.add(self.b)
        self.puzzle3 = Puzzle(
            name="Spoilery Title 3",
            codename="codename 3",
            status_mtime=datetime.fromtimestamp(0),
        )
        self.puzzle3.save()
        self.puzzle3.authors.add(self.a)
        self.puzzle3.spoiled.add(self.a)
        self.puzzle3.spoiled.add(self.b)
        self.puzzle3.editors.add(self.b)

        self.session1 = TestsolveSession(puzzle=self.puzzle1)
        self.session1.save()

        self.participation1 = TestsolveParticipation(session=self.session1, user=self.b)
        self.participation1.save()

    def test_index(self):
        c = Client()
        c.login(username="b", password="password")

        response = c.get(urls.reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertQuerysetEqual(
            response.context["inbox_puzzles"].order_by("id"),
            [repr(self.puzzle2), repr(self.puzzle3)],
        )

        response = c.get(urls.reverse("puzzle", args=[self.puzzle2.id]))
        response = c.get(urls.reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertQuerysetEqual(
            response.context["inbox_puzzles"].order_by("id"), [repr(self.puzzle3)]
        )

    def test_authored(self):
        c = Client()
        c.login(username="b", password="password")

        response = c.get(urls.reverse("authored"))
        self.assertEqual(response.status_code, 200)
        self.assertQuerysetEqual(response.context["puzzles"], [repr(self.puzzle2)])
        self.assertQuerysetEqual(
            response.context["editing_puzzles"], [repr(self.puzzle3)]
        )

    def test_all(self):
        c = Client()
        c.login(username="b", password="password")

        response = c.get(urls.reverse("all"))
        self.assertEqual(response.status_code, 200)
        # TODO add more

    def test_puzzle(self):
        c = Client()
        c.login(username="b", password="password")

        response = c.get(urls.reverse("puzzle", args=[self.puzzle1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "puzzle_unspoiled.html")

        response = c.get(urls.reverse("puzzle", args=[self.puzzle2.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "puzzle.html")
        self.assertTrue(response.context["is_author"])
        self.assertFalse(response.context["is_editor"])

        response = c.get(urls.reverse("puzzle", args=[self.puzzle3.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "puzzle.html")
        self.assertFalse(response.context["is_author"])
        self.assertTrue(response.context["is_editor"])

    def test_puzzle_subpage_sanity(self):
        c = Client()
        c.login(username="a", password="secret")

        for urlname in [
            "puzzle_edit",
            "puzzle_people",
            "puzzle_answers",
            "puzzle_tags",
            "puzzle_postprod",
        ]:
            self.assertEqual(
                c.get(urls.reverse(urlname, args=[self.puzzle1.id])).status_code, 200
            )

    def test_testsolve_main(self):
        c = Client()
        c.login(username="b", password="password")

        response = c.get(urls.reverse("testsolve_main"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["testsolvable"]), 1)
        self.assertEqual(
            response.context["testsolvable"][0]["puzzle"].id, self.puzzle1.id
        )

    def test_testsolve_one(self):
        ac = Client()
        ac.login(username="a", password="secret")

        response = ac.get(urls.reverse("testsolve_one", args=[self.session1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["spoiled"])
        self.assertIsNone(response.context["participation"])

        bc = Client()
        bc.login(username="b", password="password")

        response = bc.get(urls.reverse("testsolve_one", args=[self.session1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["spoiled"])
        self.assertIsNotNone(response.context["participation"])

        cc = Client()
        cc.login(username="c", password="password")

        response = cc.get(urls.reverse("testsolve_one", args=[self.session1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["spoiled"])
        self.assertIsNone(response.context["participation"])

    def test_testsolve_finish(self):
        ac = Client()
        ac.login(username="a", password="secret")

        response = ac.get(urls.reverse("testsolve_finish", args=[self.session1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["participation"])

        bc = Client()
        bc.login(username="b", password="password")

        response = bc.get(urls.reverse("testsolve_finish", args=[self.session1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["participation"])

    def test_rest_sanity(self):
        ac = Client()
        ac.login(username="a", password="secret")

        bc = Client()
        bc.login(username="b", password="password")

        eicc = Client()
        eicc.login(username="eic", password="super-secret")

        clients = dict(a=ac, b=bc, eic=eicc)

        class TestData(NamedTuple):
            endpoint: str
            allowed: list[str]
            banned: list[str]

        cases = [
            TestData("postprod", ["a", "b"], []),
            TestData("needs_editor", ["a", "b"], []),
            TestData("awaiting_editor", ["eic"], ["a", "b"]),
            TestData("factcheck", ["a", "b"], []),
            TestData("users", ["a", "b"], []),
            TestData("users_statuses", ["a", "b"], []),
            TestData("account", ["a", "b"], []),
            TestData("tags", ["a"], ["b"]),
            TestData("spoiled", ["a", "b"], []),
            TestData("statistics", ["a", "b"], []),
            TestData("new_tag", ["a"], ["b"]),
        ]
        for case in cases:
            url = urls.reverse(case.endpoint)
            for username in case.allowed:
                client = clients[username]
                self.assertEqual(
                    client.get(url, follow=True).status_code,
                    200,
                    f"User {username} should have access to {case.endpoint}",
                )
            for username in case.banned:
                client = clients[username]
                self.assertEqual(
                    client.get(url, follow=True).status_code,
                    403,
                    f"User {username} should not have access to {case.endpoint}",
                )

        self.assertEqual(
            ac.get(urls.reverse("rounds")).status_code,
            200,
            "editor should be able to access rounds",
        )
        self.assertEqual(
            bc.get(urls.reverse("rounds")).status_code,
            403,
            "non-meta-editor shouldn't have access to rounds",
        )


@override_settings(DISCORD_BOT_TOKEN=None)
class InteractivePuzzleHtml(TestCase):
    HTML = '<!doctype html><svg></svg><script>alert("x")</script><p>A "quoted" & odd</p>'

    def setUp(self):
        self.author = create_user("author")
        self.solver = create_user("solver")
        self.outsider = create_user("outsider")
        self.puzzle = Puzzle(
            name="Sandboxed",
            codename="sandboxed",
            status=status.TESTSOLVING,
            status_mtime=datetime.fromtimestamp(0),
            content_html=self.HTML,
        )
        self.puzzle.save()
        self.puzzle.authors.add(self.author)
        self.puzzle.spoiled.add(self.author)
        self.session = TestsolveSession(puzzle=self.puzzle)
        self.session.save()
        TestsolveParticipation(session=self.session, user=self.solver).save()

    def client_for(self, name):
        c = Client()
        self.assertTrue(c.login(username=name, password=name + "secret"))
        return c

    def assert_sandboxed(self, response):
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('sandbox="allow-scripts allow-popups allow-modals"', body)
        self.assertNotIn("allow-same-origin", body)
        self.assertNotIn("allow-top-navigation", body)
        # The puzzle only ever appears escaped inside srcdoc, never as live markup.
        self.assertNotIn("<script>alert", body)
        self.assertIn("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;", body)
        self.assertEqual(response["X-Frame-Options"], "DENY")

    def test_participant_sees_sandboxed_html(self):
        url = urls.reverse("testsolve_html", args=[self.session.id])
        self.assert_sandboxed(self.client_for("solver").get(url))

    def test_spoiled_author_sees_session_and_preview(self):
        c = self.client_for("author")
        self.assert_sandboxed(
            c.get(urls.reverse("testsolve_html", args=[self.session.id]))
        )
        self.assert_sandboxed(c.get(urls.reverse("puzzle_html", args=[self.puzzle.id])))

    def test_outsider_is_refused(self):
        c = self.client_for("outsider")
        self.assertEqual(
            c.get(urls.reverse("testsolve_html", args=[self.session.id])).status_code,
            403,
        )
        self.assertEqual(
            c.get(urls.reverse("puzzle_html", args=[self.puzzle.id])).status_code, 403
        )

    def test_unspoiled_participant_cannot_use_preview(self):
        url = urls.reverse("puzzle_html", args=[self.puzzle.id])
        self.assertEqual(self.client_for("solver").get(url).status_code, 403)

    def test_logged_out_redirects_to_login(self):
        url = urls.reverse("testsolve_html", args=[self.session.id])
        self.assertEqual(Client().get(url).status_code, 302)

    def test_no_html_is_404(self):
        self.puzzle.content_html = ""
        self.puzzle.save()
        url = urls.reverse("puzzle_html", args=[self.puzzle.id])
        self.assertEqual(self.client_for("author").get(url).status_code, 404)

    def test_testsolve_page_links_viewer(self):
        url = urls.reverse("testsolve_one", args=[self.session.id])
        body = self.client_for("solver").get(url).content.decode()
        self.assertIn(urls.reverse("testsolve_html", args=[self.session.id]), body)
        self.assertNotIn("<script>alert", body)

    def test_edit_content_saves_html(self):
        url = urls.reverse(
            "puzzle_w_slug", kwargs={"id": self.puzzle.id, "slug": self.puzzle.slug}
        )
        self.client_for("author").post(
            url,
            {
                "edit_content": "Submit",
                "content": "see link",
                "content_html": "<p>new</p>",
            },
        )
        self.puzzle.refresh_from_db()
        self.assertEqual(self.puzzle.content_html, "<p>new</p>")
        self.assertEqual(self.puzzle.content, "see link")
