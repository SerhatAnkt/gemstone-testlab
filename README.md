# Gemstone TestLab

**Yeni geliştirici için başlangıç:** [QUICKSTART.md](QUICKSTART.md).
**WP-10 yerel teslimi geçti:** temiz kaynak ZIP'i, yeni venv ve doğrulanmış SDK
üzerinden tek komutla **66 host, 45 seri, 36 gerçek vcan ve altı AArch64 hedef**
doğrulandı. Beş yamanın bağımsız önce/sonra kontrolünde 12 regresyon düzeldi.
Temiz kurulumdan sonra `tools/run_release.py` dört zorunlu profili tek komutla
başlatır. `tools/export_source.py` geçmiş kanıtlar ve SDK olmadan sade kaynak
ZIP'i üretir. Beş bağımsız düzeltme, İngilizce PR taslakları ve önce/sonra
kontrolü [CONTRIBUTING.md](CONTRIBUTING.md) altında hazırlanmıştır.
WP-10 teslim tasarımı: [WP10_DELIVERY.md](docs/WP10_DELIVERY.md).
**Uzak CI ve yayın durumu:** [RELEASE_READINESS.md](docs/RELEASE_READINESS.md).

Gemstone'un Linux kullanıcı alanı örneklerini kart olmadan derlemek ve sınamak
için geliştirilen açık kaynak test altyapısı. Mevcut teslim WP-01'in teknik
deneylerini, WP-02'nin derleme yöneticisini, WP-03'ün süreç yönetimini ve WP-04'ün
pytest/vcan fixture'larıyla CAN sözleşmesini içerir. WP-05, üç dilde CAN alıcıları
ve altı giriş noktası için hata senaryolarını; WP-06, C/C++/Python seri terminal
uygulamalarını gerçek Linux PTY'leriyle sınayan 45 vakayı ekler.

