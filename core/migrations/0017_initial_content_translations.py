from copy import deepcopy

from django.db import migrations


STARTER_TRANSLATIONS = {
    '<div>\n<h2>Наша миссия</h2>\n<p>Наша миссия — содействовать развитию экономических отношений между Турцией и Кыргызстаном — дружественными и братскими странами, а также способствовать увеличению объёмов взаимной торговли.</p>\n<p>В этом направлении мы уделяем особое внимание не только экономическому сотрудничеству, но и укреплению культурных, социальных и торговых связей между двумя государствами.</p>\n</div>\n<div>\n<h2>Наше видение</h2>\n<p>Наше видение — стать ведущей организацией в Кыргызстане, содействующей экономическому, социальному и культурному развитию страны путём максимально эффективного использования регионального и отраслевого потенциала, решения проблем, с которыми сталкиваются промышленники и предприниматели, а также защиты их интересов.</p>\n<p>В рамках этой деятельности нашими приоритетными задачами являются поддержка экономической деятельности членов Ассоциации, прежде всего в сферах внешней торговли, туризма, инвестиций, услуг, строительства и логистики.</p>\n<p>Мы также стремимся содействовать развитию корпоративной культуры, популяризации частных инвестиционных инициатив, расширению предпринимательской деятельности и укреплению профессиональных и деловых компетенций предпринимателей.</p>\n</div>': {'ky': '<div>\n<h2>Биздин миссиябыз</h2>\n<p>Биздин миссиябыз — дос жана боордош өлкөлөр болгон Түркия менен Кыргызстандын ортосундагы экономикалык мамилелерди өнүктүрүүгө, ошондой эле өз ара сооданын көлөмүн көбөйтүүгө көмөк көрсөтүү.</p>\n<p>Бул багытта биз экономикалык кызматташтыкка гана эмес, эки мамлекеттин ортосундагы маданий, социалдык жана соода байланыштарын бекемдөөгө да өзгөчө көңүл бурабыз.</p>\n</div>\n<div>\n<h2>Биздин көз карашыбыз</h2>\n<p>Биздин көз карашыбыз — аймактык жана тармактык мүмкүнчүлүктөрдү мүмкүн болушунча натыйжалуу пайдалануу, өнөр жайчылар менен ишкерлер туш болгон көйгөйлөрдү чечүү жана алардын кызыкчылыктарын коргоо аркылуу өлкөнүн экономикалык, социалдык жана маданий өнүгүүсүнө көмөк көрсөтүүчү Кыргызстандагы алдыңкы уюм болуу.</p>\n<p>Бул ишмердүүлүктүн алкагында биздин артыкчылыктуу милдеттерибиз — бирикменин мүчөлөрүнүн, өзгөчө тышкы соода, туризм, инвестиция, кызмат көрсөтүү, курулуш жана логистика чөйрөлөрүндөгү экономикалык ишмердүүлүгүн колдоо.</p>\n<p>Ошондой эле биз корпоративдик маданиятты өнүктүрүүгө, жеке инвестициялык демилгелерди жайылтууга, ишкердик ишмердүүлүктү кеңейтүүгө жана ишкерлердин кесиптик жана ишкердик компетенцияларын бекемдөөгө көмөк көрсөтүүгө умтулабыз.</p>\n</div>', 'tr': "<div>\n<h2>Misyonumuz</h2>\n<p>Misyonumuz, dost ve kardeş ülkeler olan Türkiye ile Kırgızistan arasındaki ekonomik ilişkilerin gelişmesine ve karşılıklı ticaret hacminin artmasına katkıda bulunmaktır.</p>\n<p>Bu doğrultuda yalnızca ekonomik iş birliğine değil, iki ülke arasındaki kültürel, sosyal ve ticari bağların güçlendirilmesine de özel önem veriyoruz.</p>\n</div>\n<div>\n<h2>Vizyonumuz</h2>\n<p>Vizyonumuz; bölgesel ve sektörel potansiyeli en verimli şekilde kullanarak, sanayici ve girişimcilerin karşılaştıkları sorunları çözerek ve çıkarlarını koruyarak ülkenin ekonomik, sosyal ve kültürel gelişimine katkıda bulunan, Kırgızistan'ın öncü kuruluşlarından biri olmaktır.</p>\n<p>Bu faaliyetler kapsamında öncelikli görevimiz; başta dış ticaret, turizm, yatırım, hizmetler, inşaat ve lojistik olmak üzere dernek üyelerinin ekonomik faaliyetlerini desteklemektir.</p>\n<p>Ayrıca kurumsal kültürün gelişmesine, özel yatırım girişimlerinin yaygınlaşmasına, girişimcilik faaliyetlerinin genişlemesine ve girişimcilerin mesleki ve ticari yetkinliklerinin güçlenmesine katkı sağlamayı hedefliyoruz.</p>\n</div>"},
    'TUKID объединяет турецко-кыргызское сообщество вокруг предпринимательства, культуры, солидарности и дружбы.\n\nЭто пространство для общения, обмена опытом и совместных инициатив, где деловые связи дополняются уважением к традициям и доверием между людьми.': {'ky': 'TUKID түрк-кыргыз коомчулугун ишкердик, маданият, тилектештик жана достуктун айланасында бириктирет.\n\nБул — баарлашуу, тажрыйба алмашуу жана биргелешкен демилгелер үчүн мейкиндик. Бул жерде ишкердик байланыштар салттарга болгон урмат жана адамдардын өз ара ишеними менен толукталат.', 'tr': 'TUKID, Türk-Kırgız topluluğunu girişimcilik, kültür, dayanışma ve dostluk etrafında bir araya getirir.\n\nİletişim, deneyim paylaşımı ve ortak girişimler için bir buluşma noktasıdır. İş ilişkileri, geleneklere saygı ve insanlar arasındaki güvenle güçlenir.'},
    'TUKID — Общественное объединение турецко-кыргызских предпринимателей, культуры, солидарности и дружбы.': {'ky': 'TUKID — Түрк-кыргыз ишкерлеринин маданият, тилектештик жана достук коомдук бирикмеси.', 'tr': 'TUKID — Türk-Kırgız İş İnsanları, Kültür, Dayanışma ve Dostluk Derneği.'},
    'TÜKİD активно участвует в работе государственных консультативных и инвестиционных органов Кыргызской Республики и взаимодействует с дипломатическими представительствами в целях укрепления делового сотрудничества и развития инвестиционного климата.': {'ky': 'TÜKİD ишкердик кызматташтыкты бекемдөө жана инвестициялык климатты өнүктүрүү максатында Кыргыз Республикасынын мамлекеттик консультациялык жана инвестициялык органдарынын ишине активдүү катышат жана дипломатиялык өкүлчүлүктөр менен кызматташат.', 'tr': "TÜKİD, iş birliğini güçlendirmek ve yatırım ortamını geliştirmek amacıyla Kırgız Cumhuriyeti'nin kamu danışma ve yatırım organlarının çalışmalarına aktif olarak katılır ve diplomatik temsilciliklerle iş birliği yapar."},
    'TÜKİD входит в состав Совета по инвестициям при Кабинете Министров Кыргызской Республики и участвует в обсуждении ключевых вопросов инвестиционной политики и поддержки бизнеса.': {'ky': 'TÜKİD Кыргыз Республикасынын Министрлер Кабинетине караштуу Инвестициялар боюнча кеңештин курамына кирет жана инвестициялык саясаттын жана бизнести колдоонун негизги маселелерин талкуулоого катышат.', 'tr': 'TÜKİD, Kırgız Cumhuriyeti Bakanlar Kurulu bünyesindeki Yatırım Konseyinde yer alarak yatırım politikası ve iş dünyasının desteklenmesine ilişkin temel konuların görüşülmesine katılır.'},
    'TÜKİD поддерживает тесное сотрудничество с Посольством Турецкой Республики в Бишкеке и соответствующими советниками по вопросам экономики, торговли и инвестиций.': {'ky': 'TÜKİD экономика, соода жана инвестиция маселелери боюнча Түркия Республикасынын Бишкектеги Элчилиги жана тиешелүү кеңешчилер менен тыгыз кызматташат.', 'tr': 'TÜKİD, ekonomi, ticaret ve yatırım konularında Türkiye Cumhuriyeti Bişkek Büyükelçiliği ve ilgili müşavirlerle yakın iş birliği yürütür.'},
    'TÜKİD является участником Совета по деловым вопросам в сфере противодействия коррупции при Президенте Кыргызской Республики и вносит вклад в формирование прозрачной и благоприятной деловой среды.': {'ky': 'TÜKİD Кыргыз Республикасынын Президентине караштуу коррупцияга каршы аракеттенүү жаатындагы ишкердик маселелер боюнча кеңештин катышуучусу болуп саналат жана ачык-айкын, жагымдуу ишкердик чөйрөнү түзүүгө салым кошот.', 'tr': 'TÜKİD, Kırgız Cumhuriyeti Cumhurbaşkanlığı bünyesindeki Yolsuzlukla Mücadele Alanında İş Dünyası Konseyine katılarak şeffaf ve elverişli bir iş ortamının oluşmasına katkıda bulunur.'},
    'Анонсы': {'ky': 'Алдыдагы иш-чаралар', 'tr': 'Yaklaşan etkinlikler'},
    'Анонсы мероприятий TÜKİD и событий с участием объединения появятся здесь.': {'ky': 'Бул жерде TÜKİD иш-чараларынын жана бирикме катышкан окуялардын жарыялары чыгат.', 'tr': 'TÜKİD etkinlikleri ve derneğin katılacağı programların duyuruları burada yer alacaktır.'},
    'Бизнес': {'ky': 'Бизнес', 'tr': 'İş dünyası'},
    'ВСТРЕЧИ И СОБЫТИЯ': {'ky': 'ЖОЛУГУШУУЛАР ЖАНА ОКУЯЛАР', 'tr': 'BULUŞMALAR VE ETKİNLİKLER'},
    'Взаимная поддержка, участие и совместные инициативы.': {'ky': 'Өз ара колдоо, катышуу жана биргелешкен демилгелер.', 'tr': 'Karşılıklı destek, katılım ve ortak girişimler.'},
    'Взаимодействие с Посольством Турецкой Республики в Бишкеке и соответствующими советниками': {'ky': 'Түркия Республикасынын Бишкектеги Элчилиги жана тиешелүү кеңешчилер менен кызматташтык', 'tr': 'Türkiye Cumhuriyeti Bişkek Büyükelçiliği ve ilgili müşavirlerle iş birliği'},
    'Все встречи': {'ky': 'Бардык жолугушуулар', 'tr': 'Tüm görüşmeler'},
    'Все мероприятия': {'ky': 'Бардык иш-чаралар', 'tr': 'Tüm etkinlikler'},
    'Все новости': {'ky': 'Бардык жаңылыктар', 'tr': 'Tüm haberler'},
    'Все права защищены.': {'ky': 'Бардык укуктар корголгон.', 'tr': 'Tüm hakları saklıdır.'},
    'Все члены': {'ky': 'Бардык мүчөлөр', 'tr': 'Tüm üyeler'},
    'Встреча участников TUKID': {'ky': 'TUKID катышуучуларынын жолугушуусу', 'tr': 'TUKID üyelerinin buluşması'},
    'Встречи и визиты представителей TÜKİD: государственные органы, дипломатические миссии, деловые объединения и компании.': {'ky': 'TÜKİD өкүлдөрүнүн мамлекеттик органдар, дипломатиялык өкүлчүлүктөр, ишкер бирикмелер жана компаниялар менен жолугушуулары жана сапарлары.', 'tr': 'TÜKİD temsilcilerinin kamu kurumları, diplomatik misyonlar, iş dünyası kuruluşları ve şirketlerle görüşmeleri ve ziyaretleri.'},
    'Встречи, традиции и моменты, из которых складывается наше сообщество.': {'ky': 'Коомчулугубузду түзгөн жолугушуулар, салттар жана көз ирмемдер.', 'tr': 'Topluluğumuzu oluşturan buluşmalar, gelenekler ve anlar.'},
    'ДИАЛОГ И ПАРТНЁРСТВО': {'ky': 'ДИАЛОГ ЖАНА ӨНӨКТӨШТҮК', 'tr': 'DİYALOG VE İŞ BİRLİĞİ'},
    'Деловые знакомства, обмен опытом и возможности для сотрудничества.': {'ky': 'Ишкердик таанышуулар, тажрыйба алмашуу жана кызматташуу мүмкүнчүлүктөрү.', 'tr': 'İş bağlantıları, deneyim paylaşımı ve iş birliği fırsatları.'},
    'Дружба': {'ky': 'Достук', 'tr': 'Dostluk'},
    'Жизнь объединения': {'ky': 'Бирикменин жашоосу', 'tr': 'Dernek yaşamı'},
    'Здесь появятся новости о деятельности TÜKİD, его участниках и совместных проектах.': {'ky': 'Бул жерде TÜKİD ишмердүүлүгү, анын катышуучулары жана биргелешкен долбоорлор жөнүндө жаңылыктар чыгат.', 'tr': "TÜKİD'in faaliyetleri, üyeleri ve ortak projeleri hakkındaki haberler burada yayınlanacaktır."},
    'Знакомство с традициями и культурный обмен между Турцией и Кыргызстаном.': {'ky': 'Түркия менен Кыргызстандын салттары менен таанышуу жана маданий алмашуу.', 'tr': 'Türkiye ve Kırgızistan arasında gelenekleri tanıma ve kültürel paylaşım.'},
    'Знакомство становится партнёрством.': {'ky': 'Таанышуу өнөктөштүккө айланат.', 'tr': 'Tanışmalar iş birliğine dönüşür.'},
    'Институциональное сотрудничество': {'ky': 'Институционалдык кызматташтык', 'tr': 'Kurumsal iş birliği'},
    'Карьера': {'ky': 'Карьера', 'tr': 'Kariyer'},
    'Контакты': {'ky': 'Байланыш', 'tr': 'İletişim'},
    'Культура': {'ky': 'Маданият', 'tr': 'Kültür'},
    'ЛЮДИ, КОТОРЫЕ НАС ОБЪЕДИНЯЮТ': {'ky': 'БИЗДИ БИРИКТИРГЕН АДАМДАР', 'tr': 'BİZİ BİRLEŞTİREN İNSANLAR'},
    'Мероприятия': {'ky': 'Иш-чаралар', 'tr': 'Etkinlikler'},
    'Миссия и видение': {'ky': 'Миссиябыз жана көз карашыбыз', 'tr': 'Misyonumuz ve Vizyonumuz'},
    'НАШЕ ДЕЛОВОЕ СООБЩЕСТВО': {'ky': 'БИЗДИН ИШКЕР КООМЧУЛУК', 'tr': 'İŞ DÜNYASI TOPLULUĞUMUZ'},
    'Наши члены': {'ky': 'Мүчөлөрүбүз', 'tr': 'Üyelerimiz'},
    'Новости': {'ky': 'Жаңылыктар', 'tr': 'Haberler'},
    'Новости TÜKİD': {'ky': 'TÜKİD жаңылыктары', 'tr': 'TÜKİD haberleri'},
    'О нас': {'ky': 'Биз жөнүндө', 'tr': 'Hakkımızda'},
    'ОБ ОБЪЕДИНЕНИИ': {'ky': 'БИРИКМЕ ЖӨНҮНДӨ', 'tr': 'DERNEK HAKKINDA'},
    'Общественное объединение турецко-кыргызских предпринимателей, культуры, солидарности и дружбы': {'ky': 'Түрк-кыргыз ишкерлеринин маданият, тилектештик жана достук коомдук бирикмеси', 'tr': 'Türk-Kırgız İş İnsanları, Kültür, Dayanışma ve Dostluk Derneği'},
    'Общественное объединение турецко-кыргызских предпринимателей, культуры, солидарности и дружбы.': {'ky': 'Түрк-кыргыз ишкерлеринин маданият, тилектештик жана достук коомдук бирикмеси.', 'tr': 'Türk-Kırgız İş İnsanları, Kültür, Dayanışma ve Dostluk Derneği.'},
    'Объединяем людей.\nРазвиваем партнёрство.\nУкрепляем дружбу.': {'ky': 'Адамдарды бириктиребиз.\nӨнөктөштүктү өнүктүрөбүз.\nДостукту бекемдейбиз.', 'tr': 'İnsanları bir araya getiriyoruz.\nİş birliklerini geliştiriyoruz.\nDostluğu güçlendiriyoruz.'},
    'Официальные встречи': {'ky': 'Расмий жолугушуулар', 'tr': 'Resmî görüşmeler'},
    'Предстоящие мероприятия': {'ky': 'Алдыдагы иш-чаралар', 'tr': 'Yaklaşan etkinlikler'},
    'Прошедшие мероприятия': {'ky': 'Өткөн иш-чаралар', 'tr': 'Geçmiş etkinlikler'},
    'СОБЫТИЯ ОБЪЕДИНЕНИЯ': {'ky': 'БИРИКМЕДЕГИ ОКУЯЛАР', 'tr': 'DERNEKTEN GELİŞMELER'},
    'СОТРУДНИЧЕСТВО': {'ky': 'КЫЗМАТТАШТЫК', 'tr': 'İŞ BİRLİĞİ'},
    'Совет правления': {'ky': 'Башкаруу кеңеши', 'tr': 'Yönetim Kurulu'},
    'Солидарность': {'ky': 'Тилектештик', 'tr': 'Dayanışma'},
    'Сообщество TUKID': {'ky': 'TUKID коомчулугу', 'tr': 'TUKID topluluğu'},
    'Стать членом': {'ky': 'Мүчө болуу', 'tr': 'Üye ol'},
    'Стать членом объединения': {'ky': 'Бирикмеге мүчө болуу', 'tr': 'Üye ol'},
    'Укрепление связей между людьми, сообществами и двумя странами.': {'ky': 'Адамдардын, коомчулуктардын жана эки өлкөнүн ортосундагы байланыштарды бекемдөө.', 'tr': 'İnsanlar, topluluklar ve iki ülke arasındaki bağları güçlendirme.'},
    'Участие в Совете по деловым вопросам в сфере противодействия коррупции при Президенте Кыргызской Республики': {'ky': 'Кыргыз Республикасынын Президентине караштуу коррупцияга каршы аракеттенүү жаатындагы ишкердик маселелер боюнча кеңешке катышуу', 'tr': 'Kırgız Cumhuriyeti Cumhurbaşkanlığı bünyesindeki Yolsuzlukla Mücadele Alanında İş Dünyası Konseyi çalışmalarına katılım'},
    'ЧТО НАС ОБЪЕДИНЯЕТ': {'ky': 'БИЗДИ ЭМНЕ БИРИКТИРЕТ', 'tr': 'BİZİ BİRLEŞTİREN DEĞERLER'},
    'Четыре направления. Одно сообщество.': {'ky': 'Төрт багыт. Бир коомчулук.', 'tr': 'Dört alan. Tek topluluk.'},
    'Членство в Совете по инвестициям при Кабинете Министров Кыргызской Республики': {'ky': 'Кыргыз Республикасынын Министрлер Кабинетине караштуу Инвестициялар боюнча кеңешке мүчөлүк', 'tr': 'Kırgız Cumhuriyeti Bakanlar Kurulu bünyesindeki Yatırım Konseyine üyelik'},
    'Члены TÜKİD': {'ky': 'TÜKİD мүчөлөрү', 'tr': 'TÜKİD üyeleri'},
    'г. Бишкек, улица Турусбекова, 82/1': {'ky': 'Бишкек ш., Турусбеков көчөсү, 82/1', 'tr': 'Bişkek, Turusbekov Caddesi, 82/1'},
}

CONTENT_MODELS = {
    'HomeDirection': ('title', 'description'),
    'HomeSection': ('eyebrow', 'title', 'description', 'image_alt', 'link_label', 'secondary_label'),
    'InstitutionalCooperation': ('title', 'description'),
    'MenuItem': ('title',),
    'Page': ('title', 'body', 'image_alt', 'meta_description'),
    'SiteSettings': ('name', 'organization_name', 'site_description', 'address', 'footer_text', 'copyright_text'),
}


def seed_translations(apps, schema_editor):
    db = schema_editor.connection.alias
    for name, fields in CONTENT_MODELS.items():
        Model = apps.get_model('core', name)
        for obj in Model.objects.using(db).all():
            data = deepcopy(obj.translations or {})
            for field in fields:
                original = getattr(obj, field)
                for language, translated in STARTER_TRANSLATIONS.get(original, {}).items():
                    values = data.setdefault(language, {})
                    if not values.get(field):
                        values[field] = translated
            if data != obj.translations:
                Model.objects.using(db).filter(pk=obj.pk).update(translations=data)


class Migration(migrations.Migration):
    dependencies = [('core', '0016_application_language')]
    operations = [migrations.RunPython(seed_translations, migrations.RunPython.noop)]
