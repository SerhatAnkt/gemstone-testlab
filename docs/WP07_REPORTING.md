# WP-07 — ortak rapor ve tek vaka yeniden üretimi

18 Ekim 2026. Sonuç biçimi sürümü: **1**. Şema:
[results.schema.json](results.schema.json). Bu, eski WP teslim özetlerinin
`artifacts/summary.json` sürüm numarasından bağımsızdır.

## Uygulanan davranış

CAN ve seri testleri aynı pytest eklentisinden sonuç üretir. pytest, test seçimi,
assertion'lar ve JUnit'in sahibi olarak kalır. İkinci bir test çalıştırıcısı veya
JUnit yazıcısı eklenmedi. TestLab, pytest fazlarını, kaynak girdilerini ve ham
kanıt bağlantılarını ortak JSON'a dönüştürür.

Her çalışma benzersiz UTC zaman damgası ve rastgele son ekle yeni bir dizin açar.
Mevcut çalışmanın üzerine yazılmaz. Vaka kimliği, okunabilir test adını node ID'nin
SHA-256 özetinden bir bölümle birleştirir; benzer parametre adları çakışmaz.

| Dosya | İçerik |
| --- | --- |
| `run.json` | Seçilen node'lar, durum/sayılar, kaynak ve test kodu özetleri, ortam |
| `junit.xml` | pytest'in ürettiği JUnit; kullanıcı başka XML yolu verdiyse buraya kopyası |
| `commands.jsonl` | Çalışma dizinindeki `process.json` kayıtlarının komut, çıkış ve temizlik özeti |
| `inputs/source/` | İlgili uygulama kaynaklarının doğrulanabilir, sınırlı kopyası |
| `cases/<id>/result.json` | Tek pytest node'u, parametreler, fazlar, beklenen/gözlenen veri, kanıtlar |
| `cases/<id>/failure.json` | Başarısız/hatalı vakanın sonucu ve yeniden üretim tarifi |
| `cases/<id>/evidence/` | Var olan CAN/seri `case.json`, süreç kayıtları, ham günlükler, olaylar |
| `failure.json` | Vaka başlamadan oluşan toplama veya çalışma politikası hatası |

Kanıt yolları `run.json` dizinine görelidir. Her kayıt boyut ve SHA-256 taşır.
Süreç kayıtlarının kendi içindeki eski mutlak argv/log yolları tarihsel bilgidir;
yeniden üretim bu argv alanlarını çalıştırmaz. TestLab'a ait JSON dosyaları önce
geçici dosyaya yazılır, sonra yerlerine geçirilir.

Host kontrolleri de faz ve JUnit raporu alır. Eski unittest süreç günlükleri,
`TESTLAB_EVIDENCE_ROOT` verildiyse o dizinde kalır; bu aşamadaki ortak cihaz
kanıt yerleşimi CAN ve seri fixture'ları içindir. `commands.jsonl`, çalışma kökü
altında kayıtlı süreçleri listeler; işletim sistemindeki her çağrının izi değildir.

## Sonuçların anlamı

| Durum | Kural |
| --- | --- |
| `passed` | Çalışma fazı geçti; kurulum ve temizlik başarısız olmadı |
| `failed` | Assertion, uygulama çıktısı veya süre sınırı gibi çalışma hatası |
| `error` | Kurulum/temizlik hatası, süreç başlatma/temizlik istisnası veya çalışma altyapısı hatası |
| `skipped` | pytest atlamayı açıkça kaydetti; başarı sayılmaz |
| `not_run` | Seçilmiş ama çalışmamış vaka; örneğin `--collect-only` |

Her vakada `setup`, `call`, `teardown` raporları korunur. Çalışma geçip temizlik
başarısızsa vaka `error` olur. Çalışma ve temizlik ayrı ayrı başarısızsa iki faz da
kaybolmaz; üst vaka `error` olur. JUnit'in fazları ayrı test girdileri olarak
gösterebildiği durumlarda, JSON'daki tek node sayısı ile XML girdi sayısı farklı
olabilir. XML değiştirilmez.

Süreç kaydının `failed` olması tek başına pytest vakanın başarısız olduğu anlamına
gelmez. HARNESS kontrolleri kasıtlı istisna veya takılma üretip temizliğin doğru
olduğunu sınar. TestLab bunları pytest sonucundan ayrı tutar.

Standart pytest çıkış kodları kullanılır: 0 başarı, 1 test başarısızlığı, 2
kesilme, 3 iç hata, 4 kullanım hatası, 5 test toplanmaması. Yeniden üretim, gerçek
pytest kodunu döndürür; hatanın yeniden görülmesi 0'a çevrilmez.