**WP-09 CI altyapısı hazır; yerel kabul geçti:** ortak `ci` komutu, dört
profilin kanıtlarını denetleyen `ci-verify` ve beş Actions işi eklendi.
**66 host, 45 seri, 36 gerçek vcan testi ve altı ARM64 hedef** geçti.
Seri/CAN sonuçları açıkça seçilen yama kopyalarına aittir. Gerçek commit
değişimi ve yanlış checkout denemeleri de doğrulandı. **Uzak GitHub kabulü
açık:** proje deposu [SerhatAnkt/gemstone-testlab](https://github.com/SerhatAnkt/gemstone-testlab) olarak oluşturuldu; ilk hosted kabul henüz doğrulanmadı.

**WP-08 tamamlandı:** resmî Gemstone SDK v1.0.6 arşivinin boyut/SHA-256 kilidi,
doğrulanan sysroot ve ayrı `aarch64` derleme profili eklendi. Altı özgün C/C++
hedef **AArch64 ELF olarak derlendi**. O aşamadaki kabulde **54 host ve 45 seri testi**
geçti. SDK değişikliği ve gerçek derleme hatası kontrollü olarak reddedildi.
Bu aşama `cross_build_only`: üretilen ARM64 programları çalıştırılmadı.

**WP-07'de** CAN ve seri testlerine ortak JSON/JUnit raporlaması,
girdileri doğrulayan kaynak snapshot'ı ve **hata raporundan tek komutla yeniden
çalıştırma** eklendi. Yeni raporlamayla **46 host, 45 seri ve 36 gerçek vcan testi
geçti**. Seri ve CAN kabulü önerilen yamaların ayrı kaynak kopyalarına aittir.
Özgün kaynaklardaki gerçek başarısızlıklar raporlarda korunur.

Üç özgün seri hatası, kasıtlı TX bozulması ve özgün CAN C gönderici hatası kayıtlı
kaynaklardan yeniden üretildi. Her tekrar aynı vaka/sonucu ve gerçek pytest
başarısızlık kodunu korudu. Özgün upstream dosyaları değiştirilmedi.

WP-01'de iki yönlü PTY ve ayrı Linux konuğunda gerçek `vcan` deneyleri
geçmişti. **Uzak CI kabulü açık:** GitHub Actions iş akışı proje deposuna
aktarılıyor; gerçek hosted koşunun dört profil ve toplam kabul sonucu
doğrulanana kadar bu madde açık kalır.

## Önce derleme yöneticisini çalıştır

Projenin kök klasöründe Linux, Python 3.12+, GCC, G++ ve GNU Make ile
çalıştırılır. Regresyon kontrolleri için Git de gerekir:

```sh
python3 -m tests.testlab targets
python3 -m tests.testlab build
python3 -W error::ResourceWarning -m unittest discover -s tests/host -v
```

Altı hedef için `build/testlab/host/<hedef>/<run-id>/` altında ayrı binary'ler;
`artifacts/testlab/<run-id>/` altında `run.json`, `commands.jsonl` ve hedef günlükleri
oluşur. Bu adımlar CAN yetkisi veya kart gerektirmez.

Kendi Gemstone examples çalışma ağacındaki değişiklikleri derlemek için:

```sh
python3 -m tests.testlab build --source-root /tam/yol/examples
```

Bu mod değiştirilmiş kaynakları kabul eder; referans sürümle farklarını ve
varsa Git commit/dirty bilgisini kaydeder. Dosyaları indirip eski sürüme döndürmez.
Tam açıklama: [WP02_BUILD.md](docs/WP02_BUILD.md).

## Gemstone SDK ile ARM64 derleme

Linux x86_64 bilgisayarda, Python 3.12+ ile:

```sh
python3 -m tests.testlab toolchain --output build/gemstone-sdk
python3 -m tests.testlab build --profile aarch64 --toolchain-root build/gemstone-sdk
```

İlk komut, `tests/toolchain.lock.json` içindeki yaklaşık 299 MB'lık resmî
v1.0.6 arşivini indirir; boyutunu ve SHA-256 değerini doğruladıktan sonra yeni
dizine açar. Kurulmuş 9.712 dosya/bağlantıyı da sabit bir özetle denetler.
Var olan kurulumun üstüne yazmaz. `--archive /tam/yol/arsiv.tar.gz` aynı arşivin
yerel kopyasını kullanır; özet kontrolü yine zorunludur.

İkinci komut SDK'nın GCC/G++ 11.2.1 ve Ubuntu Jammy sysroot'unu kullanır.
Çıktılar `build/testlab/aarch64/` altında host dosyalarından ayrılır. ELF başlığı,
Linux yükleyicisi, bağımlı kütüphaneler ve sembol sürümleri raporlanır. Kaynak
Makefile'ları ve uyarı bayrakları korunur; doğrulama hatasında host derleyicisine
düşülmez. ARM64 profilinde `--cc/--cxx` kabul edilmez.

Gerçek SDK ile olumsuz kontrolleri tekrar çalıştırmak için:

```sh
python3 tools/check_cross_build.py --toolchain-root build/gemstone-sdk --output artifacts/cross-check
```

Bu kontrol geçici alanda yaklaşık 1 GB'lık ayrı SDK kopyası oluşturur. Özgün
SDK'yı ve kaynak ağacını değiştirmez. Kurulum ayrıntıları ve kanıt dizinleri:
[WP08_CROSS_BUILD.md](docs/WP08_CROSS_BUILD.md).

## CI profillerini yerelde çalıştır

Bağımlılıkları ilgili requirements dosyasından hash kontrolüyle kurduktan sonra:

```sh
.venv-testlab/bin/python -m tests.testlab ci --profile host --output artifacts/ci-host
.venv-testlab/bin/python -m tests.testlab ci --profile serial --source-profile proposed-fixes --output artifacts/ci-serial
.venv-testlab/bin/python -m tests.testlab ci --profile can --source-profile proposed-fixes --output artifacts/ci-can
python3 -m tests.testlab ci --profile aarch64 --toolchain-root build/gemstone-sdk --output artifacts/ci-aarch64
```

Çıktı dizinleri yeni olmalıdır. CAN komutu normal kullanıcı ve devredilmiş
`sudo -n` ağ işlemleri gerektirir. Eksik önkoşul, hiç test olmaması, skip,
eksik zorunlu vaka veya değişmiş kanıt başarılı sonuç üretmez. `working-tree`
varsayılandır; `proposed-fixes` mevcut kaynakların özel bir kopyasına önerilen
yamaları açıkça uygular ve iki ağacın özetini ayrı kaydeder.

Her çıktıdaki `ci.json` birleşik denetime verilir. Ayrıntılar, kurulum,
yerel/hosted ayrımı ve beş işin kabul şartları: [WP09_CI.md](docs/WP09_CI.md).

## Ortak süreç yöneticisi

`tests/testlab/process.py` argv listesiyle başlatma, bağımsız süreç grubu,
stdout/stderr ve PTY okuma, süre sınırları ve kaynak temizliğini yönetir.
Derleme yöneticisi de bu modülü kullanır. Her çalıştırma için ham günlükler ve
`process.json` üretilir. SIGTERM'e yanıt vermeyen grup gerektiğinde SIGKILL ile
kapatılır; zorunlu temizlik normal kapanış başarısı sayılmaz.

Linux procfs ve child-subreaper desteği gerekir; root veya CAN yetkisi gerekmez.
Modülün kaynak sahipliği ve API'si: [WP03_PROCESS.md](docs/WP03_PROCESS.md).

## WP-07: rapor ve yeniden üretim

Her pytest çalışmasında verilen `--evidence-root` altında yeni bir run dizini
oluşur. `run.json`, pytest JUnit'i, `commands.jsonl`, kaynak snapshot'ı ve
`cases/<id>/result.json` üretilir. Başarısız/hatalı vaka ayrıca `failure.json`
alır; terminalde onu yeniden çalıştıracak tam komut yazılır.

`python -m tests.testlab reproduce --help` arayüzü; kaynak ve test hash'lerini,
Python bağımlılıklarını, tam pytest node'unu ve süre çarpanını denetler. Raporun
kayıtlı kaynaklarından yeni kopya oluşturur. Eski çalışma ağacını değiştirmez;
rapor içindeki keyfî komutları çalıştırmaz. Yeni test hâlâ bozuksa 1 döndürür.

Aynı sanal ortamı etkinleştirdikten sonra terminaldeki `TestLab reproduce:`
satırını kopyalamak yeterlidir. CAN yetkisi bulunmayan host için tek komuta
`--backend can-vm`, `--guest-root` ve `--wheels` eklenebilir.
Şema, durum kuralları, çalışma örnekleri ve gerçek kanıtlar:
[WP07_REPORTING.md](docs/WP07_REPORTING.md).

## WP-06: seri terminal matrisini çalıştır

Linux, Python 3.12, GCC/G++, Make ve Git ile:

```sh
python3 -m venv .venv-testlab
.venv-testlab/bin/python -m pip install --require-hashes -r tests/requirements-serial.txt
python3 tools/prepare_serial_fixes.py --output build/serial-fixed
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 TESTLAB_PYTHON=.venv-testlab/bin/python sh tests/scripts/run-serial-tests.sh --source-root build/serial-fixed --evidence-root artifacts/serial --junitxml=artifacts/serial.xml -q
```

Her uygulamaya ayrı konsol ve cihaz PTY'si bağlanır. İki yönlü bayt aktarımı,
parçalı veri, CR/LF ve ikili veri korunması, hatalı parametreler, yardım kodu ve
konsoldan Ctrl+C kapanışı kontrol edilir. Root, ağ yönetimi yetkisi veya `socat`
gerekmez. `pyserial`, Python seri örneği için hash ile sabitlenmiş bağımlılıktır.

Bu komut dört önerilen seri düzeltmesini **yeni bir kaynak kopyasına** uygular.
`--source-root` vermeden özgün sürümü sınamak 11 gerçek başarısızlık üretir:
C/C++ CR→LF dönüşümü ve kısmi baud sayısı kabulü, Python toplu giriş takılması ve
yardım çıkış kodu. Bunlar xfail veya skip değildir. Ayrıntılar, 45 vakanın matrisi
ve kontrollü bozulma komutu: [WP06_SERIAL.md](docs/WP06_SERIAL.md).
Katkı taslakları: [WP06_UPSTREAM_ISSUES.md](docs/WP06_UPSTREAM_ISSUES.md).

## WP-05: zorunlu CAN matrisini çalıştır

Test edilmiş profil: Ubuntu 24.04 ve Python 3.12. Normal kullanıcıyla:

```sh
python3 -m venv .venv-testlab
.venv-testlab/bin/python -m pip install --require-hashes -r tests/requirements.txt
python3 tools/prepare_can_fix.py --output build/can-fixed
TESTLAB_PYTHON=.venv-testlab/bin/python sh tests/scripts/run-can-tests.sh --source-root build/can-fixed --evidence-root artifacts/can -q
```

`iproute2`, `sudo`, `kmod`, GCC/G++ ve Make gerekir. Sarmalayıcı vcan modülünü
yükler; fixture kendi arayüzünü `sudo -n ip` ile yönetir. pytest normal kullanıcıyla
çalışır. Eksik önkoşul atlanmış başarılı test sayılmaz.

Bu komut önerilen C gönderici düzeltmesini **ayrı kaynak kopyasında** doğrular.
`patches/0001-can-c-sender-check-interface-index.patch`, `SIOCGIFINDEX` hatasının
kontrolünü ekler. `upstream/examples` özgün kalır. `--source-root` seçeneği
verilmeden çalıştırıldığında özgün sürüm sınanır; bilinen olmayan-arayüz
regresyonu başarısız sonuç üretir. Bu sonuç xfail/skip ile gizlenmez.

Host CAN yetkisi vermiyorsa pytest ve hedefleri normal kullanıcıyla çalıştıran
ayrı Linux konuğu yolu vardır. Bu teslimde gerçek CAN entegrasyon kanıtı bu yolla
alındı. Güncel matris, alıcı sözleşmesi ve kontrollü hata deneyi:
[WP05_CAN_MATRIX.md](docs/WP05_CAN_MATRIX.md). Temel sahiplik tasarımı:
[WP04_CAN.md](docs/WP04_CAN.md).

## Kaynak ve kapsam

- Kaynak: [t3gemstone/examples](https://github.com/t3gemstone/examples/tree/2619a7584d39203a057abc08ab7c6698dc476868).
- Sabit sürüm: `2619a7584d39203a057abc08ab7c6698dc476868`.
- Seçilen 27 dosya `upstream/examples/` altında özgün içerikleriyle bulunur.
  `source.lock.json` her dosyanın SHA-256 ve Git blob özetini içerir.
- WP-01 referans deneyi kaynak SHA-256 özetlerini zorunlu olarak doğrular.
  WP-02 mevcut çalışma ağacını derler ve kaynak farklarını raporlar.
  Paketlenen upstream uygulama kodu değiştirilmedi.
- Host derleme/süreç araçları standart kütüphaneyi kullanır. CAN senaryoları
  pytest kullanır; bağımlılıklar sürüm ve SHA-256 ile sabitlenmiştir. Seri testleri
  ayrıca `requirements-serial.txt` üzerinden pyserial kurar. Referans CAN ucu
  Gemstone alıcı kodunu kullanmaz; seri oracle'ı doğrudan beklenen baytları karşılaştırır.
- Bu paket bağımsız bir topluluk katkısı taslağıdır; resmî Gemstone sürümü değildir.

## WP-01: normal Linux veya Linux VM üzerinde I/O deneyi

Gerekenler: Linux, Python 3.10+, GCC, GNU Make, iproute2; gerektiğinde kmod ve
çekirdekle eşleşen `vcan` modülü. Sanal arayüz oluşturmak için root veya etkileşimsiz
`sudo` yetkisi gerekir. Konteynerde yalnızca UID=0 olmak yeterli değildir.

Ubuntu 24.04 üzerinde, paket yöneticisiyle gerekli araçları kurduktan sonra:

```sh
sudo apt-get update
sudo apt-get install --no-install-recommends -y build-essential python3 iproute2 kmod
sh tools/run-linux-wp01.sh artifacts/local
cat artifacts/local/runner.log
```

Betiğin tamamını `sudo` ile çalıştırmanız gerekmez. Betik yalnızca modül ve ağ
arayüzü işlemlerini yükseltilmiş yetkiyle yapar; kendi oluşturduğu `gtl<PID>`
arayüzünü çıkışta siler. Önceden var olan arayüzleri değiştirmez. `vcan` modülünü
çekirdekten kaldırmaz.

`Unknown device type` veya `Module vcan not found` alırsanız çekirdeğinizin
modüllerini kontrol edin. Bazı Ubuntu generic çekirdeklerinde `vcan`, çekirdeğin
**tam sürümüyle eşleşen** `linux-modules-extra` paketindedir. Docker'a yalnızca
Python paketleri kurmak çekirdek ve yetki eksikliğini gidermez.

## Tek tek çalıştırma

```sh
python3 tools/wp01.py doctor --output artifacts/doctor
python3 tools/wp01.py build --output artifacts/build
python3 tools/wp01.py serial --output artifacts/serial
python3 tools/wp01.py can --interface vcan0 --output artifacts/can
```

`can` komutu önceden oluşturulmuş ve UP durumundaki, başka trafik taşımayan bir
`vcan` arayüzü bekler. `doctor` araçları, PTY açmayı ve CAN soketi açmayı dener;
arayüz oluşturma yetkisi hakkında UID'den çıkarım yapmaz. Tam ortam kontrolünü
`run-linux-wp01.sh` gerçekleştirir.

Çıkış kodları: `0` geçti, `1` uygulama/derleme/doğrulama hatası, `2` eksik veya
engellenmiş önkoşul. Hazırlanmış arayüzdeki bozuk veri ve zaman aşımı başarısız
testtir. Engellenmiş bir önkoşul başarılı test sayılmaz.

## Deneyler neyi doğruluyor?

| Deney | İşlem | Beklenen gözlem |
| --- | --- | --- |
| Derleme | İki özgün alt dizinin Makefile'ını GCC ile çalıştır | İki binary ve çıkış kodu 0 |
| Seri hazırlık | Seri cihaz ve uygulama konsolu için ayrı PTY çiftleri aç | Hazırlık işareti uygulamadan konsola ulaşır |
| Seri RX | Seri cihazın karşı ucundan veri yaz | Konsolda aynı baytlar |
| Seri TX | Konsolun karşı ucundan veri yaz | Seri tarafta aynı baytlar |
| Seri kapanış | Konsola `0x03` yaz | Uygulama 0 ile kapanır; süreç toplanır; PTY fd'leri kapanır |
| CAN ilk çerçeve | Bağımsız alıcıyı bağla, sonra özgün göndericiyi başlat | ID `0x123`, DLC 8, `4d53475f30303000` |
| CAN kapanış | Göndericiye SIGINT gönder | ID `0x124`, DLC 3, `454e44`; gönderici 0 ile kapanır |

PTY testinde konsolun da PTY olması gerekir: özgün seri uygulaması stdin üzerinde
`tcgetattr` ve `tcsetattr` çağırır. Düz pipe bu terminal önkoşulunu karşılamaz.

`115200` ayarı uygulamaya verilir; PTY testi fiziksel baud hızını ölçmez.
`vcan` testi de fiziksel CAN hattını, bit zamanlamasını veya transceiver'ı sınamaz.

## WP-01 CAN deneyi bu ortamda nasıl çalıştı?

Host, CAN soketi açmayı ve ağ arayüzü oluşturmayı `EPERM` ile engelledi. Bunun
üzerine kullanıcı alanında QEMU TCG ile ayrı x86 Linux çekirdeği başlatıldı.
Konuğun kendi `vcan` arayüzünde özgün C göndericisi ve yeni C referans alıcı
çalıştırıldı. Konuğa ağ kartı eklenmedi; KVM ve host ağ yetkisi kullanılmadı.

Bu, **gerçek Linux SocketCAN/vcan yazılım deneyi**dir. AM67A, O1 kartı veya R5
emülasyonu değildir. ARM64 çalışma, gerçek UART/CAN donanımı ve gerçek zamanlı
davranış hakkında sonuç üretmez. İsteğe bağlı tekrar yolu için
[VM_REPRODUCTION.md](docs/VM_REPRODUCTION.md) dosyasına bakın.

## Dosyalar ve kanıtlar

| Konum | İçerik |
| --- | --- |
| `tools/wp01.py` | Kaynak doğrulama, iki derleme, PTY ve Python CAN referans deneyi |
| `tests/testlab/` | Altı hedeflik liste ve çalışma ağacını derleyen WP-02 yöneticisi |
| `tests/host/test_build_manager.py` | Beş derleme ve hata raporlama regresyon kontrolü |
| `tests/testlab/process.py` | I/O, süre sınırı, süreç grubu ve alt süreç toplama |
| `tests/testlab/pytest_report.py` | Pytest fazlarını ve cihaz kanıtlarını ortak JSON'a bağlar |
| `tests/testlab/reporting.py` | Kaynak/test özetleri, sınırlı snapshot ve rapor yardımcıları |
| `tests/testlab/reproduce.py` | Doğrulanan failure.json dosyasından tek node'u yeni kaynak kopyasında çalıştırır |
| `tests/host/test_reporting.py` | Dokuz gerçek alt pytest/CLI raporlama ve bütünlük kontrolü |
| `tests/host/test_process.py` | 17 gerçek süreç ve PTY kontrolü |
| `tests/fixtures/process_helper.py` | Kontrollü kapanan, hata veren ve takılan yardımcı süreçler |
| `tests/testlab/can.py` | Index/alias ile sahipliği doğrulanan vcan lease'i ve bağımsız SocketCAN ucu |
| `tests/testlab/contracts.py` | `can_examples_v1`: kimlik, uzunluk, veri ve dil farkları |
| `tests/testlab/receiver.py` | PTY konsolu, bağımsız hazırlık mesajı, çıktı ve kapanış kontrolü |
| `tests/can/` | 3 gönderici, 18 alıcı, 12 argüman ve 3 kaynak senaryosu |
| `tests/testlab/serial.py` | İki sahipli PTY, tek veriyle hazırlık, ham bayt oracle'ı ve temizlik |
| `tests/serial/` | Üç dilde 45 aktarım, argüman, yardım ve kaynak senaryosu |
| `tools/prepare_serial_fixes.py` | Dört seri yamasını yeni kaynak kopyasına uygular; hash'leri kaydeder |
| `tools/check_serial_mutation.py` | Kasıtlı TX bozulmasının gerçek PTY testinde reddedildiğini doğrular |
| `tests/host/test_receiver_contracts.py` | Çerçeve üretimi ve alıcı çıktı bozulmaları için 8 kontrol |
| `tests/host/test_receiver_readiness.py` | Gerçek süreç/PTY ile geç hazır olma regresyonu; CAN yayıncısı simüledir |
| `tests/requirements.txt` | Python 3.12 için sürüm ve hash ile seçilmiş pytest bağımlılıkları |
| `tools/run_can_suite_vm.py` | pytest ve altı CAN girişini UID 1000 ile vcan üzerinde çalıştıran Linux konuğu |
| `tools/check_can_mutation.py` | Özel kaynak kopyasında gerçek CAN testinin bozulmayı yakaladığını doğrular |
| `tools/prepare_can_fix.py` | Önerilen yamayı kontrol edip yeni bir kaynak kopyasına uygular |
| `patches/` | Bir CAN ve dört seri port düzeltme önerisi |
| `tools/can_reference.c` | Linux konuğunda çalıştırılmış bağımsız C SocketCAN alıcısı |
| `tools/run_can_vm.py` | Statik derleme, minimal initramfs ve QEMU ile gerçek vcan deneyi |
| `tools/run-linux-wp01.sh` | Linux/CI ortam kontrolü, geçici vcan, deneyler ve temizlik |
| `.github/workflows/testlab.yml` | Host derleme ve Linux I/O için ayrı CI işleri |
| `RESULTS.md` | Kabul maddeleri, gerçek gözlemler ve açık kalan madde |
| `artifacts/native-final/` | Native derleme ve PTY kanıtları; engellenen host CAN kaydı |
| `artifacts/can-linux-guest/` | Gerçek vcan çerçeveleri, konuk kapanışı ve temizlik kaydı |
| `artifacts/native-preflight/` | Host CAN yetkisinin bulunmadığını gösteren JSON |
| `artifacts/native-runner-attempt/` | Önkoşul eksikliğinde runner betiğinin 2 ile çıkış kanıtı |
| `artifacts/summary.json` | Çalıştırılmış raporlardan üretilen durum özeti |
| `artifacts/wp02-acceptance/` | Altı gerçek C/C++ derlemesinin komut ve çıktı kayıtları |
| `artifacts/wp02-regression/` | Kontrollü kaynak değişikliği ve hata senaryolarının kanıtları |
| `artifacts/wp03-validation/` | 22 host kontrolünün günlüğü ve süreç/PTY kanıtları |
| `artifacts/wp03-build-validation/` | Ortak modülle altı yeniden derleme ve süreç temizlik kayıtları |
| `artifacts/wp04-host-final/` | 28 host kontrolü, JUnit ve süreç kayıtları |
| `artifacts/wp04-vcan-validation/` | 6 konuk testi, çerçeveler, UID ve arayüz temizliği |
| `artifacts/wp04-clean-room/` | ZIP'ten altı yeniden derleme, 28 host ve 6 vcan testinin tekrarı |
| `artifacts/wp05-host-final/` | 37 host kontrolü ve 50 süreç temizliği kaydı |
| `artifacts/wp05-baseline-regression/` | Özgün C göndericisinin gerçek başarısız regresyonu |
| `artifacts/wp05-vcan-acceptance/` | Önerilen yama ile 36 başarılı vcan testi; 24 arayüz temizliği |
| `artifacts/wp05-controlled-failure/` | Kasıtlı DLC bozulmasının gerçek test tarafından reddi |
| `artifacts/wp05-clean-room/` | WP-05 temiz ZIP doğrulama kayıtları |
| `artifacts/wp06-baseline-final/` | Özgün seri sürümü: 34 başarılı, 11 gerçek başarısız vaka |
| `artifacts/wp06-acceptance/` | Seri yama kopyası: 45 başarılı vaka ve 50 süreç temizliği |
| `artifacts/wp06-controlled-failure/` | Gerçek PTY testinde kasıtlı bayt bozulmasının reddi |
| `artifacts/wp06-clean-room/` | WP-06 temiz ZIP doğrulaması |
| `artifacts/wp07-host/` | 46 host kontrolü ve yeni raporlama regresyonları |
| `artifacts/wp07-serial/` | Ortak raporlamayla 45 seri testi |
| `artifacts/wp07-can-vm/` | Ortak raporlamayla 36 gerçek vcan testi; 24 arayüz temizliği |
| `artifacts/wp07-baseline/` | Üç gerçek özgün seri başarısızlığı |
| `artifacts/wp07-reproduction/` | Taşınmış raporlardan dört gerçek seri tekrarı |
| `artifacts/wp07-can-reproduction/` | Gerçek CAN kusurunun konukta tek node tekrarı |
| `artifacts/wp07-clean-room/` | Güncel ZIP'ten derleme/host/seri ve taşınmış rapor tekrarının kanıtları |
| `tests/toolchain.lock.json` | Resmî SDK arşivi, kurulum özeti ve hedef kimliği |
| `artifacts/wp08-toolchain/` | Yayın kaynağı, kurulum ve 9.712 girdinin özetleri |
| `artifacts/wp08-cross-builds/` | Altı AArch64 ELF, Make/readelf günlükleri |
| `artifacts/wp08-controlled-final/` | Gerçek SDK ile dört kontrollü doğrulama |
| `artifacts/wp08-host-final/`, `artifacts/wp08-serial-final/` | 54 host ve 45 seri kabulü |
| `artifacts/wp08-clean-room/` | ZIP'ten host/ARM64/seri yeniden doğrulaması |
| `tests/ci-contract.json` | Zorunlu 66 host, 45 seri, 36 CAN vaka kimliği ve derleme hedefleri |
| `artifacts/wp09-host-final/`, `artifacts/wp09-serial-final/` | Ortak CI komutuyla host ve PTY kabulü |
| `artifacts/wp09-can-vm-final/` | CI komutunun UID 1000 ile gerçek vcan kabulü |
| `artifacts/wp09-aarch64-final/` | CI komutuyla altı AArch64 hedef |
| `artifacts/wp09-current-pr/` | Gerçek yerel Git commit değişiminin CI'da görülmesi |
| `artifacts/wp09-acceptance/` | Dört profilin kabulü ve reddedilen yanlış kanıtlar |
| `artifacts/wp09-clean-room/` | Temiz ZIP'ten ortak CI girişlerinin yeniden doğrulaması |

`run.json` kaynak sürümünü, komutları ve sonucu; I/O raporları doğrulanan baytları
kaydeder. `process.json` süreç dönüş kodunu, sinyalleri ve temizliği içerir.
Derleme günlükleri ve terminal/konuk günlükleri aynı dizindedir.
Binary'ler, Debian paketleri ve initramfs ZIP'e eklenmedi; araçlarla tekrar üretilir.
WP-01'in tarihsel raporlarındaki altı dosyalık kaynak kilidi ayrıca
`docs/wp01-source.lock.json` içinde korunur. WP-03'ün 20 dosyalık kilidi
`docs/wp03-source.lock.json` içindedir. WP-04'ün 22 dosyalık kilidi
`docs/wp04-source.lock.json` içindedir. WP-05'in 24 dosyalık kilidi
`docs/wp05-source.lock.json` içindedir. Güncel kilit 27 dosyadır.

## GitHub Actions kabulü

Paketin içeriği bir deponun köküne yerleştirildiğinde iş akışı push, pull request
ve elle çalıştırma olaylarında devreye girer. Ubuntu 24.04 runner üzerinde gereken
araçları kurar. `host-checks` altı hedefi ve 66 host kontrolünü; ayrı
`linux-integration` işi 36 pytest/vcan senaryosunu çalıştırır.
`serial-integration` işi dört önerilen seri yamasının kopyasında 45 PTY senaryosunu
ve kontrollü bayt bozulmasını çalıştırır. Hata veya engellenmiş önkoşul işi başarısız yapar; günlükler `always()` ile saklanır.
CAN işi, açıkça adlandırılmış hazırlık adımında önerilen yamayı özel kopyaya
uygular; özgün sürümün hatasız olduğu iddiasını üretmez. Yama özeti ve uygulama
günlükleri de kanıtlara eklenir.

`aarch64-cross-build` işi kilitli Gemstone SDK'yı kurar, altı hedefi derler ve
ELF/readelf kanıtlarını saklar. Bu iş hedef programlarını çalıştırmaz.

`acceptance` işi diğer dört işin artifact'lerini indirir. Aynı PR/commit,
kaynak ve test kodunun sınandığını; tüm işlerin ve kanıt denetimlerinin
geçtiğini doğrular. PR'ın head SHA'sı checkout edilir; uyuşmayan veya kirli
checkout, araçlar başlamadan reddedilir.

**Bu iş akışı henüz GitHub üzerinde çalıştırılmadı.** Kabulün kapanması için
başarılı bir run URL'si, JUnit dosyaları ve temizliği gösteren `lease.json` kayıtları gerekir.
Gereken gerçek sonuçlar [RESULTS.md](RESULTS.md) içinde listelenmiştir.

## Sonraki iş paketi

WP-09'un uzak kabulü için hedef TestLab depo adresi, başarılı run URL'si ve
saklanan kanıtlar gerekir. Ardından WP-10'da katkı paketleri ve ikinci
geliştiriciye yönelik son teslim hazırlanır. O1 donanımı, fiziksel UART/CAN
ve gerçek zamanlı davranış henüz sınanmadı.

Lisans: Apache-2.0. Kaynak atıfları için `NOTICE` ve `source.lock.json` dosyalarına bakın.
