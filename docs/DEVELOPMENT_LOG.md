# Development log

These are the earlier project notes, written in Turkish. Some paths refer to
files in the older full ZIP. Those files are not part of this Git repository.
For a short result summary, see [RESULTS.md](../RESULTS.md).


Güncelleme: 18 Ekim 2026 Türkiye saati. WP-02, WP-03 ve WP-04 doğrulamaları
UTC 17 Ekim akşamı çalıştırıldı. WP-05, UTC 18 Ekim
gecesi doğrulandı. WP-06 aynı gece native PTY testleriyle doğrulandı.
İncelenen upstream referansı:
`2619a7584d39203a057abc08ab7c6698dc476868`.

## Kabul durumu

| İş paketi | Durum | Kanıt |
| --- | --- | --- |
| WP-01: CAN ve PTY yerel teknik deneyi | Geçti | `artifacts/native-final/`, `artifacts/can-linux-guest/` |
| WP-01: gerçek GitHub runner önkoşulları | **Geçti**; hosted vcan/PTY ve temizlik doğrulandı | [Koşu #2](https://github.com/SerhatAnkt/gemstone-testlab/actions/runs/39155570890) |
| WP-02: altı C/C++ hedef, ayrı dizinler, komut ve çıktı kaydı | **Geçti** | `artifacts/wp02-acceptance/` |
| WP-02: değişiklik ve hata regresyonları | **5/5 geçti** | `artifacts/wp02-regression/`, `tests/host/test_build_manager.py` |
| WP-03: süreç yönetimi ve temizlik | **17/17 süreç kontrolü geçti** | `artifacts/wp03-validation/` |
| WP-03 ile tüm host regresyonları | **22/22 geçti** | `host-tests.log` ve süreç kayıtları |
| WP-04: CAN sözleşmesi ve sahipli vcan fixture | **6/6 entegrasyon testi geçti** | `artifacts/wp04-vcan-validation/` |
| WP-04 ile tüm host regresyonları | **28/28 geçti** | `artifacts/wp04-host-final/pytest.log`, `junit.xml` |
| WP-04 ile altı C/C++ hedefin yeniden derlenmesi | **6/6 geçti** | `artifacts/wp04-builds/` |
| WP-05: host sözleşmeleri ve geç hazır olma regresyonu | **37/37 geçti** | `artifacts/wp05-host-final/` |
| WP-05: özgün C gönderici regresyonu | **Yeniden üretildi; gerçek test başarısızlığı** | `artifacts/wp05-baseline-regression/` |
| WP-05: önerilen yama ile zorunlu CAN matrisi | **36/36 geçti — yama kopyası** | `artifacts/wp05-vcan-acceptance/` |
| WP-05: kontrollü DLC bozulması | **Test tarafından reddedildi** | `artifacts/wp05-controlled-failure/` |
| WP-06: özgün seri sürümü | **34 geçti, 11 gerçek başarısızlık** | `artifacts/wp06-baseline-final/` |
| WP-06: önerilen dört seri yamasının kopyası | **45/45 geçti** | `artifacts/wp06-acceptance/` |
| WP-06: host ve özgün derlemeler | **37/37 ve 6/6 geçti** | `artifacts/wp06-host/`, `artifacts/wp06-builds/` |
| WP-06: kontrollü TX bozulması | **Gerçek PTY testi reddetti** | `artifacts/wp06-controlled-failure/` |
| WP-07: yeni raporlamayla host kontrolleri | **46/46 geçti** | `artifacts/wp07-host/` |
| WP-07: yeni raporlamayla seri/CAN yama profilleri | **45/45 seri, 36/36 vcan geçti** | `artifacts/wp07-serial/`, `artifacts/wp07-can-vm/` |
| WP-07: taşınmış kaynak/raporla seri tekrarları | **4 aynı node/sonuç; gerçek pytest 1** | `artifacts/wp07-reproduction/experiment.json` |
| WP-07: CAN hata raporundan konukta tek vaka tekrarı | **Aynı kusur yeniden görüldü; pytest 1** | `artifacts/wp07-can-reproduction/` |
| WP-08: kilitli Gemstone SDK ve altı ARM64 hedef | **6/6 AArch64 ELF geçti** | `artifacts/wp08-toolchain/`, `artifacts/wp08-cross-builds/` |
| WP-08: gerçek SDK ile olumsuz kontroller | **4/4 deney geçti; beklenen hatalar korundu** | `artifacts/wp08-controlled-final/` |
| WP-08: güncel host/seri kabulü | **54/54 host, 45/45 seri geçti** | `artifacts/wp08-host-final/`, `artifacts/wp08-serial-final/` |
| WP-09: ortak CI yürütme ve toplam yerel kabul | **66 host, 45 seri, 36 vcan ve 6 ARM64 hedef geçti** | `artifacts/wp09-acceptance/local.json` |
| WP-09: gerçek commit ve kabul hataları | **Doğrulandı; hatalar sıfırdan farklı kodla reddedildi** | `artifacts/wp09-current-pr/`, `artifacts/wp09-acceptance/` |
| WP-09: gerçek uzak CI kabulü | **Beş iş geçti**; indirilen kanıtlar yeniden doğrulandı | [Koşu #2](https://github.com/SerhatAnkt/gemstone-testlab/actions/runs/39155570890); `docs/ci-runs/39155570890.json` |
| WP-10: temiz kurulum ve tek komutla tam yerel kabul | **66 host, 45 seri, 36 gerçek vcan, 6 AArch64 hedef geçti** | `artifacts/wp10-clean-release/` |
| WP-10: beş bağımsız katkı yaması | **12 baseline call hatası → yalnız ilgili yamayla 12 başarı** | `artifacts/wp10-contributions/contributions.json` |
| WP-10: sade kaynak dağıtımı ve hata kontrolleri | **13 exporter kontrolü ve 7 olumsuz teslim/kurulum kontrolü geçti** | `artifacts/wp10-delivery-final/`, `artifacts/wp10-controls/` |

WP-02 için gereken ayrıcalıksız derleme kanıtları tamamlandı. WP-01'in açık CI
maddesi bu sonuçla kapanmış sayılmaz.

## Altı gerçek derleme

İlk kabul run kimliği: `20261017T220410-088dbbee`.
GCC/G++ 13.3.0 ve GNU Make 4.3 kullanıldı. Altı hedefin tamamı özgün alt proje
Makefile'larıyla derlendi. Warning bayrakları değiştirilmedi. Yirmi paketlenmiş
upstream dosyanın SHA-256 ve Git blob özetleri kaynağa uydu. WP-04'te iki özgün
Python gönderici dosyası eklendi; WP-04 kilidi 22 dosyadır. WP-05 ile güncel kilit
24 özgün dosyaydı. WP-06 ile üç özgün Python seri örneği dosyası eklenerek güncel kilit 27 dosya oldu.

| Hedef | Sonuç | ELF |
| --- | --- | --- |
| `can.c.sender` | Geçti | 64 bit, x86_64 |
| `can.c.receiver` | Geçti | 64 bit, x86_64 |
| `can.cpp.sender` | Geçti | 64 bit, x86_64 |
| `can.cpp.receiver` | Geçti | 64 bit, x86_64 |
| `serial.c` | Geçti | 64 bit, x86_64 |
| `serial.cpp` | Geçti | 64 bit, x86_64 |

Her hedefin farklı çıktı dizini var. Üç araç sürümü sorgusu ve altı Make çağrısı
`commands.jsonl` içinde kayıtlı. Binary boyut/özet/ELF bilgileri `run.json` içinde.
Bu çalışma dizini Git checkout'u olmadığı için gerçek Git commit alanı `null`;
referans commit ve içerik eşleşmesi ayrı alanlarda tutuldu.

## Beş regresyon kontrolü

| Kontrol | Gözlenen sonuç |
| --- | --- |
| Kaynak metni değişir, mtime eski tutulur | Yeni binary yeni metni yazdı; kaynak özeti değişti; yerel fixture Git dirty oldu |
| Başarılı derlemeden sonra `#error` eklenir | Eski binary korunmasına rağmen yeni run başarısız oldu; yeni başarısız hedef binary'si yoktu; sağlıklı seri hedefi geçti |
| Olmayan C derleyicisi seçilir | `error`; CLI çıkış kodu 2; başarılı binary kaydı yok |
| C++ header silinir | Make çağrılmadan eksik dosya raporlandı |
| Boş/bilinmeyen/yinelenen hedef seçilir | Seçim reddedildi |

Regresyonlar ayrı geçici kaynak kopyalarında çalıştı. `upstream/examples`
değişmedi. Yerel fixture commit'leri upstream commit'leri değildir. Kasıtlı
`failed`/`error` raporları beklenen hata deneylerinin kanıtıdır; ana altı hedeflik
kabul derlemesinin başarısız olduğu anlamına gelmez.

## WP-02 temiz paket kontrolü

Oluşturulan ZIP ayrı ve boş bir klasöre açıldı. Bu kopyanın varsayılan kaynak
seçimiyle altı hedef yeniden derlendi; beş regresyon kontrolü de tekrar geçti.
Sınanan 32 kod/kaynak/iş akışı dosyası asıl çalışma ağacıyla içerik olarak eşleşti.
Kanıtlar `artifacts/wp02-clean-room/` altında bulunur.

## Önceki I/O kanıtları

WP-01'de C seri uygulaması PTY üzerinde iki yönde doğru baytları aktardı ve
`Ctrl+C` ile 0 koduyla kapandı. Ayrı x86 Linux konuğunda bağımsız C CAN alıcısı:

- ID `0x123`, DLC 8, `4d53475f30303000` ilk çerçevesini;
- SIGINT sonrası ID `0x124`, DLC 3, `454e44` kapanış çerçevesini doğruladı.

Bu eski günlükler pakette korunur; WP-02'de altı programın bütün protokol
senaryoları yeniden çalıştırılmış gibi sunulmaz. Ayrıntılar:
[WP01_RESULTS.md](WP01_RESULTS.md).

## WP-03 süreç kanıtları

WP-03 teslimindeki kontrol: **22 test, 22 başarı**. Bunun 5'i derleme regresyonu, 17'si süreç
kontrolüdür. ResourceWarning hata sayılarak çalıştırıldı. Bu kontrol takımının
ürettiği 49 `process.json` kaydında temizlik hatası, kalan grup veya açık sahipli
pipe kaydı yok. İki senaryoda yetim kalan alt süreçler `waitpid` ile toplandı.

Gerçek C seri uygulaması yeni modülle `RX\0DATA\n` ve `TX\0DATA\n` verilerini
iki yönde aynen aktardı; Ctrl+C sonrası 0 ile kapandı. PTY fd'leri fixture'a
bırakıldı; nonblocking bayrakları geri alındı.

Altı C/C++ hedef ortak modülle yeniden derlendi. Son run kimliği:
`20261017T222133-c37c1fa8`. Make/sürüm çağrılarının kendi süreç kayıtları
`artifacts/wp03-build-validation/` altında bulunur. Beklenen timeout/çıkış/hata
senaryolarının `failed`/`error` süreç kayıtları kontrol takımının başarısızlığı
değildir; bu hataların görünür kaldığının kanıtıdır.

Ayrıntılı API, sahiplik ve kapsam: [WP03_PROCESS.md](WP03_PROCESS.md).

WP-03 ZIP'i ayrı ve boş bir klasöre açılarak yeniden doğrulandı: altı hedef ve
22 host kontrolü orada da geçti. Temiz kopyadaki 49 süreç kaydında da kalan grup
veya temizlik hatası yok. Sınanan 35 kod/kaynak/iş akışı dosyası asıl dosyalarla
eşleşti. Kanıtlar `artifacts/wp03-clean-room/` altında korunur.

## WP-04 CAN ve sahiplik kanıtları

`pytest` host takımında 5 derleme regresyonu, 17 süreç kontrolü ve 6 CAN
sözleşme kontrolü olmak üzere **28/28 test geçti**. ResourceWarning hata
sayıldı. Altı C/C++ hedef de yeniden derlendi; son derleme run kimliği
`20261017T224432-d9853a27`.

Host CAN soketi açmaya `EPERM` verdiği ve etkin yetki kümesi boş olduğu için
entegrasyon testleri QEMU TCG ile ayrı Linux çekirdeğinde çalıştırıldı.
pytest ve C/C++/Python göndericileri **UID 1000** ile çalıştı; hedeflerin procfs
üzerindeki dört UID alanı ayrı ayrı kontrol edildi. Arayüz işlemleri için
yalnızca `ip` komutlarına sudo verildi. Bu, x86_64 Linux SocketCAN/vcan
doğrulamasıdır; O1, AM67A veya R5 emülasyonu değildir.

| Gönderici | İlk ID | Uzunluk | Bağımsız alıcının gördüğü veri |
| --- | --- | --- | --- |
| C | `0x123` | 8 | `4d53475f30303000` |
| C++ | `0x123` | 8 | `4d53475f30303000` |
| Python | `0x123` | 7 | `4d53475f303030` |

Üç varyantın tamamı SIGINT ardından ID `0x124`, uzunluk 3, veri `454e44`
(`END`) gönderip 0 ile kapandı. Python'un yedi baytlık mesajı, C/C++'ın
sondaki NUL içeren sekiz baytlık mesajından ayrı sözleşme beklentisi olarak
korundu. Upstream kodu değiştirilmedi.

Üç ek kaynak testi, senaryo istisnasından sonra temizliği, mevcut arayüzün
benimsenmemesini ve sahiplik işareti değişince silmenin reddedilmesini
doğruladı. Son test kendi değiştirdiği işareti geri yükleyip kendi kaynağını
sildi; ilk silme reddi kayıtta korundu. Toplam **6 test, 6 sahipli arayüz,
6 silme, 0 kalan arayüz**. Konukta üretilen 64 süreç kaydının tamamında
süreç grubu toplandı ve temizlik hatası yoktu. Beklenen sahiplik hatası olan
`lease.json`, takımın başarısız olduğu anlamına gelmez.

Ayrıntılar ve yeniden çalıştırma komutları: [WP04_CAN.md](WP04_CAN.md).
`case.json` gerçek çerçeveleri ve UID'leri; `lease.json` sahipliği;
`process.json` süreç yaşam döngüsünü; `junit.xml` test sonuçlarını içerir.
Python 3.12 profilindeki beş pytest bağımlılığı sürüm ve SHA-256 ile kilitlendi.

WP-04 ZIP'i de yeni ve boş bir klasöre açılarak doğrulandı: **altı native
derleme, 28 host kontrolü ve 6 gerçek vcan testi yeniden geçti**. Bu kopyadaki
49 host süreç kaydı ve 64 konuk süreç kaydında temizlik tamamlandı; 6 sahipli
arayüzün tamamı silindi. Sınanan 49 kod/kaynak/iş akışı/kilit dosyası asıl
çalışma ağacıyla aynıydı. Son konuk Linux 6.8.0-138-generic, x86_64 ve
Python 3.12 ile çalıştı. Kanıtlar `artifacts/wp04-clean-room/` altındadır.

## WP-05 — alıcılar, hata matrisi ve gerçek kaynak düzeltmesi

Host takımında **37 kontrol geçti**: 5 derleme, 17 süreç, 6 önceki CAN
sözleşmesi, 8 alıcı sözleşmesi ve 1 geç hazır olma regresyonu. Son regresyon gerçek
süreç/PTY kullanır; yayıncısı simüledir. SocketCAN kabulü ayrı konuk takımındadır.
ResourceWarning hata sayıldı. Altı özgün C/C++ hedef yeniden derlendi:
`20261018T010006-eca9ef14`. Kaynak kilidi artık **24 özgün dosyadır**; iki Python
alıcı dosyası aynı commit'ten Git blob ve SHA-256 kontrolüyle eklendi.

Özgün C göndericisinde `SIOCGIFINDEX` dönüş kodu kontrol edilmiyor. Gerçek konuk
çalışmasında olmayan arayüz için indeks 0 kullanıldı, mesaj gönderilmeye çalışıldı
ve ancak gönderimde hata alındı. Son regresyon testi bunu **indeks kullanılmadan
reddetme** koşuluyla yakalıyor. Seçilmiş özgün sürüm çalışmasının JUnit sonucu
1 test, 1 başarısızlıktır; xfail/skip veya yeşil sonuca çevrilmedi.

`patches/0001-can-c-sender-check-interface-index.patch` hata kontrolünü ve soket
temizliğini ekler. `prepare_can_fix.py`, yamayı özel bir kopyaya uyguladı; yalnızca
bir dosya değişti ve özgün 24 girdi korundu. Yama uygulama kanıtı
`artifacts/wp05-fix-preparation/` içindedir. Gerekçe ve İngilizce PR taslağı:
[WP05_UPSTREAM_ISSUE.md](WP05_UPSTREAM_ISSUE.md).

Matris 3 gönderici, 18 alıcı, 12 argüman ve 3 kaynak testi içerir. Alıcılar 0/1/8
baytı, NUL/yüksek baytları ve END koşulunu bağımsız yayıncıyla sınar. Yanlış ID'de
END, kısa EN ve farklı ENX kapanış üretmemeli; her birinden sonra farklı normal
çerçevenin işlendiği görülmelidir. END önekli uzun mesaj geçerli kapanıştır.

İlk 240 saniyelik VM denemesi kanıt aktarımına ulaşamadı. Sonraki keşif takımında
33/36 test geçti: bir özgün kaynak kusuru ve iki Python hazırlık zaman aşımı
kaydedildi. Yama uygulanmış ilk native bütçeli TCG denemesinde 35/36 geçti;
bir Python başlangıcı 3 saniyeyi aştı. Bunlar `wp05-vcan-final/` ve
`wp05-vcan-fixed/` altında başarısız olarak korunur. Kaynak kusuru ile test
altyapısının zamanlama sorunları aynı hata olarak sunulmaz.

Hazırlık denemelerinin süre dolmadan tükenmesi düzeltildi. Başlayan çerçeve
satırında tekrarlar durduruldu. Native bütçeler 5/3/3 saniyedir; TCG profilinde
açıkça kaydedilen 4 çarpanı 20/12/12 kullanır. Kimlik, veri, çıkış ve temizlik
beklentileri değişmedi. Bu testler performans veya gerçek zamanlılık ölçümü değildir.

Önerilen yamanın kopyasında **36/36 vcan testi geçti**. 33 uygulama vakasının
hedef UID'leri `[1000,1000,1000,1000]` olarak doğrulandı. Üç kaynak vakası dahil
24 sahipli arayüzün tamamı kaldırıldı; kalan `gtl` arayüzü yoktu. 256 süreç kaydının
tamamında grup, lider ve sahipli pipe temizliği tamamlandı. Bu sonuç TCG x86_64
Linux/Python 3.12 ve süre çarpanı 4 profiline aittir. Özgün sürüm için 36/36
başarı iddia edilmez. Kanıt: `artifacts/wp05-vcan-acceptance/`.

Kontrollü deney ayrıca özel bir C alıcı kopyasının yazdırdığı DLC'yi bozdu.
Gerçek vcan testi `Receiver DLC does not match its hex output` hatasıyla
başarısız oldu. Tek arayüz ve 10 süreç temizlendi; özgün alıcı değişmedi.
Bu yapay bozulma upstream kusuru değildir. Gerçek başarısız JUnit korunur.
Yeniden çalıştırma ve matris ayrıntıları: [WP05_CAN_MATRIX.md](WP05_CAN_MATRIX.md).

WP-05 ZIP'i yeni ve boş bir dizine açılarak tekrar doğrulandı: **6 native
derleme, 37 host testi ve önerilen yama kopyasında 36 vcan testi yeniden geçti**.
59 kod/kaynak/iş akışı/yama/kilit dosyası asıl dosyalarla eşleşti. Temiz kopyada
50 host süreç kaydı ve 256 konuk süreç kaydı temizlendi; 24 sahipli arayüzün
hepsi kaldırıldı. Aynı kopyadan kontrollü DLC bozulması deneyi de tekrarlandı;
bir gerçek pytest başarısızlığı, kaynak temizliği ve özgün dosyanın değişmediği
doğrulandı. Kanıt: `artifacts/wp05-clean-room/package-check.json` ve alt dizinler.

## WP-06 seri port kanıtları

Üç dilde konsol ve cihaz için ayrı gerçek PTY'ler kullanıldı. Özgün sürümde
**45 testten 34'ü geçti, 11'i başarısız oldu; hata veya skip yoktu**. C/C++ CR
baytlarını LF'ye dönüştürdü (4 vaka); `9600oops` değerini kabul etti (2 vaka).
Python toplu konsol verisinde takıldı (3 vaka); yardımda 1 kodu döndürdü (2 vaka).
Gerçek başarısız JUnit, hex veri, kısmi çıktılar ve temizlik kayıtları korunur.

Dört ayrı önerilen yama, `prepare_serial_fixes.py` ile yeni bir kaynak kopyasına
uygulandı. Beş seri kaynak dosyası değişti; 27 paketlenmiş özgün dosya aynı kaldı.
**45/45 seri testi geçti.** Alış/veriş metin ve ikili veriyi, CR/LF'yi, farklı
parça boyutlarını ve 257 baytlık parçayı içerir. Hazır olma, tek gönderilmiş
benzersiz cihaz verisinin konsolda görülmesiyle doğrulandı. Normal veri tekrar
edilmedi veya normalleştirilmedi. Konsoldaki `0x03`, uygulamayı 0 ile kapattı;
termios, fixture düzeltmesinden önce eski değerleriyle eşleşti.

50 süreç kaydının tümünde grup, lider, pipe ve selector temizliği tamamlandı.
Bunların üçü kontrollü senaryo istisnası için bilerek `failed` olarak kayıtlıdır;
üç pytest vakası kaynak temizliğini doğrulayarak geçer. 21 oturumun PTY'leri
kapandı; argüman kontrolleriyle birlikte toplam 54 PTY çifti yönetildi.
Bağımsız fd korundu ve kaynak-hata testlerinde açık fd kümesi eski haline döndü.

Kontrollü negatif deney, özel C kopyasının ilk TX baytını çevirdi. Gerçek PTY
senaryosu beklenen `Gemstone` yerine `Femstone` gördü ve `tx byte mismatch` ile
başarısız oldu. Deney, tam bir pytest başarısızlığı ve temizliği doğrulayınca
başarılı sayıldı; özgün kaynaklar değişmedi. Bu yapay bozulma upstream kusuru değildir.

Aynı aşamada **37 host kontrolü ve altı özgün C/C++ derlemesi yeniden geçti**.
Önceki CAN kodları değişmedi; WP-05'in 36 gerçek vcan testi bu aşamada tekrar
çalıştırılmadı. Native PTY çalışmasının UID/capability, Python/pytest/pyserial,
komut, kaynak ve harness hash'leri `serial-programs.json` içinde bulunur.
Bu ortamda UID 0 ve etkin/sınır capability kümeleri sıfırdı; ağ yetkisi gerekmedi.

Temiz ZIP kopyasından altı derleme, 37 host ve yama kopyasında 45 seri testi ile
kontrollü TX bozulması da tekrarlandı. Paket kimliği ve temizlik sayıları
`artifacts/wp06-clean-room/package-check.json` içinde kayıtlıdır.

Matris, yeniden çalıştırma ve sınırlar: [WP06_SERIAL.md](WP06_SERIAL.md).
Dört ayrı katkı taslağı: [WP06_UPSTREAM_ISSUES.md](WP06_UPSTREAM_ISSUES.md).

## WP-07 ortak rapor ve yeniden üretim kanıtları

Yeni pytest eklentisi `setup/call/teardown` fazlarını, sonuçları, parametreleri,
uygulama kaynak snapshot'ını ve kanıt hash'lerini ortak JSON sürüm 1'e aktarır.
JUnit'i pytest üretir. Kurulum veya temizlik hatası `error`; uygulama assertion'ı
ve süre sınırı `failed`; yalnızca koleksiyon `not_run` olarak görünür.
Zorunlu skip ve çalışma sırasında girdi değişimi çalışma hatasıdır; ham pytest
kodu ve etkin kod birlikte korunur. Boş koleksiyon 5, yanlış seçim 4 döndürür.

Dokuz yeni raporlama kontrolüyle **46 host testi geçti**. Kontroller gerçek alt
pytest ve CLI süreçlerini çalıştırır; kaynak/harness/selector değişikliğinin
reddini, tek vaka seçimini, faz önceliğini ve keyfî rapor argv'sinin çalıştırılmamasını
kanıtlar. Eski 37 kontrolün beklentileri değiştirilmedi.

Önerilen seri yamalarının kopyasında **45 test**, CAN yamasının kopyasında
**36 gerçek vcan testi yeniden geçti**. Bu aşamada vcan takımı yeniden çalıştırıldı.
Normal kullanıcı UID 1000 doğrulandı; 24 arayüz kaldırıldı ve 256 süreç kaydı
lider/grup/pipe temizliğini tamamladı. Ortak CAN `run.json` 36 başarı ve 256 komut
kaydı içerir. Seri kabulündeki 50 süreç ve 21 oturumun kaynakları temizlendi.
Kasıtlı HARNESS istisnaları normal uygulama başarısı gibi gösterilmez.

Üç özgün seri vakası seçildi: C CR/LF bozulması, Python yardım kodu, Python toplu
konsol aktarımı zaman aşımı. **Üçü de gerçekten başarısız oldu.** Rapor dizini
başka yere taşınıp eski adres erişilemez yapıldı. Kayıtlı kaynak snapshot'larından
üç vaka aynı node ve aynı sonuçla yeniden çalıştı. Dördüncü deneyde, özel C
kopyasındaki kasıtlı TX bayt bozulması da eski kaynak dizini erişilemezken yeniden
görüldü. Her tekrar gerçek pytest kodu 1'i döndürdü; deneyin doğrulanması ile
uygulamanın test sonucu ayrı tutuldu. Özgün dosya özetleri değişmedi.

CAN C göndericisinin özgün olmayan-arayüz kusuru da yeni ortak failure.json
üzerinden, `reproduce --backend can-vm` komutuyla yeniden görüldü. Guest aynı
node'u ve kayıtlı çarpan 4'ü kullandı; pytest/target UID 1000'di. Sonuç gerçek
başarısızlık ve kod 1 olarak kaldı. Rapor girdileri, kaynak snapshot'ı ve yeni
ortam kaydı host'a taşındı.

Güncel ZIP boş dizine açıldı. Altı özgün native derleme, 46 host ve seri yama
kopyasında 45 test yeniden geçti. Paket içindeki bir seri hata raporu farklı
klasöre taşınıp temiz proje koduyla tekrar çalıştırıldı; aynı başarısızlık görüldü.
Doğrulama ve dosya sayıları `artifacts/wp07-clean-room/package-check.json` içindedir.
CAN'in uzun tam takımı temiz kopyada ikinci kez çalıştırılmadı; ilgili kaynak,
fixture ve rapor kodlarının byte eşleşmesi kontrol edildi.

Şema, komutlar ve kapsam: [WP07_REPORTING.md](WP07_REPORTING.md).

## WP-08 doğrulanan SDK ve AArch64 derleme

Resmî Gemstone SDK v1.0.6'nın Ubuntu Jammy minimal arşivi kullanıldı. Resmî
yayın kaydındaki **298.905.352 bayt** ve
`cd53ee3604329f75ac3fbd476467738d738a3ce92c0c91df9d6d9414f4d09a23`
SHA-256 değeri eşleşti. Kurulu 9.712 dosya/bağlantı da arşivden türetilmiş
sabit ağaç özetiyle doğrulandı. Sysroot içindeki iki mutlak SSL bağlantısı,
hedef kökün SDK içinde kalacağı göreli bağlantılara dönüştürüldü; içerikler
değiştirilmedi. Dönüşüm kilitte ve makbuzda açıktır.

**Altı özgün C/C++ hedefi**, SDK'nın GCC/G++ 11.2.1 derleyicileri ve Jammy
sysroot'u ile kendi Makefile'larından derlendi. Uyarı bayrakları korundu.
Tüm çıktılar ELF64, little-endian, `e_machine=183` ve
`/lib/ld-linux-aarch64.so.1` yükleyicisine sahip. `readelf -h -l -d -V` ile
bağımlı kütüphaneler ve gereken GLIBC/GLIBCXX/CXXABI sürümleri kaydedildi.
İlk altı hedef kabulünde 23 yönetilen süreç ve altı ayrı readelf günlüğü var.

Gerçek SDK ile dört ek deney geçti: dış ortamdaki bozuk derleyici/bayrak
değerlerine rağmen altı hedef derlendi; ayrı kaynak kopyasındaki gerçek
`#error` CLI 1 ile reddedildi ve eski binary kullanılmadı; boşluk içeren
başka SDK yolundan C ve C++ hedefi derlendi; özel SDK kopyasının `env`
dosyasındaki değişiklik CLI 2 ile, hiçbir SDK komutu başlamadan reddedildi.
Çağıranın kaynakları ve SDK'sı değişmedi. İlk taşıma denemesindeki gerçek
LDFLAGS yol hatası `wp08-controlled-builds/` altında açıkça başarısız olarak
korunur; son kabul `wp08-controlled-final/` içindedir.

Sekiz yeni SDK/ELF/CLI kontrolüyle **54 host testi geçti**. Altı native derleme
ve önerilen seri yamalarının kopyasında **45 PTY testi** de geçti. Güncel
harness ile kontrollü seri hatasının rapordan tekrarı ve temiz ZIP kabulü
`artifacts/wp08-reproduction/` ve `artifacts/wp08-clean-room/` altında saklanır.
vcan tam takımı WP-08'de yeniden çalıştırılmadı; önceki WP-07'nin 36 gerçek
vcan testi güncel kabul gibi yeniden etiketlenmedi.

Çalışma modu `cross_build_only` kaldı. ARM64 programlar çalıştırılmadı.
Kart dosya sisteminin rapordaki sembol sürümlerini sağladığı, fiziksel UART/CAN
ve gerçek zamanlı davranış bu aşamada sınanmadı.
Kurulum, komutlar, rapor alanları ve sınırlar: [WP08_CROSS_BUILD.md](WP08_CROSS_BUILD.md).

## WP-09 ortak CI ve kabul denetimi

Yeni `ci` komutu host/seri/CAN/AArch64 profillerini yürütür. `ci-verify`
tam dört kanıt paketini, kaynak/harness/commit kimliğini, zorunlu vaka ve hedef
matrisini, JUnit/JSON uyumunu, dosya özetlerini ve son temizlik durumunu
denetler. Test seçiminin daraltılması, yalnız koleksiyon ve eksik artifact
başarılı toplam sonuç üretemez. Pytest'in gerçek kodu ile etkin CI kodu ayrı
korunur.

**66 host ve 45 seri testi**, **altı native ve altı ARM64 hedef** yeni CI
girişinden geçti. Seri kabulü açık yama kopyasına aittir. On iki yeni CI
regresyonu gerçek alt pytest süreçleriyle sıfır vaka, koleksiyon, skip ve
eksik vaka durumlarını; ayrıca kanıt, mimari, commit ve son temizlik
reddini kontrol eder. CAN/seri test modüllerinin ad çakışması paket
işaretçileriyle giderildi; 147 vaka birlikte toplanabildi.

Yeni CAN CI girişi ayrı Linux konuğunda UID 1000 ile çalıştı: **36 gerçek
vcan testi geçti, 24 sahipli arayüz kaldırıldı, arayüz kalmadı**. Derlenen
dört host hedefi kaynak/ELF/hash kontrolüyle konuğa verildi; konuk kendi
açık yama kopyasını hazırladı. 260 konuk süreç kaydı temizlendi. İlk CI
denemesi, sahiplik testinin sonradan kurtarılmış ilk ret kaydını yanlış
değerlendirdiği için kod 2 ile reddedildi. Bu başarısızlık korunur;
son kabul `artifacts/wp09-can-vm-final/` içindedir.

Gerçek, yayınlanmamış bir Git fixture'ında ilk commit ile altı ARM64 hedef
geçti. İkinci commit'te C göndericisine eklenen gerçek `#error` derlemeyi
kırdı; kaynak özeti değişti ve eski kaynak/binary kullanılmadı. Yanlış
commit beklentisi ise derleyici/pytest başlamadan kod 2 ile reddedildi.
İki yama hazırlık aracının parent Git deposunda yanlış bağlama girmesi de
bu aşamada bulunup düzeltildi; özgün 27 upstream dosyası değişmedi.

Dört gerçek profil raporu birleşik yerel kabulden geçti. Uzak koşu iddiası
`--require-hosted` ile denendiğinde, eksik profil veya bozulmuş kanıt
verildiğinde kabul reddedildi. Actions dosyası hash'i doğrulanan
**actionlint v1.7.12** ile statik denetimden geçti. ShellCheck/pyflakes bu
kontrolde çalıştırılmadı. Bu kontroller bir hosted run URL'si üretmez.

Temiz ZIP'ten host/seri/ARM64 CI girişleri tekrar çalıştırıldı; güncel konuk
CAN kanıtı taşınıp toplam denetim tekrarlandı. Ayrıntılar
`artifacts/wp09-clean-room/` ve [WP09_CI.md](WP09_CI.md) içindedir.

## WP-10 temiz kurulum ve katkı teslimi

[QUICKSTART.md](../QUICKSTART.md) ve [CONTRIBUTING.md](../CONTRIBUTING.md) eklendi.
`tools/run_release.py`, mevcut dört CI profilini tek komutla başlatıp toplam
kabulü denetler. `tools/export_source.py`, geçmiş ham kanıtlar, SDK, wheel ve
binary olmadan sade bir kaynak ZIP'i üretir. Dosya manifesti SHA-256/boyut/mode
bilgilerini taşır; ZIP aynı kaynak ve sıkıştırıcı ortamında deterministiktir.

**Gerçek temiz kurulum yapıldı:** kaynak ZIP'i `/tmp` altında yeni dizine açıldı,
yeni venv'e kilitli wheel'ler `--require-hashes` ile kuruldu ve SDK kilitli yerel
arşivden yeni dizine doğrulanarak çıkarıldı. Tek `run_release.py` çağrısıyla
**66 host, 45 seri, 36 gerçek vcan testi; altı native ve altı AArch64 hedef**
geçti. Dört profilin toplam kabulü de geçti. Test/çalıştırıcı/kaynak/workflow/yama
grubundaki 99 dosyanın temiz kopyayla birebir eşleştiği doğrulandı.
Bu aşamada CAN takımı gerçekten yeniden çalıştırıldı; eski kanıt taşınmadı.

CAN konuğu UID 1000 ile çalıştı; **24 sahipli arayüz kaldırıldı, arayüz kalmadı**.
CI kanıtlarındaki host/seri/CAN/AArch64 süreç kayıtları sırasıyla
185/73/260/23'tür; tüm sahipli süreç grupları, liderler, pipe ve selector'lar
temizlendi. QEMU süresi yaklaşık 590 saniyeydi. Bu ortamda 600 saniyelik profil
bütçesine yaklaşıldığı için kılavuzun VM örneği 1.200 saniyelik dış bütçe
önerir; tekil vakaların scale=4 süresi değiştirilmedi. Bu bir performans veya
on ardışık koşu güvenilirliği iddiası değildir.

`contributions/` altında beş İngilizce PR taslağı ve makinece okunabilir
`series.json` hazırlandı. Her yama diğerlerinden bağımsız olarak özgün kaynak
kopyasına uygulandı: 1 CAN, 4 raw RX/duplex, 2 baud, 3 Python stdin ve 2 Python
help vakası önce gerçek call başarısızlığı verdi, sonra yalnız ilgili yamayla
geçti. **12 önce/sonra regresyonunun tamamı doğrulandı.** Özgün 27 upstream
dosyası değişmedi. Hiçbir issue/PR gönderilmedi.

Exporter'ın 13 gerçek kontrolünde iki byte-eş arşiv ve sağlam doğrulama geçti;
10 bozulma/eksik/fazla/yinelenen dosya, yol, manifest, kaynak, symlink ve mevcut
çıktı durumu reddedildi. İlk kontrol denemesinde test aracının ZipInfo nesnesini
yeniden kullanması `BadZipFile` üretti; bu fixture hatası düzeltildi ve ilk
başarısız kayıt `wp10-delivery-check/` altında korundu. Son kabul
`wp10-delivery-final/` içindedir.

Teslim aracı kontrollerinde 7 olumsuz durum ve 4 kurulum komutu doğrulandı.
CAN yetkisi/SDK eksikken host ve seri geçti, kalan iki profil hata verdi ve
toplam kod 2 kaldı; sonraki profiller atlanmadı. Pytest olmayan yeni venv'deki
başarısız komut baseline regresyon kanıtı sayılmadı. Gerçek, yayınlanmamış Git
fixture'ında VM'nin checkout kimliği taşımadığı durum da başlamadan reddedildi.
Bu kontroller mock kullanmadı ve uzak depoyu değiştirmedi.

Tam kanıt: `artifacts/wp10-verification.json`. Yeni rapor türleri
`docs/delivery.schema.json` ile tanımlanır. Kaynak paketi ile tam kanıt arşivinin
kapsamı ve tekrar komutları: [WP10_DELIVERY.md](WP10_DELIVERY.md).

## Gerçek GitHub Actions kabulü

Proje `SerhatAnkt/gemstone-testlab` deposuna aktarıldı. İlk koşuda CAN modülü
eksikliği ve artifact yüklemesinin gizli doğrulama dosyasını atlaması bulundu.
Çalışan çekirdeğe uygun modül kurulumu ve altı kanıt yüklemesinde gizli
dosyaların korunması eklenince [koşu #2](https://github.com/SerhatAnkt/gemstone-testlab/actions/runs/39155570890)
beş işi başarıyla tamamladı. **66 host, 45 seri, 36 gerçek vcan testi ve
altı AArch64 çapraz derleme geçti; 24 sahipli arayüz kaldırıldı.**

Altı artifact'in ZIP SHA-256 değeri doğrulandı. Dört profilin dosya özetleri,
matrisleri, JSON/JUnit sonuçları ve temizlik kayıtları yerelde yeniden
denetlendi; hosted kabul tekrar geçti. Gerçek commit, job kimlikleri ve
artifact özetleri `docs/ci-runs/39155570890.json` içindedir. İlk başarısız
koşu da ayrı kaydedildi. Fiziksel kart ve ARM64 hedefte çalışma yapılmadı.

## Açık işler

- İlk mimari plandaki on ardışık tam koşu hedefi bu teslimde tamamlanmadı.
- CAN çapraz dil eşleşmeleri ve daha geniş dayanıklılık senaryoları sonraki kapsamda.
- O1 kartında çalışma yapılmadı.

Güncel CI iş akışında `host-checks` altı derleme ve 66 host kontrolünü;
`linux-integration` önerilen yamanın özel kopyasında 36 pytest/vcan senaryosunu
çalıştırır. Yeni `serial-integration` işi önerilen dört seri yamasıyla 45 PTY
senaryosu ve kontrollü bayt bozulmasını çalıştırır. Yama hazırlığı ve kaynak
özetleri de saklanır. `aarch64-cross-build` işi doğrulanan SDK ile altı hedefi
derler ve ELF/readelf kanıtlarını saklar. Beşinci `acceptance` işi hepsinin
kanıtlarını karşılaştırır. Bu gereksinimler yukarıdaki gerçek hosted koşuda
JUnit ve `lease.json` kayıtlarıyla karşılandı. Hazır YAML dosyasından ayrı
olarak gerçek koşu ve indirilen kanıtlar incelendi. Önceki WP-01 PTY kanıtları yerel kayıtlarda korunur.
