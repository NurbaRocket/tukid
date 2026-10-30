from copy import deepcopy

from django.db import migrations


ABOUT_BODY = '''<p>Наша ассоциация была основана 2 декабря 2020 года и направлена на содействие экономическому, социальному и культурному развитию Кыргызстана.</p>
<p>В этом направлении мы оказываем поддержку различным видам экономической деятельности наших членов, таким как внешняя торговля, инвестиции, услуги, заключение контрактов и логистика, чтобы обеспечить наиболее эффективную оценку регионального и отраслевого потенциала. Кроме того, развитие корпоративной культуры, декоммунизация частного инвестиционного предпринимательства и повышение предпринимательской квалификации являются одними из наших приоритетов.</p>
<p>Наша ассоциация работает над решением проблем, с которыми сталкиваются промышленники и предприниматели, и стремится стать ведущей организацией в стране, защищая свои интересы.</p>
<p>В состав нашей ассоциации входят более 70 турецких и кыргызских деловых людей и компаний, работающих в Кыргызстане. Наши члены работают в самых разных секторах экономики и вносят значительный вклад в развитие Кыргызстана.</p>
<p>Кроме того, наша ассоциация является членом Совета по антикоррупционным делам при Президенте Кыргызской Республики и Совета по инвестициям при Кабинете Министров Кыргызской Республики.</p>'''

ABOUT_TRANSLATIONS = {
    'ky': '''<p>Биздин ассоциация 2020-жылдын 2-декабрында түзүлгөн жана Кыргызстандын экономикалык, социалдык жана маданий өнүгүүсүнө көмөктөшүүгө багытталган.</p>
<p>Бул багытта аймактык жана тармактык мүмкүнчүлүктөрдү эң натыйжалуу баалоо үчүн мүчөлөрүбүздүн тышкы соода, инвестиция, кызмат көрсөтүү, келишим түзүү жана логистика сыяктуу экономикалык ишмердиктерине колдоо көрсөтөбүз. Ошондой эле корпоративдик маданиятты өнүктүрүү, жеке инвестициялык ишкердикти декоммунизациялоо жана ишкердик квалификацияны жогорулатуу биздин артыкчылыктарыбыздын катарына кирет.</p>
<p>Биздин ассоциация өнөр жайчылар менен ишкерлер туш болгон көйгөйлөрдү чечүүнүн үстүндө иштейт жана өз кызыкчылыктарын коргоп, өлкөдөгү алдыңкы уюм болууга умтулат.</p>
<p>Ассоциациябыздын курамына Кыргызстанда иштеген 70тен ашык түрк жана кыргыз ишкерлери менен компаниялары кирет. Биздин мүчөлөр экономиканын ар түрдүү тармактарында иштеп, Кыргызстандын өнүгүүсүнө олуттуу салым кошушат.</p>
<p>Мындан тышкары, ассоциациябыз Кыргыз Республикасынын Президентине караштуу Коррупцияга каршы иштер боюнча кеңештин жана Кыргыз Республикасынын Министрлер Кабинетине караштуу Инвестициялар боюнча кеңештин мүчөсү болуп саналат.</p>''',
    'tr': '''<p>Derneğimiz 2 Aralık 2020 tarihinde kurulmuş olup Kırgızistan'ın ekonomik, sosyal ve kültürel gelişimine katkıda bulunmayı amaçlamaktadır.</p>
<p>Bu doğrultuda, bölgesel ve sektörel potansiyelin en etkin şekilde değerlendirilmesini sağlamak amacıyla üyelerimizin dış ticaret, yatırım, hizmetler, sözleşme yapma ve lojistik gibi çeşitli ekonomik faaliyetlerini destekliyoruz. Ayrıca kurumsal kültürün geliştirilmesi, özel yatırım girişimciliğinin dekomünizasyonu ve girişimcilik yeterliliklerinin artırılması önceliklerimiz arasındadır.</p>
<p>Derneğimiz, sanayicilerin ve girişimcilerin karşılaştığı sorunların çözümü için çalışmakta ve çıkarlarını koruyarak ülkede öncü bir kuruluş olmayı hedeflemektedir.</p>
<p>Derneğimizin bünyesinde Kırgızistan'da faaliyet gösteren 70'ten fazla Türk ve Kırgız iş insanı ve şirket bulunmaktadır. Üyelerimiz ekonominin çok çeşitli sektörlerinde çalışmakta ve Kırgızistan'ın gelişimine önemli katkılar sağlamaktadır.</p>
<p>Ayrıca derneğimiz, Kırgız Cumhuriyeti Cumhurbaşkanlığı bünyesindeki Yolsuzlukla Mücadele İşleri Konseyi ve Kırgız Cumhuriyeti Bakanlar Kurulu bünyesindeki Yatırım Konseyi üyesidir.</p>''',
}


def publish_about(apps, schema_editor):
    Page = apps.get_model('core', 'Page')
    page, _ = Page.objects.using(schema_editor.connection.alias).get_or_create(
        slug='about', defaults={'title': 'О нас'},
    )
    # Keep the editor's cover, title, publication status and other translated fields.
    translations = deepcopy(page.translations or {})
    for language, body in ABOUT_TRANSLATIONS.items():
        translations.setdefault(language, {})['body'] = body
    page.body = ABOUT_BODY
    page.translations = translations
    page.save(using=schema_editor.connection.alias, update_fields=['body', 'translations'])


class Migration(migrations.Migration):
    dependencies = [('core', '0018_applicationrequestlimit')]
    operations = [migrations.RunPython(publish_about, migrations.RunPython.noop)]
