# WP-06 — iki PTY ile seri terminal sözleşmesi

18 Ekim 2026. Sözleşme: `serial_terminal_v1`. Referans kaynak:
`t3gemstone/examples@2619a7584d39203a057abc08ab7c6698dc476868`.

## Sonuç ve kapsam

| Profil | Gerçek sonuç | Kanıt |
| --- | --- | --- |
| Özgün C/C++/Python | **34 geçti, 11 başarısız, 0 hata, 0 skip** | `artifacts/wp06-baseline-final/` |
| Dört önerilen seri yamasının özel kopyası | **45/45 geçti** | `artifacts/wp06-acceptance/` |
| Önceki host kontrolleri | **37/37 geçti** | `artifacts/wp06-host/` |
| Altı özgün C/C++ hedefin native derlemesi | **6/6 geçti** | `artifacts/wp06-builds/` |
| Özel kopyada kasıtlı TX bayt bozulması | **Gerçek test reddetti; pytest kodu 1** | `artifacts/wp06-controlled-failure/` |

Linux x86_64, Python 3.12, GCC/G++ 13.3 ve gerçek Linux PTY'leri kullanıldı.
Native süre çarpanı 1'dir. Bu çalışma ortamında runner UID 0, etkin ve sınır
capability kümeleri sıfırdır; testler root veya ağ yönetimi yetkisi istemez.
GitHub normal runner kullanıcısındaki iş henüz çalıştırılmadı.

WP-05'in **36 vcan testi önceki teslimin kanıtıdır**. Bu pakette CAN süreç,
sözleşme ve fixture kodları değiştirilmedi; uzun konuk takımı tekrar çalıştırılmadı.
37 host kontrolü CAN sözleşmesi regresyonlarını da içerir.

## Bağlantı ve sahiplik

Her oturum iki `pty.openpty()` çağrısı yapar; toplam dört fd fixture'a aittir.

| Uç | Uygulamanın bağlantısı | Bağımsız testin bağlantısı |
| --- | --- | --- |
| Seri cihaz | `--device /dev/pts/...` ile cihaz slave'ini kendisi açar | Cihaz master'ından yazar ve okur |
| Konsol | Ayrı konsol slave'i stdin ve stdout olur | Konsol master'ından yazar ve okur |
| Hata çıktısı | Ayrı stderr pipe'ı | Süreç yöneticisi ham olarak kaydeder |

Cihaz ve konsol birbirinden ayrıdır. Test verisini başka bir Gemstone terminali
üretmez; beklenen baytlar testte bağımsız tanımlanır. Dolayısıyla iki hatalı
uygulamanın birbiriyle anlaşması başarı ölçütü değildir.

Fixture cihazı önceden raw moda almaz. Yeni PTY'nin varsayılan ayarları kaydedilir;
raw ayarını uygulama yapar. Bu ayrım CR→LF hatasını görünür kılmıştır. Cihazı test
başında raw yapmak, uygulamanın eksik `termios` ayarını gizleyebilirdi.

Konsolun da PTY olması gerekir: üç uygulama stdin üzerinde terminal ayarlarını
okur ve değiştirir. Düz pipe, bu etkileşimli terminal önkoşulunu karşılamaz.

## Hazır olma ve veri doğrulama

1. Süreç ayrı oturum/grupta başlatılır. Süreç yöneticisi iki master'ı ve stderr'i
   birlikte izler; stdout pipe'ı yerine konsol PTY'si kullanılır.
2. Cihaz ve konsolda `ECHO`, `ICANON`, `ISIG` bayraklarının kapatıldığı gözlenir.
   Bu gözlem tek başına hazır olma başarısı değildir.
3. Bağımsız cihaz ucundan benzersiz, ASCII bir nonce **bir kez** gönderilir.
   Aynı baytların konsoldan alınması gerekir. Başlangıç metni ayrı kaydedilir.
4. Asıl test verisi yalnızca bir kez yazılır. Tam uzunluğu okunur ve ham `bytes`
   olarak karşılaştırılır; CR/LF, NUL veya yüksek bayt normalleştirilmez.
5. Parçalı senaryoda her parçanın aktarımı görülünce sonraki parça gönderilir.
   Sabit uyku veya veri tekrarına dayalı bir geçme koşulu yoktur.
