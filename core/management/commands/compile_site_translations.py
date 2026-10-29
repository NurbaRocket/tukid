import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Скомпилировать переводы интерфейса без установки GNU gettext.'

    def handle(self, *args, **options):
        try:
            import polib
        except ImportError as error:
            raise CommandError('Установите зависимости из requirements-dev.txt.') from error
        for code, _ in settings.LANGUAGES:
            if code == 'ru':
                continue
            path = settings.BASE_DIR / 'locale' / code / 'LC_MESSAGES' / 'django.po'
            if not path.exists():
                raise CommandError(f'Не найден каталог {path}.')
            catalog = polib.pofile(str(path))
            for entry in catalog:
                if entry.obsolete:
                    continue
                if not entry.translated():
                    raise CommandError(f'{code}: не заполнен перевод {entry.msgid!r}.')
                source = set(re.findall(r'%\((\w+)\)s', entry.msgid))
                target = set(re.findall(r'%\((\w+)\)s', entry.msgstr))
                if source != target:
                    raise CommandError(f'{code}: несовпадающие параметры в {entry.msgid!r}.')
            catalog.save_as_mofile(str(path.with_suffix('.mo')))
            self.stdout.write(self.style.SUCCESS(f'{code}: {len(catalog)} переводов.'))
