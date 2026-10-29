from django.utils.translation import gettext_lazy as _

CAREER_CONSENT = (
    _('Согласен(на) на обработку указанных мной данных и резюме общественным объединением TÜKİD '
    'для рассмотрения моей кандидатуры на работу.')
)

CAREER_APPLICANT_FIELDS = [
    'vacancy', 'full_name', 'email', 'phone', 'city', 'desired_position', 'cover_letter', 'consent_accepted',
]