6. Kapanış için konsol master'ına gerçek `0x03` yazılır. Başarılı normal senaryoda
   SIGINT/SIGTERM gönderilmez. Çıkış kodu 0, konsol ayarlarının geri yüklenmesi ve
   süreç grubunun toplanması doğrulanır.

Başlangıç ve Python kapanış metinleri veri değildir. Veri karşılaştırması bunları
ayırır. Seri tarafta beklenmedik ek bayt, konsolda beklenmedik son çıktı ve stderr
de normal senaryoyu başarısız yapar. Konsola normal veri olarak `0x03` verilmez;
bu bayt uygulamanın tanımlı kapanış komutudur.

## Test matrisi: 45 vaka

Her satır C, C++ ve Python üzerinde parametriktir.

| Kimlik | Kontrol | Vaka |
| --- | --- | ---: |
| SER-RX-01 | Seri → konsol: ASCII ve NUL/DEL/yüksek bayt/CR/LF | 6 |
| SER-TX-01 | Konsol → seri: tek yazımda metin ve ikili veri | 6 |
| SER-IO-01 | İki yönde dönüşümlü 5 parça; 1 bayt ve 257 bayt parçalar dahil | 3 |
| SER-ARG-01 | `0`, `garbage`, desteklenmeyen `12345`, kısmi sayı `9600oops` | 12 |
| SER-ARG-02 ve ek eksik-argüman kontrolü | Olmayan cihaz; cihaz/baud parametreleri eksik | 6 |
| SER-LIFE-01 | Konsol Ctrl+C, 0 kodu, termios geri yükleme, toplanmış grup | 3 |
| CLI-HELP-01, P1 | `-h` ve `--help`: yardım metni ve 0 kodu | 6 |
| HARNESS-02-serial | Oturum ortasında kasıtlı istisna; sahipli kaynaklar kapanır | 3 |
| **Toplam** | | **45** |

257 baytlık parça C/C++ örneklerinin 255 baytlık okuma sınırını aşar. Parça
sınırları protokol paketi sınırı sayılmaz; çıktıdaki bayt sırası ve içeriği ölçülür.
Bu matris tüm olası yük boyutları, kodlamalar veya kablo hata biçimleri değildir.

Normal faz bütçeleri hazır olma 5, senaryo toplamı 10, Ctrl+C kapanışı 3, ortak
temizlik 2 saniyedir. Zorunlu temizliğin SIGTERM aşaması ayrıca en çok 1 saniyedir.
`--timeout-scale` açık, sonlu ve pozitif bir çarpandır; varsayılan 1'dir. Bu süreler
testin takılmasını sınırlar, fiziksel seri gecikmesi veya gerçek zaman garantisi vermez.

45 vakada 21 uygulama oturumu ve 12 argüman kontrolü toplam **54 PTY çifti** açar.
Oturumlara ait dört fd, argüman kontrollerine ait iki fd ve ödünç master bayrakları
kapama yolunda ele alınır. Slave fd'leri, uygulama çıktıktan sonra konsolun eski
ayarına dönüp dönmediğini gözlemek için fixture tarafından açık tutulur.

Kasıtlı istisna kontrollerinde normal Ctrl+C beklenmez: süreç kaydı `failed` ve
`context_exception` olarak korunur; pytest kaynak temizliği beklentisini sınar.
Üç böyle süreç dahil **50 süreç kaydının tümünde** lider/grup ve sahipli pipe/selector
temizliği tamamlandı. 47 kayıt başarılı, üç kayıt bu kasıtlı istisnalardır.
Bağımsız dosya tanıtıcısı yazılabilir kaldı; `/proc/self/fd` kümesi eski haline döndü.
Süreç kapandıktan sonra fixture kendi PTY ayarlarını da geri yükleyip fd'leri kapatır.
Normal Ctrl+C testindeki uygulama geri yüklemesi, bu fixture düzeltmesinden **önce** ölçülür.

## Çalıştırma

Paketin kökünde Linux, Python 3.12, GCC/G++, GNU Make ve Git gerekir. Ağ yetkisi,
`socat`, seri donanım veya kart gerekmez. Bağımlılıklar hash ile sabittir:

