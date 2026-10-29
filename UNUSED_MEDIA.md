# Проверка использования медиафайлов

Дата: 2026-10-29T10:50:03+06:00. База проверена в транзакции READ ONLY.

Это состояние после очистки: удалено 1056 исходных файлов (4.86 МиБ) и 1056 копий collectstatic. Подробности: [MEDIA_CLEANUP.md](MEDIA_CLEANUP.md).

Проверены загрузки `media/`, исходные изображения, шрифты и видео в `core/static/`, а также шрифты PDF в `core/fonts/`. Этап аудита выполняется только в режиме чтения.

## Результат

| Категория | Файлов | Размер |
| --- | ---: | ---: |
| Загрузки без ссылок в БД и коде | 0 | 0.0 КиБ |
| Исходная статика без найденных ссылок | 2575 | 9.24 МиБ |
| Нет ссылок, но защищены как демо или динамические заглушки | 1565 | 4.28 МиБ |
| Есть только косвенные совпадения; нужна ручная проверка | 15 | 473.6 КиБ |
| Есть ссылки в проекте или базе | 323 | 9.09 МиБ |

Проверено 4403 текстовых файлов и 113 записей контента. Учтено 51 заполненных файловых полей, включая черновики, скрытые и демозаписи.

Список путей кандидатов: [unused-media-files.txt](unused-media-files.txt). Полный инвентарь с размерами и найденными ссылками: [unused-media.json](unused-media.json).

## Загрузки media/

Все 51 файлов в media/ связаны с БД или ссылками проекта. Загрузок без ссылок не найдено.

## Статика без найденных ссылок

Это кандидаты для отдельной проверки. Отсутствие ссылки не доказывает, что файл можно удалить: сторонние плагины могут собирать пути во время выполнения.

| Каталог внутри core/static/core/ | Файлов | Размер |
| --- | ---: | ---: |
| `vendor/rs-plugin` | 1663 | 8.20 МиБ |
| `vendor/twentytwenty` | 6 | 382.9 КиБ |
| `vendor/linea-icons` | 629 | 223.0 КиБ |
| `vendor/simple-line-icons` | 185 | 187.6 КиБ |
| `images` | 32 | 159.6 КиБ |
| `images/icons` | 25 | 34.1 КиБ |
| `images/patterns` | 1 | 21.2 КиБ |
| `images/logos` | 22 | 18.9 КиБ |
| `css/fonts` | 4 | 13.3 КиБ |
| `master/sass` | 4 | 13.3 КиБ |
| `vendor/owl.carousel` | 1 | 3.1 КиБ |
| `images/blog` | 2 | 2.1 КиБ |
| `images/landing` | 1 | 0.7 КиБ |

### Самые крупные кандидаты

| Файл | Размер |
| --- | ---: |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/maze_large.jpg` | 275.0 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/fibers_large.jpg` | 259.6 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/bwmap1.jpg` | 246.6 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/spiral_large.jpg` | 246.6 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/bwmap2.jpg` | 211.6 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/swirl_large.jpg` | 211.6 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/clouds_large.jpg` | 194.0 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/maze_small.jpg` | 149.0 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/pointilize_large.jpg` | 134.7 КиБ |
| `core/static/core/vendor/rs-plugin/fonts/font-awesome/fonts/FontAwesome.otf` | 131.6 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/spiral_small.jpg` | 121.4 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/swirl_small.jpg` | 120.6 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/glitch_large.jpg` | 119.1 КиБ |
| `core/static/core/vendor/twentytwenty/img/4_2.jpg` | 109.4 КиБ |
| `core/static/core/vendor/twentytwenty/img/5_2.jpg` | 109.4 КиБ |
| `core/static/core/vendor/twentytwenty/img/4_1.jpg` | 104.9 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/ripple_large.jpg` | 102.7 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/crystalize_large.jpg` | 84.2 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/fibers_small.jpg` | 74.7 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/rings_large.jpg` | 60.9 КиБ |
| `core/static/core/vendor/twentytwenty/img/5_1.jpg` | 52.8 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/clouds_small.jpg` | 30.0 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/glitch3.jpg` | 29.9 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/glitch_small.jpg` | 29.9 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/pointilize_small.jpg` | 29.5 КиБ |
| `core/static/core/vendor/rs-plugin/assets/sources/vm.png` | 23.2 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/distortion/images/crystalize_small.jpg` | 21.3 КиБ |
| `core/static/core/images/patterns/fancy.jpg` | 21.2 КиБ |
| `core/static/core/vendor/rs-plugin/assets/svg/busy-icons-svg/NewTux.svg` | 20.9 КиБ |
| `core/static/core/vendor/rs-plugin/revolution-addons/whiteboard/assets/busy-icons-svg/NewTux.svg` | 20.9 КиБ |

## Что сохранено отдельно

- Демоизображения и файлы демозаписей отмечены `protected`; они не включены в список обычных кандидатов.
- Шрифты PDF, запасные логотипы, favicon, логотипы сотрудничества и динамические заглушки учтены отдельно от буквальных ссылок.
- Проверены значения файловых полей всех моделей, независимо от публикации.
- PDF заявок и резюме хранятся в BinaryField PostgreSQL, а не отдельными файлами; их байты не читались.
- В `staticfiles/` найдено 4451 медиафайлов (22.60 МиБ). Это результат collectstatic, а не отдельный набор исходников; его не следует смешивать с сиротскими загрузками.

## Ограничения проверки

Ссылки искались в Python, шаблонах, CSS/JS, SVG, исходниках стилей, переводах и текстовом контенте БД. Учитывались относительные URL CSS и пути /static/ и /media/. Совпадения только по имени файла вынесены в `manual_review`. Динамические ссылки сторонних JS-плагинов полностью доказать статическим поиском нельзя. Все упоминания, включая тесты, миграции и не подключённые сейчас стили, считаются ссылками — оценка намеренно консервативная.

Аудит отражает текущую локальную базу и файлы; архивы, резервные копии и другие окружения могут содержать дополнительные ссылки. Удаление в рамках этой задачи не выполнялось.
