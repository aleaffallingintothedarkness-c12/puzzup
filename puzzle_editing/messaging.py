import logging

from django.conf import settings
from django.core.mail.message import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_mail_wrapper(subject, template, context, recipients):
    if not recipients:
        logger.warning("Not sending email due to empty recipients: %s", template)
        return

    mail = EmailMultiAlternatives(
        subject=settings.EMAIL_SUBJECT_PREFIX + subject,
        body=render_to_string(template + ".txt", context),
        from_email="Puzzup no-reply <{}>".format(settings.DEFAULT_FROM_EMAIL),
        to=recipients,
        alternatives=[(render_to_string(template + ".html", context), "text/html")],
        reply_to=["Puzzup no-reply <{}>".format(settings.DEFAULT_FROM_EMAIL)],
    )
    # Email is a side effect: a failure here must never break the action
    # (comment, status change, testsolve) that triggered it.
    try:
        send_res = mail.send()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to send email %r to %s", subject, recipients)
        return
    if send_res != 1:
        logger.error("Email %r to %s was not sent (%s)", subject, recipients, send_res)
