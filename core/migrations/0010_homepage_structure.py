from django.db import migrations


def configure_homepage(apps, schema_editor):
    db = schema_editor.connection.alias
    Section = apps.get_model('core', 'HomeSection')
    Cooperation = apps.get_model('core', 'InstitutionalCooperation')
    sections = [
        ('home', {
            'link_label': 'О нас', 'link_route': 'about',
            'secondary_label': 'Стать членом', 'secondary_route': 'membership',
        }),
        ('members', {'title': 'Члены TÜKİD', 'eyebrow': 'НАШЕ ДЕЛОВОЕ СООБЩЕСТВО',
            'link_label': 'Все члены', 'link_route': 'members', 'items_limit': 24}),
        ('news', {'title': 'Новости TÜKİD', 'eyebrow': 'СОБЫТИЯ ОБЪЕДИНЕНИЯ',
            'description': 'Здесь появятся новости о деятельности TÜKİD, его участниках и совместных проектах.',
            'link_label': 'Все новости', 'link_route': 'news', 'items_limit': 3}),
        ('events', {'title': 'Предстоящие мероприятия', 'eyebrow': 'ВСТРЕЧИ И СОБЫТИЯ',
            'description': 'Анонсы мероприятий TÜKİD и событий с участием объединения появятся здесь.',
            'link_label': 'Все мероприятия', 'link_route': 'events', 'items_limit': 3}),
        ('meetings', {'title': 'Официальные встречи', 'eyebrow': 'ДИАЛОГ И ПАРТНЁРСТВО',
            'description': 'Встречи и визиты представителей TÜKİD: государственные органы, дипломатические миссии, деловые объединения и компании.',
            'link_label': 'Все встречи', 'link_route': 'meetings', 'items_limit': 3}),
        ('cooperation', {'title': 'Институциональное сотрудничество', 'eyebrow': 'ОБЩЕСТВЕННОЕ ВЗАИМОДЕЙСТВИЕ',
            'description': 'Взаимодействие TÜKİD с государственными и дипломатическими институтами.',
            'items_limit': 3}),
    ]
    for order, (key, values) in enumerate(sections):
        Section.objects.using(db).update_or_create(key=key, defaults={
            **values, 'sort_order': order * 10, 'is_visible': True,
        })
    # Retain previous content so editors can reuse it later.
    Section.objects.using(db).filter(key__in=['directions', 'about', 'community']).update(is_visible=False)

    cards = [
        ('Противодействие коррупции', 'scale-balanced',
            'Участие в Совете по деловым вопросам в сфере противодействия коррупции при Президенте Кыргызской Республики.'),
        ('Инвестиционное взаимодействие', 'chart-line',
            'Членство в Совете по инвестициям при Кабинете Министров Кыргызской Республики.'),
        ('Дипломатическое сотрудничество', 'landmark',
            'Взаимодействие с Посольством Турецкой Республики в Бишкеке и соответствующими советниками.'),
    ]
    for order, (title, icon, description) in enumerate(cards):
        Cooperation.objects.using(db).get_or_create(title=title, defaults={
            'description': description, 'icon': icon, 'sort_order': order * 10, 'is_published': True,
        })


class Migration(migrations.Migration):
    dependencies = [('core', '0009_institutionalcooperation_officialmeeting_and_more')]
    operations = [migrations.RunPython(configure_homepage, migrations.RunPython.noop)]