İki ek çalışma kontrolü vardır. Zorunlu `can`/`serial` vakası skip edilirse veya
test sırasında kaynak/test kodu değişirse, ham pytest kodu 0 olsa bile çalışma
`error` ve etkin kod 1 olur. `original_pytest_exitcode`, vaka fazları ve
`policy_errors` birlikte saklanır. Atlanmış vaka JUnit'te hâlâ skipped görünür;
başarısızlık gizlenmez. Hiç test toplanması pytest'in 5 kodunu korur.

## Kaynak ve ortam kaydı

Kaynak girdileri sözleşmeye göre seçilir: CAN için `canbus/`, seri için `serial/`,
ortak Make dosyaları; karma/host profili ikisini de içerir. Makefile ve seçilen
C/C++/Python kaynak/header dosyaları dosya adı, boyut ve SHA-256 ile kaydedilir.
Olması gereken ama eksik dosya da manifestte `null` özetle görünür. Gerekli dosyanın
eksikliği sessizce farklı bir kaynak profiline dönüştürülmez.

Snapshot sınırı 512 dosya ve 2 MiB'dir. Kaynak kökü dışına çıkan symlink ve `..`
yolları reddedilir. Bütün repository, kullanıcı ayarları, `.git` içeriği veya ortam
değişkenleri kopyalanmaz. Kaynak snapshot'ı testte seçilen uygulama girdileridir.

Test kodu, fixture'lar, gereksinim dosyaları, `pytest.ini` ve kaynak kilidi ayrıca
hash'lenir. Çalışma bitince kaynak ve test özetleri yeniden kontrol edilir.
Gerçek Git commit/dirty bilgisi bulunabiliyorsa ayrı kaydedilir. Vendored/özel
kopyada Git yoksa upstream referans commit'i çalıştırılmış Git commit'i gibi
gösterilmez. Upstream referansı ve test edilen dosyaların özeti ayrı alanlardır.

Python, pytest ve ilgili bağımlılık sürümleri; OS ailesi, mimari, kernel, UID,
backend ve süre çarpanı kaydedilir. Derleyici/binary kanıtları mevcut build
raporlarında kalır. ARM64 ve kart çalışması bu raporlarda `not_run`'dır.

## Nasıl çalıştırılır?

Paket kökünde Linux ve Python 3.12 ile sanal ortamı etkinleştirin:

```sh
python3 -m venv .venv-testlab
. .venv-testlab/bin/activate
python -m pip install --require-hashes -r tests/requirements-serial.txt
```

