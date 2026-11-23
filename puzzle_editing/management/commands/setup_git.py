import os
import shutil

import git
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = """Set up git repository, deleting any directory at HUNT_REPO"""

    def handle(self, *args, **options):
        if not (settings.HUNT_REPO_URL and settings.HUNT_REPO):
            print(f"Missing one of: {settings.HUNT_REPO_URL}, {settings.HUNT_REPO}")
            return

        if os.path.exists(settings.HUNT_REPO):
            shutil.rmtree(settings.HUNT_REPO)

        key_path = os.path.expanduser(settings.SSH_KEY)
        if not os.path.isfile(key_path):
            key = os.environ.get("BUILDPACK_SSH_KEY")
            if not key:
                raise CommandError(
                    f"No SSH key at {key_path} and BUILDPACK_SSH_KEY is not set"
                )
            # Hosting dashboards sometimes store multi-line values with
            # literal "\n" or strip the trailing newline; ssh rejects both.
            key = key.replace("\\n", "\n").strip() + "\n"

            ssh_dir = os.path.dirname(key_path)
            os.makedirs(ssh_dir, mode=0o700, exist_ok=True)
            with os.fdopen(
                os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600),
                "w",
            ) as handle:
                handle.write(key)

            config_path = os.path.join(ssh_dir, "config")
            existing = ""
            if os.path.isfile(config_path):
                with open(config_path) as config:
                    existing = config.read()
            if "Host github.com" not in existing:
                with open(config_path, "a") as config:
                    config.write("Host github.com\n")
                    config.write(f"  IdentityFile {key_path}\n")
                    config.write("  IdentitiesOnly yes\n")
                    config.write("  StrictHostKeyChecking no\n")
                    config.write("  UserKnownHostsFile /dev/null\n")
                    config.write("  LogLevel ERROR\n")

        os.system('git config --global user.name "Puzzup"')
        os.system(f'git config --global user.email "{settings.AUTOPOSTPROD_EMAIL}"')

        git_ssh_id_file = os.path.expanduser(settings.SSH_KEY)
        git_ssh_cmd = "ssh -i %s" % git_ssh_id_file

        repo = git.Repo.clone_from(
            settings.HUNT_REPO_URL,
            settings.HUNT_REPO,
            env={"GIT_SSH_COMMAND": git_ssh_cmd},
        )
        repo.remotes.origin.set_url(settings.HUNT_REPO_URL)
