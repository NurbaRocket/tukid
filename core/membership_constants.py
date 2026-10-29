from django.utils.translation import gettext_lazy as _

MEMBERSHIP_DECLARATION = (
    _('Я прочитал(а) Устав ОО. Ознакомился(ась) с целями и обязательствами и принимаю их. '
    'Хочу стать членом. Обязуюсь оплачивать членские взносы каждый год, а также активно '
    'участвовать и вносить вклад в деятельность ОО. Прошу принять меня в членство.')
)

APPLICANT_FIELDS = [
    'company_name', 'activity_description', 'tax_id', 'full_name', 'position',
    'organization_address', 'work_phone', 'mobile_phone', 'email',
    'recommendations', 'information_source', 'declaration_accepted',
]

BOARD_FIELDS = [
    'status', 'membership_number', 'secretary_name', 'proposed_on',
    'decision_number', 'decision_date', 'decision_reason', 'chairperson_name',
]