Özgün C seri RX kusurunu yeni ortak raporla üretmek için:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest 'tests/serial/test_terminal.py::test_serial_receive[binary-crlf-c]' --evidence-root artifacts/original-serial -q
```

Bu vaka gerçekten başarısız olur. Terminalde `TestLab report:` ve tam
`TestLab reproduce:` komutu yazılır. Sanal ortam açıkken bu ikinci komutu tek
satır olarak çalıştırın. Komut, hata dosyasını okur ve yeni çalışma dizini açar.

Arayüzün argümanları:

```sh
python -m tests.testlab reproduce --help
```

`--output-root`, yeni tekrarların üst dizinidir. `--source-root` isteğe bağlıdır;
verilen ağacın özeti kayıtlı girdilerle aynı olmalıdır. Varsayılan CAN/seri
yolunda kaynaklar raporun `inputs/source/` dizininden **yeni özel kopyaya** alınır.
Mevcut çalışma dosyaları resetlenmez, checkout yapılmaz, yama uygulanmaz veya
uzaktan kaynak indirilmez. Bu sayede değiştirilmiş bir kaynak kopyasının hatası da
orijinal geçici klasör artık yokken sınanabilir.

Yeniden üretimden önce:

1. Şema, run/vaka kimliği ve sınırlandırılmış tam node ID doğrulanır.
2. Güncel test kodu ile kayıtlı harness özeti karşılaştırılır.
3. Kaynak manifesti ve saklanan dosyalar doğrulanır; eksik/değişmiş snapshot reddedilir.
4. Python major/minor, OS ailesi, native mimari ve ilgili bağımlılık sürümleri karşılaştırılır.
5. Aynı node ve aynı süre çarpanıyla pytest başlatılır. Koleksiyonun tam bir vakadan
   oluşması gerekir; yalnızca bir dosyanın veya başka bir vakanın çalışması kabul edilmez.

Rapor içindeki keyfî `argv`/komut metinleri eval edilmez veya shell'e verilmez.
TestLab kendi izin verilen pytest argv listesini oluşturur. İmza/kimlik doğrulama
sistemi eklenmedi; hash'ler kaynak ve test girdilerinin eşleşmesini denetler.

`reproduction.json` yeni rapora, tam node eşleşmesine, yeni ortama ve eski/yeni
sonuç durumuna işaret eder. Yeni test hâlâ bozuksa komut 1 döndürür. Sonuç farklı
olursa `same_case_outcome` bunu gösterir; eski başarısızlık silinmez ve otomatik
tekrar denenmez. Ön doğrulama reddi kullanım kodu 2 ile, test başlatılmadan biter.

Host unittest yardımcıları kendi fixture kaynaklarını kullandığından, host
tekrarında paket girdilerinin de kayıtlı özetle eşleşmesi gerekir; cihaz tekrarları
gibi dışarıdan farklı bir host fixture kaynağı enjekte edilmez.

## CAN tekrarının iki ortamı

CAN yetkili normal Linux kullanıcı ortamında varsayılan `native` backend kullanılır.
Sanal arayüzü yalnızca sahipli fixture oluşturur; ayrıcalıklı `ip` işlemleri için
mevcut vcan kurulum şartları geçerlidir.

Host CAN yetkisi vermiyorsa `--backend can-vm`, `--guest-root` ve `--wheels`
seçenekleri tek komuta eklenir. CLI aynı node'u, kaynak snapshot'ını ve kayıtlı
süre çarpanını mevcut QEMU/Linux aracına iletir. Guest, pytest'i UID 1000 ile
çalıştırır. Guest'in kaynak snapshot'ı dahil ortak raporları host'a aktarılır.
Hazır runtime'ın kurulumu [VM_REPRODUCTION.md](VM_REPRODUCTION.md) içindedir.

Yeni host kernel'i veya derleyici sürümünün eskisiyle birebir aynı olduğu
iddia edilmez. Yeni ortam kaydı rapora eklenir. Dosya girdileri ve mantıksal vaka
korunur; geçici PTY/arayüz isimleri ve hazırlık nonce'ları yeniden üretilir.
Bu yol bir O1 veya ARM64 emülatörü değildir.

## Gerçek doğrulama

| Kontrol | Sonuç | Kanıt |
| --- | --- | --- |
| Host kontrolleri: önceki 37 + 9 yeni raporlama kontrolü | **46/46 geçti** | `artifacts/wp07-host/` |
| Seri yama kopyası, yeni ortak rapor | **45/45 geçti** | `artifacts/wp07-serial/` |
| CAN yama kopyası, gerçek vcan/UID 1000 | **36/36 geçti** | `artifacts/wp07-can-vm/` |
| Üç özgün seri kusuru | **3 gerçek başarısızlık korundu** | `artifacts/wp07-baseline/` |
| Taşınmış rapordan üç özgün seri kusuru + kasıtlı TX bozulması | **4/4 aynı vaka/sonuç, her biri pytest 1** | `artifacts/wp07-reproduction/experiment.json` |
| Özgün CAN C gönderici kusuru ve konukta aynı node tekrarı | **Gerçek başarısızlık yeniden görüldü** | `artifacts/wp07-can-baseline/`, `artifacts/wp07-can-reproduction/` |

Taşıma deneyinde eski run dizini erişilemez yapıldı, kaynak hint'i olmayan bir
adrese yöneltildi; özel bozuk kaynağın eski dizini de tekrar sırasında kapatıldı.
Testler saklanmış kaynak kopyasından aynı hatayı verdi. Özgün upstream dosyaları
değişmedi. Bu deneyin geçmesi, uygulama testlerinin geçtiği anlamına gelmez.

Yeni host kontrolleri gerçek alt pytest süreçleriyle faz önceliğini, JUnit hata
sayısını, boş/yanlış koleksiyonu, collect-only'yi, zorunlu skip'i, benzersiz run'ı,
tam node kapısını, keyfî argv'nin çalıştırılmamasını, bozulmuş snapshot/selector/
harness reddini ve test ortasında kaynak değişiminin görünürlüğünü doğrular.
Bu yardımcı kontroller cihaz entegrasyonu olarak sayılmaz.

36 CAN testinde 24 sahipli arayüz kaldırıldı; kalan arayüz yoktu. 256 süreç kaydı
temizlendi. Seri kabulünde 21 oturumun PTY'leri ve 50 süreç kaydı temizlendi;
üç süreç kaydı kasıtlı HARNESS istisnasıdır. Native seri çarpanı 1, TCG CAN
çarpanı 4'tür; her rapor gerçek profilini içerir.

CI rapor yolları güncellendi; GitHub hosted runner üzerinde çalıştırılmadı.
O1, fiziksel UART/CAN, ARM64 derleme/çalışma ve gerçek zaman davranışı denenmedi.
WP-08'in konusu doğrulanmış ARM64 araç zinciriyle çapraz derlemedir.

Pytest hook/JUnit arayüzü için birincil kaynak:
[pytest API reference](https://docs.pytest.org/en/stable/reference/reference.html).