```sh
python3 -m venv .venv-testlab
.venv-testlab/bin/python -m pip install --require-hashes -r tests/requirements-serial.txt
```

Özgün kaynakların kusurlarını yeniden üretir; beklenen gerçek sonuç **11 başarısızlıktır**:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 TESTLAB_PYTHON=.venv-testlab/bin/python sh tests/scripts/run-serial-tests.sh --evidence-root artifacts/serial-original --junitxml=artifacts/serial-original.xml -q
```

Önerilen düzeltmeleri yeni bir dizine uygular ve bu kopyayı sınar:

```sh
python3 tools/prepare_serial_fixes.py --output build/serial-fixed
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 TESTLAB_PYTHON=.venv-testlab/bin/python sh tests/scripts/run-serial-tests.sh --source-root build/serial-fixed --evidence-root artifacts/serial-fixed --junitxml=artifacts/serial-fixed.xml -q
```

Hazırlama aracı mevcut çıktı dizinini kullanmaz, özgün ağacı değiştirmez.
`git apply --check` ve `git apply` komutları, dört yamanın hash'i, 27 dosyanın
önce/sonra özetleri `testlab-serial-fixes.json` ve `testlab-serial-fix-evidence/`
altındadır. Beklenen değişiklik yalnızca beş seri kaynak dosyasıdır.
CAN göndericisinin WP-05 yaması bu seri kopyasına kendiliğinden uygulanmaz.

Tek vaka örneği:

```sh
.venv-testlab/bin/python -m pytest 'tests/serial/test_terminal.py::test_serial_receive[binary-crlf-c]' --source-root build/serial-fixed -q
```

Kontrollü bozulmanın gerçek test tarafından yakalanması:

```sh
.venv-testlab/bin/python tools/check_serial_mutation.py --source-root build/serial-fixed --output artifacts/serial-corruption
```

Bu deney C'nin ilk TX baytını yalnızca özel kopyada değiştirir. Testte `Gemstone`
yerine `Femstone` alınır; assertion `tx byte mismatch` olur. Deney komutunun 0
ile bitmesi, beklenen **bir gerçek pytest başarısızlığının** ve tam temizliğin
doğrulandığı anlamındadır. Başarısız JUnit ve `change.patch` korunur; hata upstream
kusuru olarak sunulmaz. Asıl kaynak hash'leri değişmemelidir.

## Kanıtlar ve sınırlar

`serial-programs.json`: kullanılan kaynak kökü, native build raporu, Python kaynak
hash'leri, harness hash'leri, Python/pytest/pyserial sürümü, UID/capability bilgileri,
komut ve referans kaynak farkları. `case.json`: senaryo, varyant ve sonuç.
`terminal/events.jsonl`: gönderilen ve alınan gerçek hex baytlar.
`terminal/serial.json`: oturum ve PTY temizliği; `process.json`: çıkış ve grup toplama.
`failure.json` ve JUnit gerçek başarısızlığı korur. Ortak, taşınabilir hata yeniden
üretim arayüzü WP-07'nin işidir; bu aşamada pytest node seçimi kullanılabilir.

`pyserial==3.5`, yalnızca Python seri uygulamasının bağımlılığıdır. CAN ve host
gereksinimleri `requirements.txt` içinde kaldı; seri için ek dosya bunu içerir.
Wheel SHA-256 ve resmî PyPI URL'si `serial-dependencies.lock.json` içindedir.
Python seri örneğine ait üç yeni dosya upstream içerikleriyle paketlendi; güncel kaynak kilidi
27 dosyadır. Önceki 24 dosyalık kilit `docs/wp05-source.lock.json` olarak korunur.

PTY, fiziksel UART hızını, parity/framing hatalarını, elektriksel seviyeyi, DMA'yı,
gerçek cihaz çıkarılmasını veya O1 sürücülerini doğrulamaz. `115200` argümanı
seçilir; bit hızı ölçülmez. ARM64 derleme/çalışma, R5 ve O1 donanım testleri yapılmadı.
GitHub Actions seri işi hazırdır; uzaktaki başarı sonucu henüz yoktur.

Bulunan kusurlar ve ayrı katkı taslakları: [WP06_UPSTREAM_ISSUES.md](WP06_UPSTREAM_ISSUES.md).
