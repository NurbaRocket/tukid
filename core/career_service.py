from django.utils.translation import gettext_lazy as _

from pathlib import PurePosixPath
import re

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.translation import get_language

from .career_constants import CAREER_CONSENT
from .career_files import RESUME_CONTENT_TYPES
from .models import CareerApplication, Vacancy


def submit_career_application(form):
    existing = CareerApplication.objects.filter(pk=form.submission_id).only('id').first()
    if existing:
        return existing
    upload = form.cleaned_data['resume']
    filename = re.sub(r'[\x00-\x1f\x7f]', '', PurePosixPath(upload.name.replace('\\', '/')).name).strip()
    suffix = PurePosixPath(filename).suffix.lower()
    application = form.save(commit=False)
    application.pk = form.submission_id
    application.language = (get_language() or 'ru').split('-')[0]
    application.resume_name = filename[:-len(suffix)][:190] + suffix
    application.resume_content_type = RESUME_CONTENT_TYPES[suffix]
    upload.seek(0)
    application.resume_data = upload.read()
    application.resume_size = len(application.resume_data)
    application.consent_text = CAREER_CONSENT
    try:
        with transaction.atomic():
            if application.vacancy_id:
                vacancy = Vacancy.objects.open().select_related('company').select_for_update().filter(pk=application.vacancy_id).first()
                if vacancy is None:
                    raise ValidationError(_('Вакансия уже закрыта. Выберите другую или отправьте общую заявку.'))
                application.vacancy = vacancy
                application.vacancy_title = vacancy.localized('title')
                application.company_name = vacancy.company.localized('name')
            application.save(force_insert=True)
    except IntegrityError:
        existing = CareerApplication.objects.filter(pk=form.submission_id).only('id').first()
        if existing is None:
            raise
        return existing
    return application
