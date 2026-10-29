from django.db import IntegrityError, transaction
from django.utils.translation import get_language

from .membership_constants import MEMBERSHIP_DECLARATION
from .membership_pdf import build_membership_pdf
from .models import MembershipApplication, SiteSettings


def submit_membership_application(form):
    # The signed form token fixes the UUID, making retries and double clicks safe.
    existing = MembershipApplication.objects.filter(pk=form.submission_id).only('id').first()
    if existing:
        return existing
    application = form.save(commit=False)
    application.pk = form.submission_id
    application.language = (get_language() or 'ru').split('-')[0]
    application.declaration_text = MEMBERSHIP_DECLARATION
    settings = SiteSettings.objects.first() or SiteSettings()
    pdf = build_membership_pdf(application, settings)
    application.submitted_pdf = pdf
    application.current_pdf = pdf
    try:
        with transaction.atomic():
            application.save(force_insert=True)
    except IntegrityError:
        existing = MembershipApplication.objects.filter(pk=form.submission_id).only('id').first()
        if existing is None:
            raise
        return existing
    return application
