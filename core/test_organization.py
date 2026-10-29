from importlib import import_module

from django.apps import apps
from django.db import connection
from django.test import TestCase

from .models import HomeSection, Member, MembershipApplication, MenuItem, News, Page, SiteSettings


class OrganizationCopyMigrationTests(TestCase):
    def test_updates_public_copy_and_preserves_applications_and_editorial_records(self):
        settings = SiteSettings.objects.get()
        settings.organization_name = 'Ассоциация турецко-кыргызских предпринимателей'
        settings.footer_text = 'Об ассоциации: свой текст.'
        settings.email = 'custom@example.com'
        settings.save()
        hero = HomeSection.objects.get(key='home')
        hero.description = 'Наша ассоциация поддерживает участников.'
        hero.link_label = 'Об ассоциации'
        hero.save()
        about = Page.objects.get(slug='about')
        about.body = '<p>Деятельность ассоциации и общение в ассоциации.</p>'
        about.save()
        menu = MenuItem.objects.get(route='membership')
        menu.title = 'Стать членом ассоциации'
        menu.save()
        editorial = News.objects.create(title='Новость партнёров', slug='partner-history',
            body='Ассоциация партнёров провела встречу.')
        company = Member.objects.create(name='Ассоциация партнёров', slug='partner-company')
        application = MembershipApplication.objects.create(
            company_name='Ассоциация заявителей', full_name='Тестовый заявитель',
            declaration_accepted=True, declaration_text='Исторический текст об ассоциации.',
            submitted_pdf=b'%PDF-1.4 original application',
            current_pdf=b'%PDF-1.4 reviewed application',
        )
        snapshot = {
            field: getattr(application, field)
            for field in ('company_name', 'declaration_text', 'submitted_pdf', 'current_pdf', 'created_at', 'updated_at')
        }
        migration = import_module('core.migrations.0008_update_organization_terminology')
        migration.update_public_copy(apps, connection.schema_editor())

        settings.refresh_from_db()
        hero.refresh_from_db()
        about.refresh_from_db()
        menu.refresh_from_db()
        self.assertEqual(settings.organization_name, 'Общественное объединение турецко-кыргызских предпринимателей')
        self.assertEqual(settings.footer_text, 'Об объединении: свой текст.')
        self.assertEqual(settings.email, 'custom@example.com')
        self.assertEqual(hero.description, 'Наше общественное объединение поддерживает участников.')
        self.assertEqual(hero.link_label, 'Об объединении')
        self.assertEqual(about.body, '<p>Деятельность объединения и общение в объединении.</p>')
        self.assertEqual(menu.title, 'Стать членом объединения')
        self.assertEqual(menu.route, 'membership')
        self.assertEqual(about.slug, 'about')

        application.refresh_from_db()
        for field, value in snapshot.items():
            self.assertEqual(getattr(application, field), value)
        editorial.refresh_from_db()
        company.refresh_from_db()
        self.assertEqual(editorial.body, 'Ассоциация партнёров провела встречу.')
        self.assertEqual(company.name, 'Ассоциация партнёров')

        # Reapplying the content conversion leaves the new wording unchanged.
        migration.update_public_copy(apps, connection.schema_editor())
        hero.refresh_from_db()
        self.assertEqual(hero.description, 'Наше общественное объединение поддерживает участников.')
