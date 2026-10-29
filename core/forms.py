from django.utils.translation import gettext_lazy as _

import re
from uuid import UUID, uuid4

from django import forms
from django.core import signing

from .membership_constants import APPLICANT_FIELDS
from .models import CareerApplication, MembershipApplication, Vacancy
from .career_constants import CAREER_APPLICANT_FIELDS, CAREER_CONSENT
from .career_files import validate_resume

SUBMISSION_SALT = 'core.membership.submission.v1'


def new_submission_token():
    return signing.dumps({'id': str(uuid4())}, salt=SUBMISSION_SALT)


class MembershipApplicationForm(forms.ModelForm):
    submission_token = forms.CharField(widget=forms.HiddenInput, max_length=300)
    website = forms.CharField(required=False, widget=forms.HiddenInput)
    declaration_accepted = forms.BooleanField(
        label=_('Подтверждаю указанные сведения и заявление о вступлении, приведённое выше.'),
        error_messages={'required': _('Подтвердите заявление о вступлении.')},
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    class Meta:
        model = MembershipApplication
        fields = APPLICANT_FIELDS
        widgets = {
            'activity_description': forms.Textarea(attrs={'rows': 4}),
            'recommendations': forms.Textarea(attrs={'rows': 3}),
            'work_phone': forms.TextInput(attrs={'type': 'tel', 'autocomplete': 'tel'}),
            'mobile_phone': forms.TextInput(attrs={'type': 'tel', 'autocomplete': 'tel'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
            'company_name': forms.TextInput(attrs={'autocomplete': 'organization'}),
            'full_name': forms.TextInput(attrs={'autocomplete': 'name'}),
            'position': forms.TextInput(attrs={'autocomplete': 'organization-title'}),
            'organization_address': forms.TextInput(attrs={'autocomplete': 'street-address'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in APPLICANT_FIELDS:
            if name != 'declaration_accepted':
                self.fields[name].widget.attrs.update({'class': 'form-control text-3 py-3'})
        for name in ('work_phone', 'mobile_phone'):
            self.fields[name].help_text = _('Укажите номер с кодом страны.')
        self.sections = [
            (_('Данные организации'), ['company_name', 'activity_description', 'tax_id', 'organization_address']),
            (_('Представитель и контакты'), ['full_name', 'position', 'mobile_phone', 'work_phone', 'email']),
            (_('Дополнительная информация'), ['recommendations', 'information_source']),
        ]
        for field in self.fields.values():
            field.label = _(str(field.label)) if field.label else field.label
            field.help_text = _(str(field.help_text)) if field.help_text else field.help_text
        if self.is_bound:
            for name in self.errors:
                if name in self.fields:
                    widget = self.fields[name].widget
                    widget.attrs['class'] = widget.attrs.get('class', '') + ' is-invalid'
                    widget.attrs['aria-invalid'] = 'true'
                    widget.attrs['aria-describedby'] = f'id_{name}_errors'

    def clean_submission_token(self):
        token = self.cleaned_data['submission_token']
        try:
            payload = signing.loads(token, salt=SUBMISSION_SALT, max_age=7200)
            self.submission_id = UUID(payload['id'])
        except (signing.BadSignature, KeyError, ValueError, TypeError):
            raise forms.ValidationError(_('Время заполнения истекло. Обновите страницу и отправьте заявку ещё раз.'))
        return token

    def clean_website(self):
        if self.cleaned_data.get('website'):
            raise forms.ValidationError(_('Не удалось отправить форму.'))
        return ''

    def clean(self):
        cleaned = super().clean()
        for name in APPLICANT_FIELDS:
            value = cleaned.get(name)
            if isinstance(value, str) and re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', value):
                self.add_error(name, _('Удалите непечатаемые символы.'))
        for name in ('work_phone', 'mobile_phone'):
            phone = cleaned.get(name, '')
            digits = re.sub(r'\D', '', phone)
            if phone and (not 7 <= len(digits) <= 15 or not re.fullmatch(r'[+\d()\s.\-]+', phone)):
                self.add_error(name, _('Введите корректный номер телефона с кодом страны.'))
        return cleaned


CAREER_SUBMISSION_SALT = 'core.career.submission.v1'


def new_career_submission_token():
    return signing.dumps({'id': str(uuid4())}, salt=CAREER_SUBMISSION_SALT)


class CareerApplicationForm(forms.ModelForm):
    submission_token = forms.CharField(widget=forms.HiddenInput, max_length=300)
    website = forms.CharField(required=False, widget=forms.HiddenInput)
    vacancy = forms.ModelChoiceField(label=_('Вакансия'), queryset=Vacancy.objects.none(), required=False,
        empty_label=_('Общая заявка — без выбранной вакансии'))
    desired_position = forms.CharField(label=_('Желаемая должность'), max_length=200, required=False,
        help_text=_('Обязательно для общей заявки. При отклике на вакансию можно оставить пустым.'))
    resume = forms.FileField(label=_('Резюме'), validators=[validate_resume],
        help_text=_('PDF или DOCX, не больше 5 МБ.'),
        widget=forms.ClearableFileInput(attrs={'accept': '.pdf,.docx'}))
    consent_accepted = forms.BooleanField(label=CAREER_CONSENT,
        error_messages={'required': _('Подтвердите согласие на обработку данных.')},
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    class Meta:
        model = CareerApplication
        fields = CAREER_APPLICANT_FIELDS
        widgets = {
            'full_name': forms.TextInput(attrs={'autocomplete': 'name'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
            'phone': forms.TextInput(attrs={'type': 'tel', 'autocomplete': 'tel'}),
            'city': forms.TextInput(attrs={'autocomplete': 'address-level2'}),
            'cover_letter': forms.Textarea(attrs={'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vacancy'].queryset = Vacancy.objects.open().select_related('company')
        self.fields['vacancy'].label_from_instance = lambda job: f"{job.localized('title')} · {job.company.localized('name')}"
        self.fields['phone'].help_text = _('Укажите номер с кодом страны.')
        for name, field in self.fields.items():
            field.label = _(str(field.label)) if field.label else field.label
            field.help_text = _(str(field.help_text)) if field.help_text else field.help_text
            if field.widget.is_hidden or name == 'consent_accepted':
                continue
            field.widget.attrs['class'] = 'form-select' if name == 'vacancy' else 'form-control'
            if field.help_text:
                field.widget.attrs['aria-describedby'] = f'id_{name}_help'
        if self.is_bound:
            for name in self.errors:
                if name in self.fields:
                    widget = self.fields[name].widget
                    widget.attrs['class'] = widget.attrs.get('class', '') + ' is-invalid'
                    widget.attrs['aria-invalid'] = 'true'
                    widget.attrs['aria-describedby'] = f'id_{name}_errors'

    def clean_submission_token(self):
        token = self.cleaned_data['submission_token']
        try:
            payload = signing.loads(token, salt=CAREER_SUBMISSION_SALT, max_age=7200)
            self.submission_id = UUID(payload['id'])
        except (signing.BadSignature, KeyError, ValueError, TypeError):
            raise forms.ValidationError(_('Время заполнения истекло. Обновите страницу и отправьте заявку ещё раз.'))
        return token

    def clean_website(self):
        if self.cleaned_data.get('website'):
            raise forms.ValidationError(_('Не удалось отправить форму.'))
        return ''

    def clean(self):
        cleaned = super().clean()
        vacancy = cleaned.get('vacancy')
        if not cleaned.get('desired_position'):
            if vacancy:
                cleaned['desired_position'] = vacancy.localized('title')
            else:
                self.add_error('desired_position', _('Укажите желаемую должность для общей заявки.'))
        for name in CAREER_APPLICANT_FIELDS:
            value = cleaned.get(name)
            if isinstance(value, str) and re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', value):
                self.add_error(name, _('Удалите непечатаемые символы.'))
        phone = cleaned.get('phone', '')
        if phone and (not 7 <= len(re.sub(r'\D', '', phone)) <= 15 or not re.fullmatch(r'[+\d()\s.\-]+', phone)):
            self.add_error('phone', _('Введите корректный номер телефона с кодом страны.'))
        return cleaned
