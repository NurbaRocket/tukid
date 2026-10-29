from django.db import migrations


def seed_content(apps, schema_editor):
    db = schema_editor.connection.alias
    Settings = apps.get_model('core', 'SiteSettings')
    Section = apps.get_model('core', 'HomeSection')
    Direction = apps.get_model('core', 'HomeDirection')
    Photo = apps.get_model('core', 'GalleryPhoto')
    Menu = apps.get_model('core', 'MenuItem')
    Page = apps.get_model('core', 'Page')
    Settings.objects.using(db).get_or_create(pk=1)
    about = Page.objects.using(db).filter(slug='about').first()
    sections = [
        dict(key='home', eyebrow='TUKID', title='Объединяем людей.\nРазвиваем партнёрство.\nУкрепляем дружбу.',
             description='Ассоциация турецко-кыргызских предпринимателей, культуры, солидарности и дружбы.',
             link_label='Об ассоциации', link_route='about', secondary_label='Наши члены', secondary_route='members',
             image_alt='Встреча участников TUKID'),
        dict(key='directions', eyebrow='ЧТО НАС ОБЪЕДИНЯЕТ', title='Четыре направления. Одно сообщество.', items_limit=4),
        dict(key='about', eyebrow='ОБ АССОЦИАЦИИ', title='Знакомство становится партнёрством.',
             description=about.body if about and about.body else
             'TUKID объединяет турецко-кыргызское сообщество вокруг предпринимательства, культуры, солидарности и дружбы.\n\nЭто пространство для общения, обмена опытом и совместных инициатив, где деловые связи дополняются уважением к традициям и доверием между людьми.',
             link_label='Миссия и видение', link_route='mission', image_alt='Сообщество TUKID'),
        dict(key='members', eyebrow='НАШЕ ДЕЛОВОЕ СООБЩЕСТВО', title='Члены ассоциации',
             link_label='Все члены ассоциации', link_route='members', items_limit=8),
        dict(key='events', eyebrow='ВСТРЕЧИ И СОБЫТИЯ', title='Ближайшие мероприятия',
             description='Здесь появятся анонсы деловых встреч, культурных событий и совместных инициатив TUKID.',
             link_label='Все мероприятия', link_route='events'),
        dict(key='news', eyebrow='СОБЫТИЯ СООБЩЕСТВА', title='Новости TUKID',
             description='Следите за публикациями о деятельности ассоциации, её участниках и совместных проектах.',
             link_label='Все новости', link_route='news'),
        dict(key='community', eyebrow='ЛЮДИ, КОТОРЫЕ НАС ОБЪЕДИНЯЮТ', title='Жизнь ассоциации',
             description='Встречи, традиции и моменты, из которых складывается наше сообщество.', items_limit=4),
    ]
    for order, data in enumerate(sections):
        key = data.pop('key')
        Section.objects.using(db).get_or_create(key=key, defaults={**data, 'sort_order': order * 10})
    directions = [
        ('Бизнес', 'handshake', 'Деловые знакомства, обмен опытом и возможности для сотрудничества.'),
        ('Культура', 'landmark', 'Знакомство с традициями и культурный обмен между Турцией и Кыргызстаном.'),
        ('Солидарность', 'hands-holding-circle', 'Взаимная поддержка, участие и совместные инициативы.'),
        ('Дружба', 'people-group', 'Укрепление связей между людьми, сообществами и двумя странами.'),
    ]
    for order, (title, icon, description) in enumerate(directions):
        Direction.objects.using(db).create(title=title, icon=icon, description=description, sort_order=order)
    for order, title in enumerate(['Встречи участников', 'Культурные события', 'Совместные инициативы', 'Дружба и общение']):
        Photo.objects.using(db).create(title=title, sort_order=order,
            placeholder=f'core/images/placeholders/home-gallery-{order + 1}.svg')
    menu = [
        ('О нас', 'about', [('О нас', 'about'), ('Миссия и видение', 'mission'), ('Совет правления', 'board')]),
        ('Наши члены', 'members', [('Наши члены', 'members'), ('Стать членом ассоциации', '')]),
        ('Новости', 'news', [('Все новости', 'news'), ('Новости TÜKİD', 'tukid_news')]),
        ('Мероприятия', 'events', [('Все мероприятия', 'events'), ('Анонсы', 'upcoming_events'), ('Прошедшие мероприятия', 'past_events')]),
        ('Карьера', 'career', []),
        ('Контакты', 'contacts', []),
    ]
    for order, (title, route, children) in enumerate(menu):
        parent = Menu.objects.using(db).create(title=title, route=route, sort_order=order * 10)
        for child_order, (child_title, child_route) in enumerate(children):
            Menu.objects.using(db).create(title=child_title, route=child_route, parent=parent,
                is_enabled=bool(child_route), sort_order=child_order * 10)


class Migration(migrations.Migration):
    dependencies = [('core', '0003_galleryphoto_homedirection_homesection_event_image_and_more')]
    operations = [migrations.RunPython(seed_content, migrations.RunPython.noop)]
