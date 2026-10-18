# WP-10 — temiz kurulum ve katkı teslimi

WP-10'un ilk ZIP teslimi WP-09'un **yerelde doğrulanmış** altyapısı üzerinden
hazırlandı. Sonraki GitHub aktarımında [gerçek hosted kabul](https://github.com/SerhatAnkt/gemstone-testlab/actions/runs/39155570890)
da geçti. On ardışık tam koşu hedefi ve upstream gönderimleri açık olduğundan
bu durum ilk sürümün etiketlenip yayımlandığı anlamına gelmez.

## Teslim bileşenleri

| Bileşen | Dosya | Kabul davranışı |
| --- | --- | --- |
| Temiz kurulum | `QUICKSTART.md` | Sabit ortam, hash ile Python/SDK kurulumu, ilk host/seri koşusu |
| Tek komutla tam yerel kabul | `tools/run_release.py` | Dört zorunlu profil + mevcut `ci-verify`; hata/eksik profil toplam başarı vermez |
| Sade kaynak dağıtımı | `tools/export_source.py` | Seçili kaynaklar, 27 kilitli upstream dosyası, deterministik ZIP ve dosya manifesti |
| Bağımsız katkı kanıtı | `tools/check_contributions.py` | Her yama ayrı uygulanır; gerçek baseline call hatası → yalnız ilgili yama ile başarı |
| Katkı eşlemesi | `contributions/series.json` | Beş yama, değişmesi gereken dosyalar ve kesin regresyon node'ları |
| PR taslakları | `contributions/01-*.md`…`05-*.md` | Sorun, düzeltme, komut, kanıt kapsamı ve sınırlar |
| Katkı süreci | `CONTRIBUTING.md`, `.github/` şablonları | Küçük değişiklikler, gerçek kanıt ve güncel hedef dalda yeniden doğrulama |

`run_release.py`, `ci` ve `ci-verify` kabul kurallarını tekrar uygulayan ikinci
bir test motoru değildir; mevcut araçları başlatır ve sonuçları birleştirir.
Çıktı kökü yeni dizin olmak zorundadır. Host/seri/CAN/AArch64'ün hiçbiri atlanamaz.
Başlatıcı ve alt süreç kodları ayrı görünür; bir hata sonrası kalan profillerin
kanıtı da toplanır. Tüm başlatıcılar ortak süreç yöneticisiyle sınırlanır.

## Kaynak paketi ile tam kanıt paketi

`Gemstone_TestLab_Source.zip`, Git'e aktarılacak sade proje ağacıdır. SDK,
wheel, `.git`, build ve geçmiş ham kanıt dosyaları içermez. Lisans/NOTICE,
testler, workflow, kılavuzlar, yamalar ve seçilmiş özgün örnekler korunur.
Paket kaynakları checkout'a uygulama yaması eklenmiş gibi sunmaz.

`Gemstone_TestLab.zip` ise önceki iş paketlerinin başarı/başarısızlık kayıtlarını
da içeren tam teslimdir. Tarihsel raporlar güncel koşu gibi yeniden etiketlenmez.
Kaynak paketinde geçmiş rapor yollarının bulunmaması bilinçli dağıtım farkıdır.

Kaynak exporter'ı 27 upstream girdisinin SHA-256/boyut/Git blob kimliğini
kontrol eder. İzin verilen dizin ve uzantılardan dosya toplar; symlink ve ELF
dosyalarını reddeder. ZIP dosya sırası, zaman damgaları ve mode'ları sabittir.
Aynı kaynak ve aynı exporter/zlib ortamında aynı ZIP baytları üretilir; farklı
sıkıştırıcı sürümleri arasında byte eşitliği sözü verilmez. İç manifestteki
`content_sha256`, manifest dışındaki tüm dosya kayıtlarının deterministik JSON
özetidir; kendi dosyasını hash'lemeye çalışmaz.

`--verify`, arşivi açmadan yolu, yinelenen girişi, dosya listesini, mode/boyut/
SHA-256 ve CRC'yi denetler. Bu, kazara bozulmayı yakalayan içerik bütünlüğü
kontrolüdür. İmza, yayın kimliği veya kriptografik runner tasdiki değildir.

Exporter'ın gerçek dosyalarla olumlu/olumsuz kontrolleri tekrar çalıştırılabilir:

```sh
python3 tools/check_delivery.py --output artifacts/delivery-first
```

Bu komut özel kaynak kopyasında iki byte-eş arşiv üretir; bozulma, eksik/fazla
dosya, yinelenen kayıt, dizin dışına çıkan yol, bozuk manifest, kaynak değişikliği,
symlink ve eski çıktı üzerine yazma davranışlarını denetler. Asıl kaynakları
değiştirmez. Her deneme gerçek exporter CLI'sini çalıştırır.

## Bağımsız yama kontrolü

Her giriş kilitli özgün 27 dosyadan yeni bir kaynak kopyası oluşturur; diğer
dört yama bu kopyaya uygulanmaz. `git apply --check` ve gerçek apply sonucu
kaydedilir. Değişen dosyalar `series.json` ile birebir karşılaştırılır.
Seçilen baseline vakalarının setup/teardown'ı geçmeli, call fazı başarısız
olmalı ve gerçek pytest çıkışı 1 kalmalıdır. Fixed vakalarının tamamı geçmeli;
ortak rapor/JUnit/kanıt denetimi de başarı vermelidir.

Bu odaklı kanıt, birlikte uygulanmış tüm yamaların tam 45 seri/36 CAN matrisini
geçmesinden farklı bir inceleme sorusunu yanıtlar: **Bu küçük yama kendi
iddia ettiği kusuru tek başına düzeltiyor mu?** İki kanıt birlikte tutulur.

## Tekrar ve doğrulama kapsamı

Temiz kurulum, kaynak ZIP'inden yeni dizine açılarak ve yeni Python venv'iyle
denenir. SDK kilitli arşivden doğrulanır; `run_release.py` dört profili gerçekten
başlatır. Host CAN'a izin vermediğinde ayrı Linux konuğu yolu açıkça seçilir.
VM toplam kabulü Git metadatası olmayan kaynak dağıtımını destekler; checkout
kimliği gereken GitHub akışı native CAN kullanır.

Yeni araçların hata yolları gerçek komutlarla ayrıca denetlenir: var olan çıktı,
eksik önkoşul, yanlış arşiv listesi, bozuk içerik ve özgün kaynak değişikliği
başarı üretmemelidir. Herhangi bir kontrollü hata kaydı gerçek geçmiş hata
olarak korunur; sonraki başarılı deneme onun üstüne yazılmaz.

Çalıştırılmış WP-10 deneylerinin sayısal sonuçları `RESULTS.md` ve
`artifacts/wp10-verification.json` içindedir. Önceki WP-09 kanıtları bu dosyalarda
yeniden koşulmuş gibi sunulmaz.
Üç yeni rapor türünün yapısı `docs/delivery.schema.json` ile sürümlenir;
test/CI raporları mevcut iki şemayı kullanmayı sürdürür. Şema biçimi denetler;
gerçek kabul matrisinin sahibi `ci-verify` ve ilgili kontrol aracıdır.

## Açık yayın maddeleri

[RELEASE_READINESS.md](RELEASE_READINESS.md) uzaktaki koşu, hedef depo ve fiziksel
kart kapsamını ayrı gösterir. WP-09 hosted kabulü sonradan gerçek GitHub
koşusuyla kapatıldı. İlk mimari plandaki on tekrar hedefi açık kalır. Yeni AHRS kapsamına geçmeden önce ilk sürümün bu maddeleri gözden
geçirilmelidir.
